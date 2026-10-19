import json
import os
import sys
from datetime import datetime

import psutil
import requests


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from incident_detection.detector import detect_incident
from database.storage import initialize_database, save_incident


CONFIG_FILE = os.path.join(
    BASE_DIR,
    "config",
    "monitoring.json"
)


def load_config():
    """Load application monitoring configuration."""

    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def collect_system_metrics():
    """Collect CPU, memory and disk usage."""

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


def find_process(process_name):
    """Check whether the configured application process is running."""

    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = process.info["name"]

            if name and process_name.lower() in name.lower():
                return {
                    "running": True,
                    "pid": process.info["pid"],
                    "name": name,
                }

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "running": False,
        "pid": None,
        "name": process_name,
    }


def check_application_health(url):
    """Check whether the configured application health endpoint responds."""

    try:
        response = requests.get(url, timeout=5)

        return {
            "reachable": True,
            "status_code": response.status_code,
            "healthy": response.status_code == 200,
        }

    except requests.RequestException:
        return {
            "reachable": False,
            "status_code": None,
            "healthy": False,
        }


def read_recent_logs(log_file, number_of_lines=10):
    """Read the most recent application log entries."""

    if not os.path.exists(log_file):
        return []

    with open(log_file, "r", encoding="utf-8") as file:
        lines = file.readlines()

    return lines[-number_of_lines:]


def analyze_logs(log_lines):
    """Look for ERROR and WARNING events in recent logs."""

    errors = []
    warnings = []

    for line in log_lines:

        if "ERROR" in line:
            errors.append(line.strip())

        if "WARNING" in line:
            warnings.append(line.strip())

    return {
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    initialize_database()
    config = load_config()

    application = config["application"]

    application_name = application["name"]
    base_url = application["base_url"]
    health_endpoint = application["health_endpoint"]
    process_name = application["process_name"]

    log_file = os.path.join(
        BASE_DIR,
        application["log_file"]
    )

    health_url = base_url + health_endpoint

    print("IncidentGraph Monitoring Agent")
    print("-" * 40)

    print(f"Application: {application_name}")

    metrics = collect_system_metrics()

    print(f"Timestamp : {metrics['timestamp']}")
    print(f"CPU Usage : {metrics['cpu_percent']}%")
    print(f"Memory    : {metrics['memory_percent']}%")
    print(f"Disk      : {metrics['disk_percent']}%")

    print(f"\n{application_name} Process:")

    process = find_process(process_name)

    print(f"Running   : {process['running']}")
    print(f"PID       : {process['pid']}")
    print(f"Process   : {process['name']}")

    print(f"\n{application_name} Health:")

    health = check_application_health(health_url)

    print(f"Reachable : {health['reachable']}")
    print(f"Status    : {health['status_code']}")
    print(f"Healthy   : {health['healthy']}")

    print("\nRecent Application Logs:")

    recent_logs = read_recent_logs(
        log_file,
        10
    )

    for log in recent_logs:
        print(log.strip())

    log_analysis = analyze_logs(recent_logs)

    print("\nLog Analysis:")
    print(f"Errors    : {log_analysis['error_count']}")
    print(f"Warnings  : {log_analysis['warning_count']}")

    incident = detect_incident(
        metrics,
        health,
        log_analysis
    )

    print("\nIncident Detection:")
    print(f"Detected  : {incident['incident_detected']}")
    print(f"Incident  : {incident['incident_id']}")
    if incident["incident_detected"]:
        save_incident(
            incident,
            metrics,
            health,
            application_name
        )
        print("Incident saved to SQLite database.")

    if incident["incident_detected"]:

        print("Reasons:")

        for reason in incident["reasons"]:
            print(f"- {reason}")
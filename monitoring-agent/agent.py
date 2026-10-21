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

    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = process.info["name"] or ""
            command = " ".join(process.info["cmdline"] or [])

            if (
                process_name.lower() in name.lower()
                or process_name.lower() in command.lower()
            ):
                return {
                    "running": True,
                    "pid": process.info["pid"],
                    "name": name or command,
                }

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "running": False,
        "pid": None,
        "name": process_name,
    }


def check_application_health(url):
    """Check whether the configured health endpoint responds."""

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

    try:
        with open(log_file, "r", encoding="utf-8") as file:
            lines = file.readlines()

        return lines[-number_of_lines:]

    except (OSError, UnicodeDecodeError) as error:
        print(f"Could not read log file {log_file}: {error}")
        return []


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


def monitor_application(application, metrics):
    """Monitor one application using shared server metrics."""

    application_name = application["name"]
    base_url = application["base_url"].rstrip("/")
    health_endpoint = application["health_endpoint"]
    process_name = application["process_name"]

    log_file = os.path.join(
        BASE_DIR,
        application["log_file"]
    )

    health_url = f"{base_url}/{health_endpoint.lstrip('/')}"

    print("\n" + "=" * 50)
    print(f"Application: {application_name}")
    print("=" * 50)

    print(f"Timestamp : {metrics['timestamp']}")
    print(f"CPU Usage : {metrics['cpu_percent']}%")
    print(f"Memory    : {metrics['memory_percent']}%")
    print(f"Disk      : {metrics['disk_percent']}%")

    process = find_process(process_name)

    print(f"\n{application_name} Process:")
    print(f"Running   : {process['running']}")
    print(f"PID       : {process['pid']}")
    print(f"Process   : {process['name']}")

    health = check_application_health(health_url)

    print(f"\n{application_name} Health:")
    print(f"Reachable : {health['reachable']}")
    print(f"Status    : {health['status_code']}")
    print(f"Healthy   : {health['healthy']}")

    recent_logs = read_recent_logs(log_file)

    print("\nRecent Application Logs:")
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
        print("Reasons:")

        for reason in incident["reasons"]:
            print(f"- {reason}")


def main():
    """Initialize storage and monitor all configured applications."""

    initialize_database()
    config = load_config()

    applications = config.get("applications", [])

    if not applications:
        raise ValueError(
            "No applications configured in config/monitoring.json"
        )

    print("IncidentGraph Monitoring Agent")
    print(f"Applications configured: {len(applications)}")

    # These metrics describe the shared server, not individual apps.
    metrics = collect_system_metrics()

    for application in applications:
        try:
            monitor_application(application, metrics)

        except (KeyError, TypeError, ValueError) as error:
            name = application.get("name", "Unknown application")
            print(f"\nConfiguration/data error for {name}: {error}")

        except Exception as error:
            name = application.get("name", "Unknown application")
            print(f"\nMonitoring failed for {name}: {error}")


if __name__ == "__main__":
    main()

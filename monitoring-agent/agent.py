import os
from datetime import datetime

import psutil
import requests


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "logs", "demoshop.log")


def collect_system_metrics():
    """Collect CPU, memory and disk usage."""

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


def find_process(process_name):
    """Check whether a process with the given name is running."""

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
    """Check whether the DemoShop health endpoint is responding."""

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


def read_recent_logs(number_of_lines=10):
    """Read the most recent DemoShop log entries."""

    if not os.path.exists(LOG_FILE):
        return []

    with open(LOG_FILE, "r", encoding="utf-8") as file:
        lines = file.readlines()

    return lines[-number_of_lines:]


def analyze_logs(log_lines):
    """Look for ERROR and WARNING events in the recent logs."""

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
    print("IncidentGraph Monitoring Agent")
    print("-" * 40)

    metrics = collect_system_metrics()

    print(f"Timestamp : {metrics['timestamp']}")
    print(f"CPU Usage : {metrics['cpu_percent']}%")
    print(f"Memory    : {metrics['memory_percent']}%")
    print(f"Disk      : {metrics['disk_percent']}%")

    print("\nDemoShop Process:")

    process = find_process("python")

    print(f"Running   : {process['running']}")
    print(f"PID       : {process['pid']}")
    print(f"Process   : {process['name']}")

    print("\nDemoShop Health:")

    health = check_application_health(
        "http://127.0.0.1:5000/health"
    )

    print(f"Reachable : {health['reachable']}")
    print(f"Status    : {health['status_code']}")
    print(f"Healthy   : {health['healthy']}")

    print("\nRecent Application Logs:")

    recent_logs = read_recent_logs(10)

    for log in recent_logs:
        print(log.strip())

    log_analysis = analyze_logs(recent_logs)

    print("\nLog Analysis:")
    print(f"Errors    : {log_analysis['error_count']}")
    print(f"Warnings  : {log_analysis['warning_count']}")
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil
import requests


BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from incident_detection.detector import detect_incident
from database.storage import (
    initialize_database,
    save_incident,
    resolve_application_incidents,
    get_log_cursor,
    update_log_cursor,
)

CONFIG_FILE = BASE_DIR / "config" / "monitoring.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config.get("applications"), list):
        raise ValueError("'applications' must be a list in monitoring.json")

    return config


def collect_system_metrics():
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


def find_process(process_name):
    """Find a process by configured name or command-line text."""
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

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    return {
        "running": False,
        "pid": None,
        "name": process_name,
    }


def check_application_health(url):
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


def read_new_logs(application_name, log_file):
    """
    Read only log entries appended since the previous check.

    On the first run, existing log content is skipped. File rotation
    and truncation are detected using inode and file size.
    """
    log_path = Path(log_file)

    if not log_path.exists():
        return []

    try:
        with log_path.open("rb") as file:
            stat = os.fstat(file.fileno())
            current_inode = stat.st_ino
            current_size = stat.st_size
            cursor = get_log_cursor(application_name)

            if cursor is None:
                # Establish a starting point without replaying old logs.
                offset = current_size
            elif (
                cursor["file_path"] != str(log_path.resolve())
                or cursor["file_inode"] != current_inode
                or current_size < cursor["file_offset"]
            ):
                # New file, rotated file, or truncated file.
                offset = 0
            else:
                offset = cursor["file_offset"]

            file.seek(offset)
            content = file.read()
            new_offset = file.tell()

            update_log_cursor(
                application_name,
                str(log_path.resolve()),
                current_inode,
                new_offset,
            )

        return content.decode("utf-8", errors="replace").splitlines()

    except OSError as error:
        print(f"Could not read log file {log_path}: {error}")
        return []


def analyze_logs(log_lines):
    """Count only entries explicitly marked with ERROR or WARNING."""
    errors = []
    warnings = []

    for line in log_lines:
        if " - ERROR - " in line:
            errors.append(line.strip())
        elif " - WARNING - " in line:
            warnings.append(line.strip())

    return {
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def monitor_application(application, metrics):
    application_name = application["name"]
    base_url = application["base_url"].rstrip("/")
    health_endpoint = application.get("health_endpoint", "/health")
    process_name = application["process_name"]

    log_file = BASE_DIR / application["log_file"]
    health_url = f"{base_url}/{health_endpoint.lstrip('/')}"

    process = find_process(process_name)
    health = check_application_health(health_url)

    # Both the process and HTTP health endpoint must be healthy.
    effective_health = {
        **health,
        "healthy": health["healthy"] and process["running"],
    }

    new_logs = read_new_logs(application_name, log_file)
    log_analysis = analyze_logs(new_logs)

    incident = detect_incident(
        metrics,
        effective_health,
        log_analysis,
    )

    print("\n" + "=" * 55)
    print(f"Application : {application_name}")
    print("=" * 55)
    print(f"Timestamp   : {metrics['timestamp']}")
    print(f"CPU         : {metrics['cpu_percent']}%")
    print(f"Memory      : {metrics['memory_percent']}%")
    print(f"Disk        : {metrics['disk_percent']}%")
    print(f"Process     : {'Running' if process['running'] else 'Stopped'}")
    print(f"PID         : {process['pid']}")
    print(f"HTTP status : {health['status_code']}")
    print(f"Healthy     : {effective_health['healthy']}")
    print(f"New log lines: {len(new_logs)}")
    print(f"New errors  : {log_analysis['error_count']}")
    print(f"New warnings: {log_analysis['warning_count']}")

    if incident["incident_detected"]:
        incident_id = save_incident(
            incident,
            metrics,
            effective_health,
            application_name,
        )

        print("\nIncident detected.")
        print(f"Incident ID : {incident_id}")

        for reason in incident.get("reasons", []):
            print(f"- {reason}")

    else:
        resolved_count = resolve_application_incidents(application_name)

        if resolved_count:
            print(f"\nRecovery detected. Resolved {resolved_count} incident(s).")
        else:
            print("\nNo active incident detected.")


def run_cycle(applications):
    """Run one monitoring cycle across all configured applications."""
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


def main():
    parser = argparse.ArgumentParser(description="IncidentGraph AI monitoring agent")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one monitoring cycle and exit",
    )
    args = parser.parse_args()

    initialize_database()
    config = load_config()
    applications = config["applications"]

    if not applications:
        raise ValueError("No applications configured in monitoring.json")

    interval = config.get("poll_interval_seconds", 15)

    if not isinstance(interval, (int, float)) or interval < 5:
        raise ValueError("poll_interval_seconds must be at least 5")

    print("IncidentGraph AI Monitoring Agent")
    print(f"Applications configured: {len(applications)}")
    print(f"Polling interval: {interval} seconds")

    if args.once:
        run_cycle(applications)
        return

    print("Continuous monitoring started. Press CTRL+C to stop.")

    try:
        while True:
            cycle_started = time.monotonic()
            run_cycle(applications)

            elapsed = time.monotonic() - cycle_started
            sleep_time = max(0, interval - elapsed)

            print(f"\nNext monitoring cycle in {sleep_time:.1f} seconds.")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")


if __name__ == "__main__":
    main()

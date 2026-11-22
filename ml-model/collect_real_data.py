import csv
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

import psutil
import requests

OUTPUT = Path(__file__).resolve().parent / "real_world_metrics.csv"
HEALTH_URL = "http://127.0.0.1:5000/health"

parser = argparse.ArgumentParser()
parser.add_argument("--samples", type=int, default=20)
parser.add_argument("--interval", type=int, default=5)
args = parser.parse_args()

fields = [
    "timestamp", "cpu_percent", "memory_percent",
    "disk_percent", "health_healthy", "error_count",
    "warning_count", "experiment_label"
]

new_file = not OUTPUT.exists()

with OUTPUT.open("a", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fields)

    if new_file:
        writer.writeheader()

    print(f"Collecting {args.samples} real system measurements...")

    for index in range(args.samples):
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent

        try:
            response = requests.get(HEALTH_URL, timeout=3)
            healthy = int(response.status_code == 200)
        except requests.RequestException:
            healthy = 0

        writer.writerow({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": cpu,
            "memory_percent": memory,
            "disk_percent": disk,
            "health_healthy": healthy,
            "error_count": 0,
            "warning_count": 0,
            "experiment_label": "normal"
        })

        file.flush()
        print(f"Sample {index + 1}/{args.samples}: CPU {cpu}%, Memory {memory}%, Disk {disk}%")
        if index + 1 < args.samples:
            time.sleep(args.interval)

print(f"\nSaved measurements to: {OUTPUT}")

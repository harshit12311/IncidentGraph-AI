from datetime import datetime


def detect_incident(metrics, health, log_analysis):
    """
    Determine whether the collected monitoring information
    represents an incident.
    """

    reasons = []

    # Application unavailable
    if not health["healthy"]:
        reasons.append("Application health check failed")

    # Application errors
    if log_analysis["error_count"] > 0:
        reasons.append(
            f"{log_analysis['error_count']} application error(s) detected"
        )

    # High CPU
    if metrics["cpu_percent"] >= 90:
        reasons.append("High CPU utilization")

    # High memory
    if metrics["memory_percent"] >= 90:
        reasons.append("High memory utilization")

    # High disk
    if metrics["disk_percent"] >= 90:
        reasons.append("High disk utilization")

    incident_detected = len(reasons) > 0

    if incident_detected:
        return {
            "incident_detected": True,
            "incident_id": f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "reasons": reasons,
        }

    return {
        "incident_detected": False,
        "incident_id": None,
        "timestamp": datetime.now().isoformat(),
        "reasons": [],
    }
#tempo
if __name__ == "__main__":

    test_metrics = {
        "cpu_percent": 20,
        "memory_percent": 50,
        "disk_percent": 40,
    }

    test_health = {
        "healthy": False
    }

    test_log_analysis = {
        "error_count": 1,
        "warning_count": 0,
        "errors": [
            "CONTROLLED FAILURE: Simulated database connection error"
        ],
        "warnings": []
    }

    incident = detect_incident(
        test_metrics,
        test_health,
        test_log_analysis
    )

    print("Incident Detection Test")
    print("-" * 40)
    print(f"Incident detected : {incident['incident_detected']}")
    print(f"Incident ID       : {incident['incident_id']}")
    print(f"Timestamp         : {incident['timestamp']}")
    print("Reasons:")

    for reason in incident["reasons"]:
        print(f"- {reason}")
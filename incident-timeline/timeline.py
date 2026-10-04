from datetime import datetime


def create_timeline(events):
    """
    Create a structured timeline from correlated events.
    """

    if not events:
        return None

    sorted_events = sorted(
        events,
        key=lambda event: event["timestamp"]
    )

    start_time = datetime.fromisoformat(
        sorted_events[0]["timestamp"]
    )

    end_time = datetime.fromisoformat(
        sorted_events[-1]["timestamp"]
    )

    duration_seconds = (
        end_time - start_time
    ).total_seconds()

    timeline = {
        "start_time": sorted_events[0]["timestamp"],
        "end_time": sorted_events[-1]["timestamp"],
        "duration_seconds": duration_seconds,
        "event_count": len(sorted_events),
        "events": sorted_events
    }

    return timeline


if __name__ == "__main__":

    test_events = [
        {
            "timestamp": "2026-10-04T22:00:00",
            "type": "database_error",
            "message": "Database connection failed"
        },
        {
            "timestamp": "2026-10-04T22:00:10",
            "type": "http_500",
            "message": "Checkout returned HTTP 500"
        },
        {
            "timestamp": "2026-10-04T22:00:25",
            "type": "application_error",
            "message": "Checkout operation failed"
        }
    ]

    timeline = create_timeline(test_events)

    print("Incident Timeline")
    print("-" * 40)

    print(f"Start time : {timeline['start_time']}")
    print(f"End time   : {timeline['end_time']}")
    print(f"Duration   : {timeline['duration_seconds']} seconds")
    print(f"Events     : {timeline['event_count']}")

    print("\nEvent Sequence:")

    for event in timeline["events"]:
        print(
            f"{event['timestamp']} | "
            f"{event['type']} | "
            f"{event['message']}"
        )
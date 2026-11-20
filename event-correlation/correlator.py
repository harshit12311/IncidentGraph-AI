from datetime import datetime


def events_are_related(first, second):
    """Check whether two events share meaningful incident characteristics."""
    same_cause = (
        first.get("predicted_root_cause")
        and first.get("predicted_root_cause")
        == second.get("predicted_root_cause")
    )

    same_type = (
        first.get("type")
        and first.get("type") == second.get("type")
    )

    same_application = (
        first.get("application_name")
        and first.get("application_name")
        == second.get("application_name")
    )

    return bool(same_cause or same_type or same_application)


def correlate_events(events, time_window_seconds=60):
    """
    Group related events that occur within a specified time window.
    """

    if not events:
        return []

    # Sort events by timestamp
    sorted_events = sorted(
        events,
        key=lambda event: event["timestamp"]
    )

    incidents = []
    current_incident = [sorted_events[0]]

    for event in sorted_events[1:]:

        previous_time = datetime.fromisoformat(
            current_incident[-1]["timestamp"]
        )

        current_time = datetime.fromisoformat(
            event["timestamp"]
        )

        time_difference = (
            current_time - previous_time
        ).total_seconds()

        has_correlation_data = any(
            event.get(key)
            for key in ("predicted_root_cause", "type", "application_name")
        ) or any(
            current_incident[-1].get(key)
            for key in ("predicted_root_cause", "type", "application_name")
        )

        related = events_are_related(current_incident[-1], event)

        if time_difference <= time_window_seconds and (
            related or not has_correlation_data
        ):
            current_incident.append(event)

        else:
            incidents.append(current_incident)
            current_incident = [event]

    incidents.append(current_incident)

    return incidents


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
        },
        {
            "timestamp": "2026-10-04T22:05:00",
            "type": "health_check",
            "message": "Application unavailable"
        }
    ]

    correlated = correlate_events(
        test_events,
        time_window_seconds=60
    )

    print("Event Correlation Test")
    print("-" * 40)

    for number, incident_events in enumerate(correlated, start=1):

        print(f"\nIncident Group {number}")
        print(f"Events: {len(incident_events)}")

        for event in incident_events:
            print(
                f"- {event['type']}: "
                f"{event['message']}"
            )
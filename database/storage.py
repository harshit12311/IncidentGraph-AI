import sqlite3
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_FILE = BASE_DIR / "database" / "incidents.db"


def get_connection():
    """Create a connection to the SQLite database."""
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create the incidents table if it does not exist."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                application_name TEXT NOT NULL,
                detected INTEGER NOT NULL,
                reasons TEXT NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                disk_percent REAL,
                health_status TEXT NOT NULL
            )
        """)


def save_incident(incident, metrics, health, application_name):
    """Save one detected incident to the database."""
    if not incident.get("incident_detected"):
        return None

    reasons = "; ".join(incident.get("reasons", []))

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO incidents (
                incident_id, timestamp, application_name, detected,
                reasons, cpu_percent, memory_percent, disk_percent,
                health_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(incident_id) DO NOTHING
        """, (
            incident["incident_id"],
            incident.get("timestamp", datetime.now().isoformat()),
            application_name,
            1,
            reasons,
            metrics.get("cpu_percent"),
            metrics.get("memory_percent"),
            metrics.get("disk_percent"),
            "healthy" if health.get("healthy") else "unhealthy",
        ))

        return cursor.lastrowid


def get_recent_incidents(limit=20):
    """Return the most recent incidents."""
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM incidents
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]

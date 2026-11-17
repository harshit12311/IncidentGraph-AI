import sqlite3
import uuid
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_FILE = BASE_DIR / "database" / "incidents.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create tables and safely migrate existing incident records."""
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

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(incidents)"
            ).fetchall()
        }

        if "status" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN status TEXT NOT NULL DEFAULT 'resolved'
            """)

        if "resolved_at" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN resolved_at TEXT
            """)

        if "last_seen_at" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN last_seen_at TEXT
            """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS log_cursors (
                application_name TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_inode INTEGER NOT NULL,
                file_offset INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS website_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                website_name TEXT NOT NULL,
                url TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                status_code INTEGER,
                response_time_ms REAL,
                available INTEGER NOT NULL,
                error_message TEXT
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_status
            ON incidents(status)
        """)


def save_incident(incident, metrics, health, application_name):
    """Create an incident or update the existing open incident for an app."""
    if not incident.get("incident_detected"):
        return None

    now = incident.get("timestamp") or datetime.now().isoformat()
    reasons = "; ".join(incident.get("reasons", []))
    health_status = "healthy" if health.get("healthy") else "unhealthy"

    with get_connection() as connection:
        existing = connection.execute("""
            SELECT id, incident_id
            FROM incidents
            WHERE application_name = ? AND status = 'open'
            ORDER BY id DESC
            LIMIT 1
        """, (application_name,)).fetchone()

        if existing:
            connection.execute("""
                UPDATE incidents
                SET last_seen_at = ?,
                    reasons = ?,
                    cpu_percent = ?,
                    memory_percent = ?,
                    disk_percent = ?,
                    health_status = ?
                WHERE id = ?
            """, (
                now,
                reasons,
                metrics.get("cpu_percent"),
                metrics.get("memory_percent"),
                metrics.get("disk_percent"),
                health_status,
                existing["id"],
            ))
            return existing["incident_id"]

        incident_id = (
            f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}-"
            f"{uuid.uuid4().hex[:8]}"
        )

        connection.execute("""
            INSERT INTO incidents (
                incident_id, timestamp, application_name, detected,
                reasons, cpu_percent, memory_percent, disk_percent,
                health_status, status, last_seen_at
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, 'open', ?)
        """, (
            incident_id,
            now,
            application_name,
            reasons,
            metrics.get("cpu_percent"),
            metrics.get("memory_percent"),
            metrics.get("disk_percent"),
            health_status,
            now,
        ))

        return incident_id


def resolve_application_incidents(application_name):
    """Resolve all open incidents for an application after recovery."""
    now = datetime.now().isoformat()

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE incidents
            SET status = 'resolved', resolved_at = ?
            WHERE application_name = ? AND status = 'open'
        """, (now, application_name))

        return cursor.rowcount


def get_log_cursor(application_name):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT file_path, file_inode, file_offset
            FROM log_cursors
            WHERE application_name = ?
        """, (application_name,)).fetchone()

        return dict(row) if row else None


def update_log_cursor(application_name, file_path, file_inode, file_offset):
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO log_cursors (
                application_name, file_path, file_inode,
                file_offset, updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(application_name) DO UPDATE SET
                file_path = excluded.file_path,
                file_inode = excluded.file_inode,
                file_offset = excluded.file_offset,
                updated_at = excluded.updated_at
        """, (
            application_name,
            str(file_path),
            file_inode,
            file_offset,
            datetime.now().isoformat(),
        ))



def record_website_check(
    website_name, url, status_code, response_time_ms,
    available, error_message=None
):
    """Persist one external website availability check."""
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO website_checks (
                website_name, url, checked_at, status_code,
                response_time_ms, available, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            website_name,
            url,
            datetime.now().isoformat(),
            status_code,
            response_time_ms,
            1 if available else 0,
            error_message,
        ))


def get_recent_website_checks(limit=50):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM website_checks
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_website_check_summary():
    with get_connection() as connection:
        row = connection.execute("""
            SELECT
                COUNT(*) AS total_checks,
                COALESCE(SUM(available), 0) AS successful_checks,
                COALESCE(AVG(response_time_ms), 0) AS average_response_time_ms
            FROM website_checks
        """).fetchone()

        total = row["total_checks"]
        successful = row["successful_checks"]

        return {
            "total_checks": total,
            "successful_checks": successful,
            "failed_checks": total - successful,
            "availability_percent": (
                round(successful * 100 / total, 2) if total else None
            ),
            "average_response_time_ms": round(
                row["average_response_time_ms"], 2
            ),
        }


def get_recent_incidents(limit=20):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM incidents
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]


def get_incident_summary():
    with get_connection() as connection:
        total = connection.execute("""
            SELECT COUNT(*) FROM incidents
        """).fetchone()[0]

        by_application = connection.execute("""
            SELECT application_name, COUNT(*) AS incident_count
            FROM incidents
            GROUP BY application_name
            ORDER BY incident_count DESC
        """).fetchall()

        by_health_status = connection.execute("""
            SELECT health_status, COUNT(*) AS incident_count
            FROM incidents
            GROUP BY health_status
        """).fetchall()

        by_status = connection.execute("""
            SELECT status, COUNT(*) AS incident_count
            FROM incidents
            GROUP BY status
        """).fetchall()

        return {
            "total_incidents": total,
            "by_application": [dict(row) for row in by_application],
            "by_health_status": [dict(row) for row in by_health_status],
            "by_status": [dict(row) for row in by_status],
        }

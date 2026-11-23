import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
import json

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

        if "severity" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN severity TEXT
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
        if "predicted_root_cause" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN predicted_root_cause TEXT
            """)

        if "confidence_percent" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN confidence_percent REAL
            """)

        if "root_cause_probabilities" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN root_cause_probabilities TEXT
            """)

        if "website_status_code" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN website_status_code INTEGER
            """)

        if "website_response_time_ms" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN website_response_time_ms REAL
            """)

        if "website_url" not in columns:
            connection.execute("""
                ALTER TABLE incidents
                ADD COLUMN website_url TEXT
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
            CREATE TABLE IF NOT EXISTS application_health (
                application_name TEXT PRIMARY KEY,
                checked_at TEXT NOT NULL,
                process_running INTEGER NOT NULL,
                pid INTEGER,
                status_code INTEGER,
                healthy INTEGER NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                disk_percent REAL
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_status
            ON incidents(status)
        """)



def save_incident(
    incident,
    metrics,
    health,
    application_name,
    prediction=None,
):
    """Create or update an incident with its ML root-cause prediction."""
    if not incident.get("incident_detected"):
        return None

    now = incident.get("timestamp") or datetime.now().isoformat()
    reasons = "; ".join(incident.get("reasons", []))
    health_status = "healthy" if health.get("healthy") else "unhealthy"

    prediction = prediction or {}
    predicted_root_cause = prediction.get("predicted_root_cause")
    confidence_percent = prediction.get("confidence_percent")
    probabilities = prediction.get("probabilities")

    probabilities_json = (
        json.dumps(probabilities) if probabilities is not None else None
    )

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
                    health_status = ?,
                    severity = ?,
                    predicted_root_cause = ?,
                    confidence_percent = ?,
                    root_cause_probabilities = ?
                WHERE id = ?
            """, (
                now,
                reasons,
                metrics.get("cpu_percent"),
                metrics.get("memory_percent"),
                metrics.get("disk_percent"),
                health_status,
                incident.get("severity"),
                predicted_root_cause,
                confidence_percent,
                probabilities_json,
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
                health_status, status, last_seen_at, severity,
                predicted_root_cause, confidence_percent,
                root_cause_probabilities
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
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
            incident.get("severity"),
            predicted_root_cause,
            confidence_percent,
            probabilities_json,
        ))

        return incident_id



def save_website_incident(
    website_name, url, status_code, response_time_ms, error_message=None
):
    """Create or update one open incident for an unavailable website."""
    now = datetime.now().isoformat()
    application_name = f"Website: {website_name}"
    reason = error_message or f"Website returned HTTP {status_code}"

    with get_connection() as connection:
        existing = connection.execute("""
            SELECT incident_id FROM incidents
            WHERE application_name = ? AND status = 'open'
            ORDER BY id DESC LIMIT 1
        """, (application_name,)).fetchone()

        if existing:
            connection.execute("""
                UPDATE incidents
                SET last_seen_at = ?, reasons = ?, health_status = 'unhealthy',
                    website_status_code = ?, website_response_time_ms = ?,
                    website_url = ?
                WHERE incident_id = ?
            """, (
                now, reason, status_code, response_time_ms,
                url, existing["incident_id"]
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
                health_status, status, last_seen_at, severity,
                predicted_root_cause, confidence_percent,
                website_status_code, website_response_time_ms, website_url
            )
            VALUES (?, ?, ?, 1, ?, NULL, NULL, NULL,
                    'unhealthy', 'open', ?, 'High',
                    'website_unavailable', NULL, ?, ?, ?)
        """, (
            incident_id, now, application_name, reason, now,
            status_code, response_time_ms, url
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



def resolve_website_incidents(website_name):
    """Resolve open website incidents after a successful availability check."""
    now = datetime.now().isoformat()
    application_name = f"Website: {website_name}"

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

        by_severity = connection.execute("""
            SELECT severity, COUNT(*) AS incident_count
            FROM incidents
            WHERE severity IS NOT NULL
            GROUP BY severity
        """).fetchall()

        return {
            "total_incidents": total,
            "by_application": [dict(row) for row in by_application],
            "by_health_status": [dict(row) for row in by_health_status],
            "by_status": [dict(row) for row in by_status],
            "by_severity": [dict(row) for row in by_severity],
        }


def get_incident_by_id(incident_id):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT *
            FROM incidents
            WHERE incident_id = ?
        """, (incident_id,)).fetchone()

        if row is None:
            return None

        incident = dict(row)

        if incident.get("root_cause_probabilities"):
            import json
            try:
                incident["root_cause_probabilities"] = json.loads(
                    incident["root_cause_probabilities"]
                )
            except (json.JSONDecodeError, TypeError):
                incident["root_cause_probabilities"] = {}

        return incident


def save_application_health(application_name, checked_at, process, health, metrics):
    """Store the latest application monitoring snapshot."""
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO application_health (
                application_name, checked_at, process_running, pid,
                status_code, healthy, cpu_percent, memory_percent, disk_percent
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(application_name) DO UPDATE SET
                checked_at = excluded.checked_at,
                process_running = excluded.process_running,
                pid = excluded.pid,
                status_code = excluded.status_code,
                healthy = excluded.healthy,
                cpu_percent = excluded.cpu_percent,
                memory_percent = excluded.memory_percent,
                disk_percent = excluded.disk_percent
        """, (
            application_name,
            checked_at,
            int(process.get("running", False)),
            process.get("pid"),
            health.get("status_code"),
            int(health.get("healthy", False)),
            metrics.get("cpu_percent"),
            metrics.get("memory_percent"),
            metrics.get("disk_percent"),
        ))


def get_latest_application_health():
    """Return the latest health snapshot for each monitored application."""
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM application_health
            ORDER BY application_name
        """).fetchall()
        return [dict(row) for row in rows]


# User-scoped queries for the multi-user platform.
def get_user_recent_incidents(user_id, limit=20):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM incidents
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()

        return [dict(row) for row in rows]


def get_user_incident_by_id(user_id, incident_id):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT *
            FROM incidents
            WHERE user_id = ? AND incident_id = ?
        """, (user_id, incident_id)).fetchone()

        if row is None:
            return None

        incident = dict(row)

        if incident.get("root_cause_probabilities"):
            try:
                incident["root_cause_probabilities"] = json.loads(
                    incident["root_cause_probabilities"]
                )
            except (json.JSONDecodeError, TypeError):
                incident["root_cause_probabilities"] = {}

        return incident


def get_user_incident_summary(user_id):
    with get_connection() as connection:
        total = connection.execute("""
            SELECT COUNT(*) FROM incidents WHERE user_id = ?
        """, (user_id,)).fetchone()[0]

        queries = {
            "by_application": """
                SELECT application_name, COUNT(*) AS incident_count
                FROM incidents WHERE user_id = ?
                GROUP BY application_name ORDER BY incident_count DESC
            """,
            "by_health_status": """
                SELECT health_status, COUNT(*) AS incident_count
                FROM incidents WHERE user_id = ?
                GROUP BY health_status
            """,
            "by_status": """
                SELECT status, COUNT(*) AS incident_count
                FROM incidents WHERE user_id = ?
                GROUP BY status
            """,
            "by_severity": """
                SELECT severity, COUNT(*) AS incident_count
                FROM incidents
                WHERE user_id = ? AND severity IS NOT NULL
                GROUP BY severity
            """,
        }

        result = {"total_incidents": total}

        for key, query in queries.items():
            rows = connection.execute(query, (user_id,)).fetchall()
            result[key] = [dict(row) for row in rows]

        return result


def get_user_recent_website_checks(user_id, limit=50):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM website_checks
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()

        return [dict(row) for row in rows]


def get_user_website_check_summary(user_id):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT
                COUNT(*) AS total_checks,
                COALESCE(SUM(available), 0) AS successful_checks,
                COALESCE(AVG(response_time_ms), 0) AS average_response_time_ms
            FROM website_checks
            WHERE user_id = ?
        """, (user_id,)).fetchone()

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


# Multi-tenant website monitoring storage.
def record_user_website_check(
    user_id, website_id, website_name, url,
    status_code, response_time_ms, available, error_message=None
):
    """Store a website check for its verified owner."""
    with get_connection() as connection:
        website = connection.execute("""
            SELECT id FROM monitored_websites
            WHERE id = ? AND user_id = ?
        """, (website_id, user_id)).fetchone()

        if website is None:
            raise ValueError("Website does not belong to this user.")

        connection.execute("""
            INSERT INTO website_checks (
                website_name, url, checked_at, status_code,
                response_time_ms, available, error_message,
                user_id, website_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            website_name, url, datetime.now().isoformat(),
            status_code, response_time_ms,
            1 if available else 0, error_message,
            user_id, website_id
        ))


def save_user_website_incident(
    user_id, website_id, website_name, url,
    status_code, response_time_ms, error_message=None
):
    """Create or update an open incident for one user's website."""
    now = datetime.now().isoformat()
    application_name = f"Website: {website_name}"
    reason = error_message or f"Website returned HTTP {status_code}"

    with get_connection() as connection:
        website = connection.execute("""
            SELECT id FROM monitored_websites
            WHERE id = ? AND user_id = ?
        """, (website_id, user_id)).fetchone()

        if website is None:
            raise ValueError("Website does not belong to this user.")

        existing = connection.execute("""
            SELECT incident_id FROM incidents
            WHERE user_id = ? AND website_id = ?
              AND status = 'open'
            ORDER BY id DESC LIMIT 1
        """, (user_id, website_id)).fetchone()

        if existing:
            connection.execute("""
                UPDATE incidents
                SET last_seen_at = ?, reasons = ?,
                    health_status = 'unhealthy',
                    website_status_code = ?,
                    website_response_time_ms = ?,
                    website_url = ?
                WHERE incident_id = ?
                  AND user_id = ? AND website_id = ?
            """, (
                now, reason, status_code, response_time_ms,
                url, existing["incident_id"], user_id, website_id
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
                health_status, status, last_seen_at, severity,
                predicted_root_cause, confidence_percent,
                website_status_code, website_response_time_ms,
                website_url, user_id, website_id
            )
            VALUES (?, ?, ?, 1, ?, NULL, NULL, NULL,
                    'unhealthy', 'open', ?, 'High',
                    'website_unavailable', NULL, ?, ?, ?, ?, ?)
        """, (
            incident_id, now, application_name, reason, now,
            status_code, response_time_ms, url, user_id, website_id
        ))

        return incident_id


def resolve_user_website_incidents(user_id, website_id):
    """Resolve open incidents for one user's website only."""
    now = datetime.now().isoformat()

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE incidents
            SET status = 'resolved', resolved_at = ?
            WHERE user_id = ? AND website_id = ?
              AND status = 'open'
        """, (now, user_id, website_id))

        return cursor.rowcount


def get_active_user_websites():
    """Retrieve enabled websites approved for active monitoring."""
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT
                id AS website_id,
                user_id,
                name,
                url,
                monitoring_status,
                200 AS expected_status_code,
                10 AS timeout_seconds
            FROM monitored_websites
            WHERE enabled = 1
              AND monitoring_status IN ('pending', 'active')
            ORDER BY id
        """).fetchall()

        return [dict(row) for row in rows]


def update_user_website_status(user_id, website_id, status):
    """Update monitoring status for a website owned by the specified user."""
    if status not in ("pending", "active", "disabled"):
        raise ValueError("Invalid website monitoring status.")

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE monitored_websites
            SET monitoring_status = ?
            WHERE id = ? AND user_id = ?
        """, (status, website_id, user_id))

        return cursor.rowcount

from datetime import datetime, timedelta, timezone

from database.storage import get_connection


def create_user(email, password_hash, role="user"):
    if role not in ("admin", "user"):
        raise ValueError("Invalid user role.")

    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO users (email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?)
        """, (email.strip().lower(), password_hash, role, now))

        return cursor.lastrowid


def get_user_by_email(email):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT id, email, password_hash, role, is_active, created_at
            FROM users
            WHERE email = ?
        """, (email.strip().lower(),)).fetchone()

        return dict(row) if row else None


def get_user_by_id(user_id):
    with get_connection() as connection:
        row = connection.execute("""
            SELECT id, email, role, is_active, created_at
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        return dict(row) if row else None


def create_session(user_id, token_hash, duration_hours=24):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=duration_hours)

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO sessions (
                user_id, token_hash, expires_at, created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            token_hash,
            expires_at.isoformat(),
            now.isoformat(),
        ))

    return expires_at.isoformat()


def get_session_user(token_hash):
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        row = connection.execute("""
            SELECT users.id, users.email, users.role, users.is_active
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
              AND sessions.expires_at > ?
              AND users.is_active = 1
        """, (token_hash, now)).fetchone()

        return dict(row) if row else None


def delete_session(token_hash):
    with get_connection() as connection:
        connection.execute("""
            DELETE FROM sessions WHERE token_hash = ?
        """, (token_hash,))


def delete_expired_sessions():
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM sessions WHERE expires_at <= ?
        """, (now,))

        return cursor.rowcount


def deactivate_user(user_id):
    """Deactivate an account while preserving its monitoring history."""
    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if user is None:
            return False

        if user["role"] == "admin":
            raise ValueError("Administrator accounts cannot be deactivated here.")

        connection.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?",
            (user_id,),
        )
        connection.execute(
            """
            UPDATE monitored_websites
            SET enabled = 0, monitoring_status = 'disabled'
            WHERE user_id = ?
            """,
            (user_id,),
        )
        connection.execute(
            "DELETE FROM sessions WHERE user_id = ?",
            (user_id,),
        )

    return True

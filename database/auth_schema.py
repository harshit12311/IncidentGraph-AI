from database.storage import get_connection


def initialize_auth_schema():
    """Create authentication and user-owned website tables."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
                    CHECK (role IN ('admin', 'user')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_token_hash
            ON sessions(token_hash)
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS monitored_websites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                ownership_confirmed INTEGER NOT NULL DEFAULT 0,
                monitoring_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        monitoring_status IN ('pending', 'active', 'disabled')
                    ),
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_monitored_websites_user_id
            ON monitored_websites(user_id)
        """)


def initialize_ownership_schema():
    """Add ownership links while preserving legacy monitoring records."""
    with get_connection() as connection:
        migrations = {
            "incidents": [
                ("user_id", "INTEGER REFERENCES users(id)"),
                ("website_id", "INTEGER REFERENCES monitored_websites(id)"),
            ],
            "website_checks": [
                ("user_id", "INTEGER REFERENCES users(id)"),
                ("website_id", "INTEGER REFERENCES monitored_websites(id)"),
            ],
        }

        for table, columns_to_add in migrations.items():
            existing = {
                row["name"]
                for row in connection.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            }

            for column, definition in columns_to_add:
                if column not in existing:
                    connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_user_id
            ON incidents(user_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_website_checks_user_id
            ON website_checks(user_id)
        """)

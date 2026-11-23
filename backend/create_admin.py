import getpass
import re

from backend.auth import hash_password
from database.auth_storage import create_user
from database.storage import get_connection


def main():
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()

    if existing:
        print("An administrator account already exists. Setup cancelled.")
        return

    email = input("Administrator email: ").strip().lower()

    if not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
        email,
    ):
        print("Invalid email address.")
        return

    password = getpass.getpass("Administrator password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")

    if password != confirmation:
        print("Passwords do not match.")
        return

    try:
        password_hash = hash_password(password)
        user_id = create_user(email, password_hash, role="admin")
    except ValueError as exc:
        print(exc)
        return

    print(f"Administrator account created successfully. User ID: {user_id}")


if __name__ == "__main__":
    main()

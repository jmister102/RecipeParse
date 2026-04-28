#!/usr/bin/env python3
"""Change a user's password. Run from the project root with the venv active."""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_conn
from app.auth import hash_password


def main():
    parser = argparse.ArgumentParser(description="Change a user's password")
    parser.add_argument('--username', required=True, help='Username to update')
    args = parser.parse_args()

    conn = get_conn()
    user = conn.execute(
        'SELECT id, username FROM users WHERE username = ?', (args.username,)
    ).fetchone()

    if not user:
        print(f"Error: user '{args.username}' not found.")
        conn.close()
        sys.exit(1)

    print(f"Changing password for user: {user['username']}")
    password = getpass.getpass('New password: ')
    confirm = getpass.getpass('Confirm password: ')

    if password != confirm:
        print('Error: passwords do not match.')
        conn.close()
        sys.exit(1)

    if len(password) < 8:
        print('Error: password must be at least 8 characters.')
        conn.close()
        sys.exit(1)

    conn.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (hash_password(password), user['id'])
    )
    conn.commit()
    conn.close()
    print(f"Password updated for '{user['username']}'.")


if __name__ == '__main__':
    main()

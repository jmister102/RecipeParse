#!/usr/bin/env python3
"""
One-time script: creates the admin user account and assigns all existing
unowned recipes to that account.

Usage:
    python scripts/create_admin.py --username josh --email josh.magerman@gmail.com
"""
import sys
import os
import argparse
import getpass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import init_db, get_conn
from app.auth import hash_password


def main():
    parser = argparse.ArgumentParser(description='Create admin account and claim existing recipes')
    parser.add_argument('--username', required=True)
    parser.add_argument('--email', required=True)
    args = parser.parse_args()

    password = getpass.getpass(f'Password for {args.username}: ')
    confirm = getpass.getpass('Confirm password: ')
    if password != confirm:
        print('Passwords do not match.')
        sys.exit(1)
    if len(password) < 8:
        print('Password must be at least 8 characters.')
        sys.exit(1)

    init_db()
    conn = get_conn()

    existing = conn.execute('SELECT id FROM users WHERE username = ?', (args.username,)).fetchone()
    if existing:
        print(f'User "{args.username}" already exists (id={existing["id"]}).')
        unclaimed = conn.execute('SELECT COUNT(*) as n FROM recipes WHERE user_id IS NULL').fetchone()['n']
        if unclaimed > 0:
            conn.execute('UPDATE recipes SET user_id = ? WHERE user_id IS NULL', (existing['id'],))
            conn.commit()
            print(f'Assigned {unclaimed} unowned recipes to {args.username}.')
        conn.close()
        return

    conn.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
        (args.username, args.email.lower(), hash_password(password))
    )
    conn.commit()
    user = conn.execute('SELECT id FROM users WHERE username = ?', (args.username,)).fetchone()

    unclaimed = conn.execute('SELECT COUNT(*) as n FROM recipes WHERE user_id IS NULL').fetchone()['n']
    conn.execute('UPDATE recipes SET user_id = ? WHERE user_id IS NULL', (user['id'],))
    conn.commit()

    total = conn.execute('SELECT COUNT(*) as n FROM recipes WHERE user_id = ?', (user['id'],)).fetchone()['n']
    conn.close()

    print(f'Created user "{args.username}" (id={user["id"]})')
    print(f'Assigned {unclaimed} existing recipes to this account ({total} total)')

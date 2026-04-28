#!/usr/bin/env python3
import sys
import bcrypt

sys.path.insert(0, '.')
from app.database import init_db, get_conn

init_db()

username = input('Username: ')
email = input('Email: ')
password = input('Password: ')

if len(password) < 8:
    print('Password must be at least 8 characters.')
    sys.exit(1)

conn = get_conn()
existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
if existing:
    print(f'User "{username}" already exists.')
    conn.close()
    sys.exit(1)

pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
conn.execute(
    'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
    (username, email.lower(), pw_hash)
)
conn.commit()
user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
print(f'User "{username}" created (id={user["id"]}).')
conn.close()

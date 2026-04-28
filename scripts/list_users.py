#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_conn

conn = get_conn()
rows = conn.execute('''
    SELECT u.id, u.username, u.email, u.created_at,
           COUNT(r.id) as recipe_count
    FROM users u
    LEFT JOIN recipes r ON r.user_id = u.id
    GROUP BY u.id
    ORDER BY recipe_count DESC
''').fetchall()
conn.close()

if not rows:
    print('No users found.')
    sys.exit(0)

print(f'{"ID":<5} {"Username":<20} {"Email":<30} {"Recipes":>7}  {"Joined"}')
print('─' * 80)
for r in rows:
    print(f'{r["id"]:<5} {r["username"]:<20} {r["email"]:<30} {r["recipe_count"]:>7}  {r["created_at"][:10]}')
print('─' * 80)
print(f'{"Total users:":<55} {len(rows):>7}')

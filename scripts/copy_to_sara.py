"""Copy Josh's last 20 recipes into Sara's account, skipping any she already has."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_conn, init_db

print("Running migrations...")
init_db()

conn = get_conn()

josh  = conn.execute("SELECT id FROM users WHERE LOWER(username) = 'josh'").fetchone()
sara  = conn.execute("SELECT id FROM users WHERE LOWER(username) = 'sara'").fetchone()

if not josh:
    sys.exit("User 'josh' not found — check the username in the database.")
if not sara:
    sys.exit("User 'sara' not found — check the username in the database.")

recipes = conn.execute(
    "SELECT * FROM recipes WHERE user_id = ? ORDER BY date_added DESC LIMIT 20",
    (josh['id'],)
).fetchall()

copied = skipped = 0
for r in recipes:
    exists = conn.execute(
        "SELECT id FROM recipes WHERE url = ? AND user_id = ?",
        (r['url'], sara['id'])
    ).fetchone()
    if exists:
        print(f"  skip (already has): {r['title']}")
        skipped += 1
        continue
    conn.execute(
        """INSERT INTO recipes
           (url, title, image_url, source_site, category, ingredients, instructions,
            description, cook_time, yields, scrape_status, scrape_error, source_file, user_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (r['url'], r['title'], r['image_url'], r['source_site'], r['category'],
         r['ingredients'], r['instructions'], r['description'], r['cook_time'],
         r['yields'], r['scrape_status'], r['scrape_error'], r['source_file'],
         sara['id'])
    )
    print(f"  copied: {r['title']}")
    copied += 1

conn.commit()
conn.close()
print(f"\nDone — {copied} copied, {skipped} skipped.")

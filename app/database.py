import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'recipes.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now')),
            is_active     INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS recipes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            url           TEXT NOT NULL,
            title         TEXT,
            image_url     TEXT,
            source_site   TEXT,
            category      TEXT,
            ingredients   TEXT,
            instructions  TEXT,
            description   TEXT,
            cook_time     TEXT,
            yields        TEXT,
            scrape_status TEXT DEFAULT 'pending',
            scrape_error  TEXT,
            date_added    TEXT DEFAULT (datetime('now')),
            source_file   TEXT,
            user_id       INTEGER REFERENCES users(id)
        );
    """)

    # Idempotent column migrations
    cols = [row[1] for row in conn.execute('PRAGMA table_info(recipes)').fetchall()]
    if 'user_id' not in cols:
        conn.execute('ALTER TABLE recipes ADD COLUMN user_id INTEGER REFERENCES users(id)')
    if 'notes' not in cols:
        conn.execute('ALTER TABLE recipes ADD COLUMN notes TEXT')
    if 'starred' not in cols:
        conn.execute('ALTER TABLE recipes ADD COLUMN starred INTEGER DEFAULT 0')
    conn.commit()
    conn.close()

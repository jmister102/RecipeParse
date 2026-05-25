import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'recipes.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
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

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sent_recipes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id   INTEGER NOT NULL REFERENCES recipes(id),
            from_user   INTEGER NOT NULL REFERENCES users(id),
            to_user     INTEGER NOT NULL REFERENCES users(id),
            sent_at     TEXT DEFAULT (datetime('now'))
        );
    """)

    # Migrate from globally-unique url to per-user unique (url, user_id).
    # The original single-user schema had url UNIQUE; that blocks sharing.
    existing_indexes = {row['name'] for row in conn.execute('PRAGMA index_list(recipes)').fetchall()}
    if 'recipes_url_user' not in existing_indexes:
        conn.executescript("""
            CREATE TABLE recipes_new (
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
                user_id       INTEGER REFERENCES users(id),
                notes         TEXT,
                starred       INTEGER DEFAULT 0
            );
            INSERT INTO recipes_new
                SELECT id, url, title, image_url, source_site, category,
                       ingredients, instructions, description, cook_time, yields,
                       scrape_status, scrape_error, date_added, source_file,
                       user_id, notes, starred
                FROM recipes;
            DROP TABLE recipes;
            ALTER TABLE recipes_new RENAME TO recipes;
            CREATE UNIQUE INDEX recipes_url_user ON recipes(url, user_id);
        """)

    conn.commit()
    conn.close()

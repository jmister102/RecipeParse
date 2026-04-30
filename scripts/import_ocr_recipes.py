#!/usr/bin/env python3
"""
Import OCR-extracted recipes from Sara's Recipe Book into RecipeParse.

Creates a new user and imports all recipes from recipes.js.
Run from the project root or anywhere — paths are resolved automatically.

Usage:
    python3 scripts/import_ocr_recipes.py \\
        --username sara \\
        --email sara@example.com \\
        --password 'yourpassword'

    # Custom source path:
    python3 scripts/import_ocr_recipes.py \\
        --source /path/to/recipe_site \\
        --username sara --email sara@example.com --password 'yourpassword'

    # Skip copying images (DB only):
    python3 scripts/import_ocr_recipes.py \\
        --username sara --email sara@example.com --password 'yourpassword' \\
        --skip-images

On the droplet, first SCP the source data:
    scp '/mnt/c/Users/joshm/Downloads/Recipes/recipe_site/recipes.js' recipeparse:~/recipe_site/
    scp -r '/mnt/c/Users/joshm/Downloads/Recipes/recipe_site/images' recipeparse:~/recipe_site/
Then run this script with --source ~/recipe_site
"""

import argparse
import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import bcrypt

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'data' / 'recipes.db'
STATIC_IMPORTED = PROJECT_ROOT / 'static' / 'imported'

DEFAULT_SOURCE = Path('/mnt/c/Users/joshm/Downloads/Recipes/recipe_site')

CATEGORY_MAP = {
    'side-dish': 'Side Dish',
    'entree':    'Entrée',
    'appetizer': 'Appetizer',
    'dessert':   'Dessert',
    'beverage':  'Beverage',
    'snack':     'Snack',
    'non-food':  'Non-Food',
}


# ── Helpers ────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def load_recipes(source_dir: Path) -> list:
    js_file = source_dir / 'recipes.js'
    content = js_file.read_text(encoding='utf-8')
    # Strip JS wrapper: const RECIPES_DATA = [...];
    content = re.sub(r'^const\s+\w+\s*=\s*', '', content.strip())
    content = content.rstrip(';').strip()
    return json.loads(content)


def parse_markdown(text: str):
    """Return (ingredients, instructions) lists from OCR markdown text."""
    ingredients: list[str] = []
    instructions: list[str] = []
    section = None

    for line in text.split('\n'):
        s = line.strip()

        if re.match(r'^#{1,3}\s', s):
            header = re.sub(r'^#+\s*', '', s).lower()
            if 'ingredient' in header:
                section = 'ingredients'
            elif any(kw in header for kw in ['direction', 'instruction', 'step', 'method', 'preparation']):
                section = 'instructions'
            else:
                section = None
            continue

        if not s or s == '---':
            continue

        if section == 'ingredients':
            item = re.sub(r'^[-*•]\s*', '', s)
            if item and not item.startswith('#'):
                ingredients.append(item)

        elif section == 'instructions':
            if s.startswith('>') or s.startswith('**Note'):
                continue
            item = re.sub(r'^\d+[\.\)]\s*', '', s)
            item = re.sub(r'^\*\*(.+)\*\*$', r'\1', item)
            if item and not item.startswith('*'):
                instructions.append(item)

    return ingredients, instructions


def extract_description(text: str) -> str | None:
    """Pull any italicised intro lines before the first section header."""
    parts = []
    for line in text.split('\n'):
        s = line.strip()
        if not s:
            continue
        if s.startswith('#') or s == '---':
            break
        if s.startswith('*') and s.endswith('*') and not s.startswith('**'):
            parts.append(s.strip('*').strip())
        else:
            break
    return ' '.join(parts) if parts else None


def parse_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, '%b %d, %Y').strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── Core steps ─────────────────────────────────────────────────────────────

def create_user(conn: sqlite3.Connection, username: str, email: str, password: str) -> int:
    existing = conn.execute(
        'SELECT id FROM users WHERE username = ? OR email = ?', (username, email)
    ).fetchone()
    if existing:
        print(f'  User "{username}" already exists (id={existing[0]}) — using existing account.')
        return existing[0]

    conn.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
        (username, email, hash_password(password)),
    )
    conn.commit()
    user_id = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()[0]
    print(f'  Created user "{username}" (id={user_id})')
    return user_id


def import_recipes(source_dir: Path, user_id: int, skip_images: bool) -> None:
    recipes = load_recipes(source_dir)
    print(f'  Found {len(recipes)} recipes in recipes.js')

    if not skip_images:
        STATIC_IMPORTED.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    imported = skipped = errors = 0

    for r in recipes:
        rid    = r['id']
        url_key = f'ocr:{rid}'

        if conn.execute('SELECT id FROM recipes WHERE url = ? AND user_id = ?', (url_key, user_id)).fetchone():
            skipped += 1
            continue

        try:
            ingredients, instructions = parse_markdown(r.get('text', ''))
            description = extract_description(r.get('text', ''))
            category    = CATEGORY_MAP.get(r.get('category', '')) or r.get('category', '').replace('-', ' ').title() or None
            date_added  = parse_date(r.get('date', ''))
            status      = 'ok' if r.get('complete') else 'fallback'

            image_url = None
            if not skip_images:
                images = r.get('images', [])
                if images:
                    src = source_dir / images[0]
                    if src.exists():
                        suffix = src.suffix or '.jpg'
                        dest   = STATIC_IMPORTED / f'{rid}{suffix}'
                        shutil.copy2(src, dest)
                        image_url = f'/static/imported/{rid}{suffix}'

            conn.execute(
                '''INSERT INTO recipes
                   (url, title, image_url, source_site, category,
                    ingredients, instructions, description,
                    scrape_status, date_added, source_file, user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    url_key,
                    r.get('title', 'Untitled'),
                    image_url,
                    "Sara's Recipe Book",
                    category,
                    json.dumps(ingredients),
                    json.dumps(instructions),
                    description,
                    status,
                    date_added,
                    'ocr_import',
                    user_id,
                ),
            )
            imported += 1

        except Exception as exc:
            print(f'  ERROR importing {rid}: {exc}')
            errors += 1

    conn.commit()
    conn.close()

    complete   = sum(1 for r in recipes if r.get('complete'))
    incomplete = len(recipes) - complete
    print(f'  Imported : {imported}')
    print(f'  Skipped  : {skipped} (already in DB)')
    print(f'  Errors   : {errors}')
    print(f'  Complete recipes: {complete} | Incomplete (missing OCR data): {incomplete}')


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description='Import Sara\'s OCR recipes into RecipeParse')
    p.add_argument('--source',      default=str(DEFAULT_SOURCE), help='Path to recipe_site directory')
    p.add_argument('--username',    required=True)
    p.add_argument('--email',       required=True)
    p.add_argument('--password',    required=True)
    p.add_argument('--skip-images', action='store_true', help="Don't copy images (DB only)")
    args = p.parse_args()

    source = Path(args.source)
    if not source.exists():
        sys.exit(f'ERROR: source directory not found: {source}')
    if not (source / 'recipes.js').exists():
        sys.exit(f'ERROR: recipes.js not found in {source}')

    print(f'Database : {DB_PATH}')
    print(f'Source   : {source}')
    print(f'Images   : {"skipped" if args.skip_images else str(STATIC_IMPORTED)}')

    print('\n[1/2] User...')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    user_id = create_user(conn, args.username, args.email, args.password)
    conn.close()

    print('\n[2/2] Recipes...')
    import_recipes(source, user_id, skip_images=args.skip_images)

    print('\nDone. Restart the server if running: sudo systemctl restart recipeparse')


if __name__ == '__main__':
    main()

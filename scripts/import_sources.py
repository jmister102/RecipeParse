#!/usr/bin/env python3
"""
One-time import script. Parses notes.json and recipe_bookmarks.html,
scrapes all URLs, and populates data/recipes.db.
Re-running is safe — already-imported URLs are skipped.
Use --force to re-scrape failed entries.
"""
import sys
import os
import json
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import init_db, get_conn
from app.scraper import scrape_url, SKIP_DOMAINS

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
NOTES_PATH = os.path.join(BASE_DIR, 'notes.json')
BOOKMARKS_PATH = os.path.join(BASE_DIR, 'recipe_bookmarks.html')
FAILED_PATH = os.path.join(BASE_DIR, 'data', 'failed_urls.txt')


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_notes_json():
    """Return list of dicts: url, title, image_url, description."""
    with open(NOTES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    for msg in data.get('messages', []):
        annotations = msg.get('annotations', [])
        if not annotations:
            continue
        meta = annotations[0].get('url_metadata', {})
        if not meta:
            continue
        url_obj = meta.get('url', {})
        url = url_obj.get('private_do_not_access_or_else_safe_url_wrapped_value', '')
        if not url:
            url = msg.get('text', '').strip().split()[0] if msg.get('text', '').strip().startswith('http') else ''
        if not url:
            continue
        results.append({
            'url': url,
            'title': meta.get('title', '') or '',
            'image_url': meta.get('image_url', '') or '',
            'description': meta.get('snippet', '') or '',
            'source_file': 'notes',
            'category': None,
        })
    return results


class _BookmarkHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.folder_stack = []   # list of [name, dl_depth_for_this_folder]
        self.dl_depth = 0
        self.in_h3 = False
        self.pending_folder = ''
        self.in_a = False
        self.current_href = ''
        self.current_title = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        if tag == 'dl':
            self.dl_depth += 1
        elif tag == 'h3':
            self.in_h3 = True
            self.pending_folder = ''
        elif tag == 'a':
            self.in_a = True
            self.current_href = attrs.get('href', '')
            self.current_title = ''

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'dl':
            # pop folders whose depth matches the DL we're closing
            while self.folder_stack and self.folder_stack[-1][1] >= self.dl_depth:
                self.folder_stack.pop()
            self.dl_depth -= 1
        elif tag == 'h3':
            self.in_h3 = False
            name = self.pending_folder.strip()
            # this folder's DL will be at depth dl_depth + 1
            self.folder_stack.append([name, self.dl_depth + 1])
        elif tag == 'a':
            if self.in_a and self.current_href:
                # find innermost non-root folder
                category = None
                for name, depth in reversed(self.folder_stack):
                    if name and name.lower() not in ('bookmarks', 'recipes'):
                        category = name
                        break
                if category is None and self.folder_stack:
                    # top-level inside Recipes → General
                    for name, depth in reversed(self.folder_stack):
                        if name.lower() == 'recipes':
                            category = 'General'
                            break
                self.results.append({
                    'url': self.current_href,
                    'title': self.current_title.strip(),
                    'category': category,
                    'source_file': 'bookmarks',
                    'image_url': '',
                    'description': '',
                })
            self.in_a = False
            self.current_href = ''

    def handle_data(self, data):
        if self.in_h3:
            self.pending_folder += data
        elif self.in_a:
            self.current_title += data


def parse_bookmarks_html():
    with open(BOOKMARKS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    parser = _BookmarkHTMLParser()
    parser.feed(content)
    return parser.results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_skippable(url):
    domain = urlparse(url).netloc.lstrip('www.')
    for skip in SKIP_DOMAINS:
        if domain.endswith(skip):
            return True
    return False


def _source_site(url):
    return urlparse(url).netloc.lstrip('www.')


def _deduplicate(notes, bookmarks):
    """Merge both lists, deduplicating by URL. notes metadata takes priority for image."""
    seen = {}  # url → dict

    def _norm(url):
        return url.rstrip('/').split('#')[0].split('?')[0]

    for entry in notes:
        key = _norm(entry['url'])
        seen[key] = entry.copy()

    for entry in bookmarks:
        key = _norm(entry['url'])
        if key in seen:
            # merge: keep notes image/desc, add category from bookmarks
            if entry.get('category'):
                seen[key]['category'] = entry['category']
        else:
            seen[key] = entry.copy()

    return list(seen.values())


# ── Main ──────────────────────────────────────────────────────────────────────

def process_one(entry, force=False):
    """Scrape one entry, return (entry, scrape_result)."""
    url = entry['url']
    conn = get_conn()

    existing = conn.execute('SELECT id, scrape_status FROM recipes WHERE url = ?', (url,)).fetchone()

    if existing and not force:
        conn.close()
        return entry, None  # already done

    if existing and force and existing['scrape_status'] != 'failed':
        conn.close()
        return entry, None  # only re-scrape failed ones with --force

    # Pre-insert / update seed metadata so we have title+image even if scrape fails
    if not existing:
        conn.execute(
            '''INSERT OR IGNORE INTO recipes
               (url, title, image_url, source_site, category, description, scrape_status, source_file)
               VALUES (?,?,?,?,?,?,'pending',?)''',
            (url, entry.get('title') or '', entry.get('image_url') or '',
             _source_site(url), entry.get('category'),
             entry.get('description') or '', entry['source_file'])
        )
        conn.commit()
    conn.close()

    # Skip non-recipe domains quickly
    if _is_skippable(url):
        conn = get_conn()
        conn.execute(
            "UPDATE recipes SET scrape_status='skipped', scrape_error=? WHERE url=?",
            ('Non-recipe domain', url)
        )
        conn.commit()
        conn.close()
        return entry, {'scrape_status': 'skipped'}

    data = scrape_url(url)
    final_url = data['url']

    conn = get_conn()
    # If the URL changed (AMP resolved / redirect followed), update or deduplicate
    if final_url != url:
        existing_final = conn.execute('SELECT id FROM recipes WHERE url=?', (final_url,)).fetchone()
        if existing_final:
            # Another entry already has this final URL — delete the duplicate stub
            conn.execute('DELETE FROM recipes WHERE url=?', (url,))
            conn.commit()
            conn.close()
            return entry, data
        conn.execute('UPDATE recipes SET url=? WHERE url=?', (final_url, url))

    conn.execute(
        "UPDATE recipes SET"
        " title=COALESCE(NULLIF(?,''), title),"
        " image_url=COALESCE(NULLIF(?,''), image_url),"
        " source_site=?,"
        " ingredients=?, instructions=?,"
        " description=COALESCE(NULLIF(?,''), description),"
        " cook_time=?, yields=?,"
        " scrape_status=?, scrape_error=?"
        " WHERE url=?",
        (
            data['title'] or '', data['image_url'] or '',
            _source_site(final_url),
            json.dumps(data['ingredients']), json.dumps(data['instructions']),
            data['description'] or '', data['cook_time'], data['yields'],
            data['scrape_status'], data['scrape_error'],
            final_url,
        )
    )
    conn.commit()
    conn.close()
    return entry, data


def main():
    parser = argparse.ArgumentParser(description='Import recipes from source files')
    parser.add_argument('--force', action='store_true', help='Re-scrape failed entries')
    args = parser.parse_args()

    print('Initializing database...')
    init_db()

    print('Parsing source files...')
    notes = parse_notes_json()
    bookmarks = parse_bookmarks_html()
    print(f'  notes.json:            {len(notes)} URLs')
    print(f'  recipe_bookmarks.html: {len(bookmarks)} URLs')

    all_entries = _deduplicate(notes, bookmarks)
    print(f'  After deduplication:   {len(all_entries)} unique URLs')
    print()

    counts = {'ok': 0, 'fallback': 0, 'failed': 0, 'skipped': 0, 'skipped_existing': 0}
    failed_urls = []

    print(f'Scraping {len(all_entries)} URLs (5 workers, this may take a few minutes)...')
    print()

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(process_one, e, args.force): e for e in all_entries}
        done = 0
        for future in as_completed(futures):
            entry, result = future.result()
            done += 1
            if result is None:
                counts['skipped_existing'] += 1
                status = 'exists'
            else:
                status = result.get('scrape_status', 'failed')
                counts[status] = counts.get(status, 0) + 1
                if status == 'failed':
                    failed_urls.append(entry['url'])

            title = (entry.get('title') or entry['url'])[:55]
            print(f'  [{done:3d}/{len(all_entries)}] {status:8s}  {title}')

    print()
    print('─' * 60)
    print('Import complete')
    print(f'  ok (recipe-scrapers):  {counts.get("ok", 0)}')
    print(f'  fallback (wild/BS4):   {counts.get("fallback", 0)}')
    print(f'  failed:                {counts.get("failed", 0)}')
    print(f'  skipped (non-recipe):  {counts.get("skipped", 0)}')
    print(f'  already in DB:         {counts.get("skipped_existing", 0)}')
    print()

    if failed_urls:
        with open(FAILED_PATH, 'w') as f:
            f.write('\n'.join(failed_urls) + '\n')
        print(f'Failed URLs written to data/failed_urls.txt')
    print('Done! Run: python app.py   then open http://localhost:8000')


if __name__ == '__main__':
    main()

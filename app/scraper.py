import json
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

SKIP_DOMAINS = {
    'scholastic.com', 'pinterest.com', 'qvc.com',
    'airbnb.com', 'collegian.psu.edu',
}

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def _domain(url):
    return urlparse(url).netloc.lstrip('www.')


def _resolve_amp(url):
    m = re.match(r'https?://(?:www\.)?google\.com/amp/s/(.+)', url)
    if m:
        canonical = 'https://' + m.group(1)
        if canonical.endswith('.amp'):
            canonical = canonical[:-4]
        return canonical
    return url


def _follow_redirect(url, timeout=10):
    try:
        r = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=timeout)
        return r.url
    except Exception:
        try:
            r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=timeout, stream=True)
            return r.url
        except Exception:
            return url


def _fetch_html(url, timeout=15):
    """Fetch page HTML. Returns (final_url, html_text) or raises."""
    r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=timeout)
    # Many sites return 403 with HTML that still contains JSON-LD — try anyway
    return r.url, r.text


def _parse_jsonld(html):
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
            items = data if isinstance(data, list) else data.get('@graph', [data]) if isinstance(data, dict) else [data]
            for item in items:
                if isinstance(item, dict) and item.get('@type') in ('Recipe', ['Recipe']):
                    return item
        except Exception:
            continue
    return None


def _extract_from_jsonld(data):
    def text_list(val):
        if not val:
            return []
        if isinstance(val, str):
            return [val.strip()]
        if isinstance(val, list):
            out = []
            for v in val:
                if isinstance(v, str):
                    out.append(v.strip())
                elif isinstance(v, dict):
                    out.append((v.get('text') or v.get('name') or '').strip())
            return [x for x in out if x]
        return []

    def first_image(val):
        if not val:
            return None
        if isinstance(val, str):
            return val
        if isinstance(val, list) and val:
            v = val[0]
            return v if isinstance(v, str) else v.get('url', '')
        if isinstance(val, dict):
            return val.get('url', '')
        return None

    def duration_str(val):
        if not val:
            return None
        m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', str(val))
        if m:
            parts = []
            if m.group(1):
                parts.append(f'{m.group(1)} hr')
            if m.group(2):
                parts.append(f'{m.group(2)} min')
            return ' '.join(parts) if parts else None
        return str(val)

    cook = duration_str(data.get('cookTime') or data.get('totalTime'))
    return {
        'title': (data.get('name') or '').strip(),
        'image_url': first_image(data.get('image')),
        'ingredients': text_list(data.get('recipeIngredient')),
        'instructions': text_list(data.get('recipeInstructions')),
        'description': (data.get('description') or '').strip(),
        'cook_time': cook,
        'yields': str(data.get('recipeYield') or ''),
    }


def scrape_url(url, timeout=15):
    """
    Scrape a recipe URL. Returns dict with keys:
    url, title, image_url, ingredients (list), instructions (list),
    description, cook_time, yields, scrape_status, scrape_error
    """
    result = {
        'url': url,
        'title': None, 'image_url': None,
        'ingredients': [], 'instructions': [],
        'description': None, 'cook_time': None, 'yields': None,
        'scrape_status': 'failed', 'scrape_error': None,
    }

    url = _resolve_amp(url)

    domain = _domain(url)
    for skip in SKIP_DOMAINS:
        if domain.endswith(skip):
            result.update(url=url, scrape_status='skipped', scrape_error=f'Non-recipe domain: {domain}')
            return result

    if 'share.google' in url:
        resolved = _follow_redirect(url, timeout=timeout)
        if resolved != url:
            url = resolved
            domain = _domain(url)
            for skip in SKIP_DOMAINS:
                if domain.endswith(skip):
                    result.update(url=url, scrape_status='skipped', scrape_error=f'Non-recipe domain after redirect: {domain}')
                    return result

    result['url'] = url

    # Fetch HTML once; reuse for all scrape attempts
    try:
        final_url, html = _fetch_html(url, timeout=timeout)
        result['url'] = final_url
    except Exception as e:
        result['scrape_error'] = f'Fetch failed: {e}'
        return result

    # Step 1: recipe-scrapers with pre-fetched HTML
    try:
        from recipe_scrapers import scrape_html
        s = scrape_html(html, org_url=result['url'], wild_mode=False)
        ingr = s.ingredients() if callable(s.ingredients) else []
        instr_raw = s.instructions() if callable(s.instructions) else ''
        instr = [l.strip() for l in instr_raw.split('\n') if l.strip()] if isinstance(instr_raw, str) else list(instr_raw)
        title = s.title() if callable(s.title) else ''
        if title or ingr or instr:
            try:
                image = s.image() if callable(s.image) else None
            except Exception:
                image = None
            try:
                cook = s.total_time()
                cook = f'{cook} min' if cook else None
            except Exception:
                cook = None
            try:
                yld = str(s.yields()) if callable(s.yields) else None
            except Exception:
                yld = None
            try:
                desc = s.description() if callable(s.description) else None
            except Exception:
                desc = None
            result.update(title=title, image_url=image, ingredients=ingr, instructions=instr,
                          description=desc, cook_time=cook, yields=yld, scrape_status='ok')
            return result
    except Exception:
        pass

    # Step 2: recipe-scrapers wild mode
    try:
        from recipe_scrapers import scrape_html
        s = scrape_html(html, org_url=result['url'], wild_mode=True)
        ingr = s.ingredients() if callable(s.ingredients) else []
        instr_raw = s.instructions() if callable(s.instructions) else ''
        instr = [l.strip() for l in instr_raw.split('\n') if l.strip()] if isinstance(instr_raw, str) else list(instr_raw)
        title = s.title() if callable(s.title) else ''
        if title or ingr or instr:
            try:
                image = s.image() if callable(s.image) else None
            except Exception:
                image = None
            try:
                cook = s.total_time()
                cook = f'{cook} min' if cook else None
            except Exception:
                cook = None
            try:
                yld = str(s.yields()) if callable(s.yields) else None
            except Exception:
                yld = None
            try:
                desc = s.description() if callable(s.description) else None
            except Exception:
                desc = None
            result.update(title=title, image_url=image, ingredients=ingr, instructions=instr,
                          description=desc, cook_time=cook, yields=yld, scrape_status='fallback')
            return result
    except Exception:
        pass

    # Step 3: manual JSON-LD parse from already-fetched HTML
    try:
        jsonld = _parse_jsonld(html)
        if jsonld:
            extracted = _extract_from_jsonld(jsonld)
            if extracted.get('title') or extracted.get('ingredients') or extracted.get('instructions'):
                result.update(extracted)
                result['scrape_status'] = 'fallback'
                return result
        result['scrape_error'] = 'No recipe schema found'
    except Exception as e:
        result['scrape_error'] = str(e)

    return result

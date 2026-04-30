import json
import uuid
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional

from .database import get_conn
from .scraper import scrape_url
from .auth import get_current_user

router = APIRouter()


def _row_to_card(row):
    return {
        'id': row['id'],
        'url': row['url'],
        'title': row['title'],
        'image_url': row['image_url'],
        'source_site': row['source_site'],
        'category': row['category'],
        'scrape_status': row['scrape_status'],
        'description': row['description'],
        'cook_time': row['cook_time'],
        'yields': row['yields'],
        'date_added': row['date_added'],
        'starred': bool(row['starred']),
    }


def _row_to_detail(row):
    card = _row_to_card(row)
    card['ingredients'] = json.loads(row['ingredients'] or '[]')
    card['instructions'] = json.loads(row['instructions'] or '[]')
    card['notes'] = row['notes'] or ''
    return card


@router.get('/recipes')
def list_recipes(
    q: str = '',
    category: str = '',
    current_user: dict = Depends(get_current_user),
):
    conn = get_conn()
    query = 'SELECT * FROM recipes WHERE user_id = ?'
    params = [current_user['id']]
    if q:
        query += ' AND (title LIKE ? OR description LIKE ? OR ingredients LIKE ?)'
        like = f'%{q}%'
        params += [like, like, like]
    if category:
        query += ' AND category = ?'
        params.append(category)
    query += ' ORDER BY title COLLATE NOCASE'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_card(r) for r in rows]


@router.get('/recipes/{recipe_id}')
def get_recipe(recipe_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    row = conn.execute(
        'SELECT * FROM recipes WHERE id = ? AND user_id = ?',
        (recipe_id, current_user['id'])
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail='Recipe not found')
    return _row_to_detail(row)


class AddRecipeRequest(BaseModel):
    url: str


@router.post('/recipes')
def add_recipe(req: AddRecipeRequest, current_user: dict = Depends(get_current_user)):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail='URL is required')

    conn = get_conn()
    existing = conn.execute(
        'SELECT id FROM recipes WHERE url = ? AND user_id = ?',
        (url, current_user['id'])
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail='Recipe already in your collection')
    conn.close()

    data = scrape_url(url)
    source_site = urlparse(data['url']).netloc.lstrip('www.')

    conn = get_conn()
    existing = conn.execute(
        'SELECT id FROM recipes WHERE url = ? AND user_id = ?',
        (data['url'], current_user['id'])
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail='Recipe already in your collection')

    conn.execute(
        '''INSERT INTO recipes
           (url, title, image_url, source_site, category, ingredients, instructions,
            description, cook_time, yields, scrape_status, scrape_error, source_file, user_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            data['url'], data['title'], data['image_url'], source_site, None,
            json.dumps(data['ingredients']), json.dumps(data['instructions']),
            data['description'], data['cook_time'], data['yields'],
            data['scrape_status'], data['scrape_error'], 'manual',
            current_user['id'],
        )
    )
    conn.commit()
    row = conn.execute(
        'SELECT * FROM recipes WHERE url = ? AND user_id = ?',
        (data['url'], current_user['id'])
    ).fetchone()
    conn.close()
    return _row_to_detail(row)


ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/heic', 'image/heif'}
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post('/recipes/ocr')
async def ocr_recipe(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    from .ocr import extract_recipe_from_image

    content_type = (file.content_type or '').split(';')[0].strip().lower()
    if content_type not in ALLOWED_IMAGE_TYPES and not content_type.startswith('image/'):
        raise HTTPException(status_code=415, detail='Please upload an image file (JPEG, PNG, WebP, etc.)')

    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail='Image too large (max 20 MB)')
    if not image_bytes:
        raise HTTPException(status_code=400, detail='Empty file')

    try:
        data = extract_recipe_from_image(image_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    url = f'ocr:{uuid.uuid4()}'
    conn = get_conn()
    conn.execute(
        '''INSERT INTO recipes
           (url, title, image_url, source_site, category, ingredients, instructions,
            description, cook_time, yields, scrape_status, source_file, user_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            url,
            data.get('title', 'Untitled Recipe'),
            None,
            'Photo OCR',
            data.get('category'),
            json.dumps(data.get('ingredients', [])),
            json.dumps(data.get('instructions', [])),
            data.get('description'),
            data.get('cook_time'),
            data.get('yields'),
            'ok' if (data.get('ingredients') or data.get('instructions')) else 'fallback',
            'ocr',
            current_user['id'],
        ),
    )
    conn.commit()
    row = conn.execute('SELECT * FROM recipes WHERE url = ? AND user_id = ?',
                       (url, current_user['id'])).fetchone()
    conn.close()
    return _row_to_detail(row)


class PatchRecipeRequest(BaseModel):
    notes: Optional[str] = None
    category: Optional[str] = None
    starred: Optional[bool] = None


@router.patch('/recipes/{recipe_id}')
def patch_recipe(recipe_id: int, req: PatchRecipeRequest, current_user: dict = Depends(get_current_user)):
    fields = req.model_fields_set
    if not fields:
        raise HTTPException(status_code=400, detail='No fields to update')
    updates, params = [], []
    if 'notes' in fields:
        updates.append('notes = ?')
        params.append(req.notes.strip() if req.notes else None)
    if 'category' in fields:
        updates.append('category = ?')
        params.append(req.category.strip() if req.category else None)
    if 'starred' in fields:
        updates.append('starred = ?')
        params.append(1 if req.starred else 0)
    params += [recipe_id, current_user['id']]
    conn = get_conn()
    result = conn.execute(
        f'UPDATE recipes SET {", ".join(updates)} WHERE id = ? AND user_id = ?',
        params
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail='Recipe not found')
    return {'ok': True}


class ManualRecipeRequest(BaseModel):
    title: str
    description: str = ''
    image_url: str = ''
    category: str = ''
    cook_time: str = ''
    yields: str = ''
    ingredients: List[str] = []
    instructions: List[str] = []


@router.post('/recipes/manual')
def add_manual_recipe(req: ManualRecipeRequest, current_user: dict = Depends(get_current_user)):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail='Title is required')

    url = f'manual:{uuid.uuid4()}'
    ingredients = [i for i in req.ingredients if i.strip()]
    instructions = [i for i in req.instructions if i.strip()]

    conn = get_conn()
    conn.execute(
        '''INSERT INTO recipes
           (url, title, image_url, source_site, category, ingredients, instructions,
            description, cook_time, yields, scrape_status, source_file, user_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            url, req.title.strip(),
            req.image_url.strip() or None,
            'Manual entry',
            req.category.strip() or None,
            json.dumps(ingredients), json.dumps(instructions),
            req.description.strip() or None,
            req.cook_time.strip() or None,
            req.yields.strip() or None,
            'ok', 'manual', current_user['id'],
        )
    )
    conn.commit()
    row = conn.execute(
        'SELECT * FROM recipes WHERE url = ? AND user_id = ?',
        (url, current_user['id'])
    ).fetchone()
    conn.close()
    return _row_to_detail(row)


@router.delete('/recipes/{recipe_id}')
def delete_recipe(recipe_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    result = conn.execute(
        'DELETE FROM recipes WHERE id = ? AND user_id = ?',
        (recipe_id, current_user['id'])
    )
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail='Recipe not found')
    return {'ok': True}


@router.get('/categories')
def list_categories(current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT category FROM recipes WHERE user_id = ? AND category IS NOT NULL AND category != '' ORDER BY category",
        (current_user['id'],)
    ).fetchall()
    conn.close()
    return [r['category'] for r in rows]


@router.get('/stats')
def get_stats(current_user: dict = Depends(get_current_user)):
    conn = get_conn()
    total = conn.execute(
        'SELECT COUNT(*) as n FROM recipes WHERE user_id = ?',
        (current_user['id'],)
    ).fetchone()['n']
    by_status = conn.execute(
        'SELECT scrape_status, COUNT(*) as n FROM recipes WHERE user_id = ? GROUP BY scrape_status',
        (current_user['id'],)
    ).fetchall()
    conn.close()
    return {
        'total': total,
        'by_status': {r['scrape_status']: r['n'] for r in by_status},
    }

import base64
import io
import json
import os
import re

import anthropic
from PIL import Image

# claude-haiku-4-5 is used to keep per-extraction cost low (~$0.001/image).
# Upgrade to claude-sonnet-4-6 here if accuracy needs improvement.
_MODEL = 'claude-haiku-4-5-20251001'
_MAX_DIM = 1568  # Claude's recommended max dimension

_PROMPT = """\
This is a photo or screenshot of a recipe. Extract everything you can see and return \
ONLY a valid JSON object — no markdown fences, no commentary — with these fields:

{
  "title": "Recipe name",
  "description": "Brief intro or personal note if present, otherwise null",
  "category": "best match from: Appetizer, Dessert, Entrée, Side Dish, Beverage, Snack — or null",
  "cook_time": "e.g. '45 mins' or null",
  "yields": "e.g. '4 servings' or null",
  "ingredients": ["ingredient 1", "ingredient 2", ...],
  "instructions": ["Step 1 text", "Step 2 text", ...]
}

Rules:
- ingredients and instructions must be arrays (empty [] if not visible in the image)
- Strip any leading numbers or bullets from instructions — just the step text
- Strip any leading bullets/dashes from ingredients — just the ingredient text
- If this is clearly not a recipe image, return {"error": "Not a recipe"}
"""


def _resize_to_jpeg(image_bytes: bytes) -> bytes:
    """Resize image to fit within _MAX_DIM and convert to JPEG."""
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    img.thumbnail((_MAX_DIM, _MAX_DIM), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def extract_recipe_from_image(image_bytes: bytes) -> dict:
    """
    Send image to Claude vision and return structured recipe data.

    Returns a dict with keys: title, description, category, cook_time,
    yields, ingredients, instructions.

    Raises ValueError for non-recipe images or API errors.
    Raises RuntimeError if ANTHROPIC_API_KEY is not configured.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY is not configured on this server.')

    jpeg_bytes = _resize_to_jpeg(image_bytes)
    b64 = base64.standard_b64encode(jpeg_bytes).decode()

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/jpeg',
                        'data': b64,
                    },
                },
                {'type': 'text', 'text': _PROMPT},
            ],
        }],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if the model added them anyway
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'Could not parse model response as JSON: {exc}') from exc

    if 'error' in data:
        raise ValueError(data['error'])

    # Normalise — ensure arrays exist even if model omitted them
    data.setdefault('ingredients', [])
    data.setdefault('instructions', [])
    data.setdefault('title', 'Untitled Recipe')

    return data

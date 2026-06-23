import io
import os
import uuid

from PIL import Image, ImageOps

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')
_MAX_DIM = 1600  # plenty for a hero image; keeps files small


def save_recipe_image(image_bytes: bytes) -> str:
    """Normalise an uploaded image to JPEG, save it under static/uploads,
    and return its web path (e.g. '/static/uploads/<id>.jpg').

    Raises ValueError if the bytes can't be decoded as an image.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img)  # honour camera orientation
        img = img.convert('RGB')
    except Exception as exc:
        raise ValueError('Could not read image file') from exc

    img.thumbnail((_MAX_DIM, _MAX_DIM), Image.LANCZOS)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f'{uuid.uuid4().hex}.jpg'
    img.save(os.path.join(UPLOAD_DIR, filename), format='JPEG', quality=85)
    return f'/static/uploads/{filename}'


def delete_recipe_image(image_url) -> None:
    """Delete a previously-uploaded local image file. No-op for remote URLs
    or anything not under static/uploads."""
    if not image_url or not str(image_url).startswith('/static/uploads/'):
        return
    path = os.path.join(UPLOAD_DIR, os.path.basename(image_url))
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

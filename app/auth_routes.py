import re
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from .database import get_conn
from .auth import hash_password, verify_password, create_token, get_current_user
from fastapi import Depends

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,30}$')


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post('/register')
@limiter.limit('5/hour')
def register(req: RegisterRequest, request: Request):
    if not USERNAME_RE.match(req.username):
        raise HTTPException(status_code=400, detail='Username must be 3–30 chars, letters/numbers/underscores only')
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail='Password must be at least 8 characters')
    if '@' not in req.email or '.' not in req.email.split('@')[-1]:
        raise HTTPException(status_code=400, detail='Invalid email address')

    conn = get_conn()
    existing = conn.execute(
        'SELECT id FROM users WHERE username = ? OR email = ?',
        (req.username, req.email.lower())
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail='Username or email already taken')

    conn.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
        (req.username, req.email.lower(), hash_password(req.password))
    )
    conn.commit()
    user = conn.execute('SELECT id FROM users WHERE username = ?', (req.username,)).fetchone()
    conn.close()

    token = create_token(user['id'])
    return {'token': token, 'username': req.username}


@router.post('/login')
@limiter.limit('10/15minutes')
def login(req: LoginRequest, request: Request):
    conn = get_conn()
    user = conn.execute(
        'SELECT id, username, password_hash, is_active FROM users WHERE username = ?',
        (req.username,)
    ).fetchone()
    conn.close()

    if not user or not user['is_active'] or not verify_password(req.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Invalid username or password')

    token = create_token(user['id'])
    return {'token': token, 'username': user['username']}


@router.get('/me')
def me(current_user: dict = Depends(get_current_user)):
    return current_user

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.environ.get('RECIPES_SECRET_KEY', '')
ALGORITHM = 'HS256'
TOKEN_EXPIRE_DAYS = 30

if not SECRET_KEY:
    raise RuntimeError('RECIPES_SECRET_KEY environment variable is not set')

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login')


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({'sub': str(user_id), 'exp': expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid or expired token',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload['sub'])
    except Exception:
        raise exc

    from .database import get_conn
    conn = get_conn()
    user = conn.execute(
        'SELECT id, username, email FROM users WHERE id = ? AND is_active = 1',
        (user_id,)
    ).fetchone()
    conn.close()

    if not user:
        raise exc
    return dict(user)

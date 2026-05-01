import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import init_db
from app.routes import router
from app.auth_routes import router as auth_router

BASE_DIR = os.path.dirname(__file__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    yield


application = FastAPI(title='Recipe Books', lifespan=lifespan)
application.state.limiter = limiter
application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

application.include_router(router, prefix='/api')
application.include_router(auth_router, prefix='/api/auth')
application.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'static')), name='static')


@application.get('/')
def index():
    return FileResponse(
        os.path.join(BASE_DIR, 'templates', 'index.html'),
        headers={'Cache-Control': 'no-cache, no-store, must-revalidate'},
    )


@application.get('/sw.js')
def service_worker():
    return FileResponse(
        os.path.join(BASE_DIR, 'static', 'sw.js'),
        media_type='application/javascript',
        headers={'Cache-Control': 'no-cache, no-store, must-revalidate'},
    )


@application.get('/manifest.json')
def manifest():
    return FileResponse(
        os.path.join(BASE_DIR, 'static', 'manifest.json'),
        media_type='application/manifest+json',
    )


if __name__ == '__main__':
    uvicorn.run('server:application', host='127.0.0.1', port=8001)

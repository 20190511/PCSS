from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.db import log_col

from app.core.paths import STATIC_DIR, TEMPLATES_DIR
from app.routes import api_router
from app.routes.author_routes import router as author_router
from app.routes.page_routes import router as page_router
from app.routes.subscription_routes import router as subscription_router
from app.routes.auth_routes import router as auth_router
from app.routes.conf_routes import router as conf_router
from app.routes.search_routes import router as search_router
from app.db.mongo import get_mongo_client

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PCSS API", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://pcss.r-e.kr",
        "https://pcss.r-e.kr",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    await get_mongo_client()

app.include_router(page_router)
app.include_router(api_router, prefix="/api")
app.include_router(conf_router, prefix="/conferences")
app.include_router(author_router, prefix="/author")
app.include_router(subscription_router, prefix="/subscriptions")
app.include_router(auth_router, prefix="/auth")
app.include_router(search_router, prefix="/api/search")
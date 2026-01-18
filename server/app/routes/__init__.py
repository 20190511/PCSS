from fastapi import APIRouter
from .conf_routes import router as conf_router
from .search_routes import router as search_router
from .page_routes import router as page_router
from .log_routes import router as log_router

api_router = APIRouter()    

api_router.include_router(conf_router, prefix="/conf", tags=["conferences"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(log_router, prefix="/logs", tags=["logs"])
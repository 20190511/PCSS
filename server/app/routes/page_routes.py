from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi import Form
from app.core.templates import templates
from app.services.author_service import compute_author_stats_mongo

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("homepage.html", {"request": request})
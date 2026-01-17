from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi import Form
from app.core.templates import templates
from app.services.author_service import compute_author_stats_mongo

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("homepage.html", {"request": request})

@router.post("/author-stats/page", response_class=HTMLResponse)
async def author_stats_page(
    request: Request,
    target_author: str = Form(...),
    url: str = Form(""),               
    include_papers: bool = Form(True),
):
    result = await compute_author_stats_mongo(
        target_author=target_author,
        include_papers=include_papers,
    )

    if not include_papers:
        result.pop("papers", None)

    return templates.TemplateResponse(
        "author_stats.html",
        {
            "request": request,
            "name": target_author,
            "url": url, 
            "stats": result.get("stats", (0, 0, 0, 0)),
            "total": result.get("total", 0),
            "papers": result.get("papers", []),
        },
    )
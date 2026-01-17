from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi import Form
from app.core.templates import templates
from app.services.author_service import compute_author_stats_mongo
from app.db import name_col, req_korean_col
from app.data import name_dict
from app.libs.exceptions import NotFoundException
from datetime import datetime, timezone

router = APIRouter()

@router.post("/stats/page", response_class=HTMLResponse)
async def author_stats_page(
    request: Request,
    target_author: str = Form(...),
    url: str = Form(""),               
    include_papers: bool = Form(True),
    uncertainty: float = Form(0.5),
):
    result = await compute_author_stats_mongo(
        target_author=target_author,
        include_papers=include_papers,
    )

    if not include_papers:
        result.pop("papers", None)
    
    score = name_dict.get(target_author, 0)
    is_korean = score >= uncertainty

    return templates.TemplateResponse(
        "author_stats.html",
        {
            "request": request,
            "name": target_author,
            "url": url, 
            "stats": result.get("stats", (0, 0, 0, 0)),
            "total": result.get("total", 0),
            "papers": result.get("papers", []),
            "is_korean": is_korean,
        },
    )

@router.post("/korean/{param}")
async def add_korean_stat(param: str):
    if param not in name_dict:
        raise NotFoundException("Name not found")

    name_dict[param] = 1

    result = name_col.update_one(
        {"name": param},
        {"$set": {"score": 1, "updated_at": datetime.now(timezone.utc)}},
    )

    if result.matched_count == 0:
        # dict에는 있는데 DB에는 없는 상태 -> 데이터 불일치
        raise NotFoundException("Name not found in DB")

    return {"status": "Updated", "param": param}


@router.delete("/korean/{param}")
async def delete_korean_stat(param: str):
    if param not in name_dict:
        raise NotFoundException("Name not found")

    name_dict[param] = 0

    result = name_col.update_one(
        {"name": param},
        {"$set": {"score": 0, "updated_at": datetime.now(timezone.utc)}},
    )

    if result.matched_count == 0:
        raise NotFoundException("Name not found in DB")

    return {"status": "Deleted", "param": param}


@router.post("/add/korean/{param}")
async def request_add_korean_stat(param: str):
    if param not in name_dict:
        raise NotFoundException("Name not found")

    req_korean_col.update_one(
        {"name": param},
        {"$set": {
            "name": param,
            "score": name_dict[param],
            "type": 1,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"status": "Requested", "param": param}


@router.post("/delete/korean/{param}")
async def request_delete_korean_stat(param: str):
    if param not in name_dict:
        raise NotFoundException("Name not found")

    req_korean_col.update_one(
        {"name": param},
        {"$set": {
            "name": param,
            "score": name_dict[param],
            "type": 0,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"status": "Requested", "param": param}

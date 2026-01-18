from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Form
from app.core.templates import templates
from app.services.author_service import compute_author_stats_mongo
from app.db import name_col, req_korean_col
from app.data import name_dict
from app.libs.exceptions import NotFoundException
from datetime import datetime, timezone
from app.libs.auth import _require_admin_or_redirect


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
        "search/author_stats.html",
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


@router.get("/request/korean")
async def get_korean_requests():
    requests = list(req_korean_col.find({}))
    response = []
    for req in requests:
        response.append({
            "name": req["name"],
            "score": req["score"],
            "type": req["type"],
            "updated_at": req["updated_at"],
        })
    return {"requests": response}


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


@router.post("/cancel/korean/{param}")
async def cancel_korean_request(param: str):
    if param not in name_dict:
        raise NotFoundException("Name not found")

    result = req_korean_col.delete_one({"name": param})

    if result.deleted_count == 0:
        # 취소할 요청이 없을 때
        raise NotFoundException("No pending request to cancel")

    return {"status": "Canceled", "param": param}


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


@router.get("/manage", response_class=HTMLResponse)
async def admin_requests_page(request: Request):
    next_path = request.url.path  # "/author/requests"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)

    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp

    if status_or_resp is None:
        # 로그인은 했는데 admin 아님
        return templates.TemplateResponse(
            "admin/admin_name_requests.html",
            {"request": request, "requests": [], "error": "권한이 없습니다. 관리자 계정으로 로그인하세요."},
            status_code=403,
        )

    reqs = list(req_korean_col.find({}).sort("updated_at", -1))

    items = []
    for r in reqs:
        items.append({
            "name": r.get("name", ""),
            "score": r.get("score", 0),
            "type": r.get("type", None),
            "updated_at": r.get("updated_at", None).isoformat() if r.get("updated_at", None) else "",
        })

    return templates.TemplateResponse(
        "admin/admin_name_requests.html",
        {"request": request, "requests": items, "error": None, "email": email},
    )


def apply_korean_score(param: str, score: int):
    """
    add_korean_stat / delete_korean_stat와 동일한 핵심 로직
    (권장: DB 성공 후 dict 반영)
    """
    if param not in name_dict:
        raise NotFoundException("Name not found")

    result = name_col.update_one(
        {"name": param},
        {"$set": {"score": score, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise NotFoundException("Name not found in DB")

    name_dict[param] = score
    

@router.post("/requests/approve")
async def approve_korean_request(request: Request, name: str = Form(...)):
    next_path = "/author/requests"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)

    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    req_doc = req_korean_col.find_one({"name": name})
    if not req_doc:
        raise NotFoundException("No pending request")

    req_type = req_doc.get("type", None)
    if req_type not in (0, 1):
        raise NotFoundException("Invalid request type")

    new_score = 1 if req_type == 1 else 0
    apply_korean_score(name, new_score)

    req_korean_col.delete_one({"name": name})
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/requests/deny")
async def deny_korean_request(request: Request, name: str = Form(...)):
    next_path = "/author/requests"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)

    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    result = req_korean_col.delete_one({"name": name})
    if result.deleted_count == 0:
        raise NotFoundException("No pending request to deny")

    return RedirectResponse(url=next_path, status_code=303)

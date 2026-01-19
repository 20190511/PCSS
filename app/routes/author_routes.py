from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi import Form
from app.core.templates import templates
from app.services.author_service import compute_author_stats_mongo
from app.db import name_col, req_korean_col, authors_col
from app.data import name_dict
from datetime import datetime, timezone
from app.libs.auth import _require_admin_or_redirect
import re

router = APIRouter()

@router.post("/stats/page", response_class=HTMLResponse)
async def author_stats_page(
    request: Request,
    target_author: str = Form(...), # 화면 표시용 이름
    target_pid: str = Form(...),    # [추가] DB 검색용 PID
    url: str = Form(""),               
    uncertainty: float = Form(0.8),
):
    result = await compute_author_stats_mongo(
        target_pid=target_pid, 
    )
    
    # 한국인 판단 로직 (이름 기준 유지)
    score = name_dict.get(target_author, 0)
    is_korean = score >= uncertainty

    return templates.TemplateResponse(
        "search/author_stats.html",
        {
            "request": request,
            "name": target_author, # 템플릿 타이틀에는 이름을 표시
            "url": url, 
            "stats": result.get("stats", (0, 0, 0, 0)),
            "total": result.get("total", 0),
            "papers": result.get("papers", []),
            "is_korean": is_korean,
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def author_search_input_page(request: Request):
    """
    저자 이름을 검색하여 통계 페이지로 이동하기 위한 입력 폼 페이지
    """
    return templates.TemplateResponse(
        "search/author_search_input.html",
        {"request": request}
    )


@router.get("/autocomplete")
async def author_autocomplete(query: str = Query(..., min_length=1)):
    """
    입력된 query로 시작하거나 포함하는 저자 목록(이름, PID, 소속 등)을 반환.
    성능을 위해 최대 10개만 반환.
    """
    try:
        # 대소문자 구분 없이 부분 일치 검색 (Regex)
        # 인덱스가 걸려있지 않다면 데이터가 많을 경우 느릴 수 있습니다.
        # 운영 환경에서는 Atlas Search나 Text Index 사용을 권장합니다.
        regex_pattern = re.compile(re.escape(query), re.IGNORECASE)
        
        # author_col에서 검색 (이름, PID, 소속 정보 필요)
        # author_col 스키마에 따라 필드명 조정 필요 (여기선 name, pid, affiliation 가정)
        cursor = authors_col.find(
            {"name": {"$regex": regex_pattern}},
            {"_id": 0, "name": 1, "pid": 1, "affiliation": 1} # 필요한 필드만 조회
        ).limit(10)
        
        results = []
        for doc in cursor:
            # PID가 없으면 건너뜀 (PID 필수)
            if not doc.get("pid"):
                continue
                
            results.append({
                "name": doc.get("name"),
                "pid": doc.get("pid"),
                # 소속 정보가 있으면 같이 보여줌
                "affiliation": doc.get("affiliation", "") 
            })
            
        return JSONResponse(content=results)
        
    except Exception as e:
        print(f"[Autocomplete Error] {e}")
        return JSONResponse(content=[], status_code=500)


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
        raise HTTPException(404, "Name not found")

    name_dict[param] = 1

    result = name_col.update_one(
        {"name": param},
        {"$set": {"score": 1, "updated_at": datetime.now(timezone.utc)}},
    )

    if result.matched_count == 0:
        # dict에는 있는데 DB에는 없는 상태 -> 데이터 불일치
        raise HTTPException(404, "Name not found in DB")

    return {"status": "Updated", "param": param}


@router.delete("/korean/{param}")
async def delete_korean_stat(param: str):
    if param not in name_dict:
        raise HTTPException(404, "Name not found")

    name_dict[param] = 0

    result = name_col.update_one(
        {"name": param},
        {"$set": {"score": 0, "updated_at": datetime.now(timezone.utc)}},
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Name not found in DB")

    return {"status": "Deleted", "param": param}


@router.post("/add/korean/{param}")
async def request_add_korean_stat(param: str):
    if param not in name_dict:
        raise HTTPException(404, "Name not found")

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
        raise HTTPException(404, "Name not found")

    result = req_korean_col.delete_one({"name": param})

    if result.deleted_count == 0:
        # 취소할 요청이 없을 때
        raise HTTPException(404, "No pending request to cancel")

    return {"status": "Canceled", "param": param}


@router.post("/delete/korean/{param}")
async def request_delete_korean_stat(param: str):
    if param not in name_dict:
        raise HTTPException(404, "Name not found")

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
            "admin/access_denied.html",
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
        raise HTTPException(404, "Name not found")

    result = name_col.update_one(
        {"name": param},
        {"$set": {"score": score, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Name not found in DB")

    name_dict[param] = score
    

@router.post("/requests/approve")
async def approve_korean_request(request: Request, name: str = Form(...)):
    next_path = "/author/manage"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)

    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    req_doc = req_korean_col.find_one({"name": name})
    if not req_doc:
        raise HTTPException(404, "No pending request")

    req_type = req_doc.get("type", None)
    if req_type not in (0, 1):
        raise HTTPException(404, "Invalid request type")

    new_score = 1 if req_type == 1 else 0
    apply_korean_score(name, new_score)

    req_korean_col.delete_one({"name": name})
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/requests/deny")
async def deny_korean_request(request: Request, name: str = Form(...)):
    next_path = "/author/manage"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)

    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    result = req_korean_col.delete_one({"name": name})
    if result.deleted_count == 0:
        raise HTTPException(404, "No pending request to deny")

    return RedirectResponse(url=next_path, status_code=303)

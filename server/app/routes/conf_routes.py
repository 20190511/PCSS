from fastapi import APIRouter, HTTPException, Query
from app.db import conf_col
from app.schemas.conf import AddUrlRequest, AddParamsRequest, DeleteParamRequest, CreateConferenceRequest
from fastapi import APIRouter, HTTPException, Query, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timezone
from app.core.templates import templates
from app.db import conf_col
from app.libs.auth import _require_admin_or_redirect


router = APIRouter()


def _now():
    return datetime.now(timezone.utc)


def _parse_list(text: str) -> list[str]:
    # 줄바꿈/콤마 모두 지원
    items = []
    for token in (text or "").replace("\r", "\n").replace(",", "\n").split("\n"):
        t = token.strip()
        if t:
            items.append(t)
    # dedup (순서 유지)
    return list(dict.fromkeys(items))


def _normalize_params(doc: dict) -> list[str]:
    """
    DB 문서가
      - params: ["a","b"] (신 스키마)
      - param: "a"        (구 스키마)
    둘 중 무엇이든 와도 항상 List[str]로 정규화.
    """
    ps = doc.get("params")
    if isinstance(ps, list):
        out = [str(x).strip() for x in ps if str(x).strip()]
        if out:
            return out

    p = doc.get("param")
    if isinstance(p, str) and p.strip():
        return [p.strip()]

    return []


def _find_by_param(param: str) -> dict | None:
    """
    param 하나로 조회:
    - 신 스키마: params 배열에 포함
    - 구 스키마: param 필드 일치
    """
    return conf_col.find_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"_id": 0},
    )


@router.get("/manage", response_class=HTMLResponse)
async def conf_manage_page(request: Request):
    # next_path는 "이 페이지"로
    next_path = request.url.path  # /conf/manage 또는 /manage

    email, status_or_resp = _require_admin_or_redirect(request, next_path)
    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp

    # 권한 없음 처리
    if status_or_resp is None:
        return templates.TemplateResponse(
            "admin/admin_conferences.html",
            {
                "request": request,
                "email": email,
                "error": "권한이 없습니다. admin에 등록된 이메일로 로그인하세요.",
                "success": None,
                "conferences": [],
            },
            status_code=403,
        )

    docs = list(conf_col.find({}, {"_id": 0}))
    for d in docs:
        d["params"] = _normalize_params(d)
        d.pop("param", None)
        d["urls"] = d.get("urls") or []
        d["kind"] = (d.get("kind") or "").strip()
        d["name"] = (d.get("name") or "").strip()

    docs.sort(key=lambda x: (x.get("kind",""), x.get("name",""), ",".join(x.get("params") or [])))

    return templates.TemplateResponse(
        "admin/admin_conferences.html",
        {
            "request": request,
            "email": email,
            "error": None,
            "success": None,
            "conferences": docs,
        },
    )


@router.post("/manage/create", response_class=HTMLResponse)
async def conf_manage_create(
    request: Request,
    kind: str = Form(...),
    name: str = Form(""),
    params_text: str = Form(...),
    urls_text: str = Form(""),
):
    next_path = request.url_for("conf_manage_page") if False else (request.url.path.replace("/create", ""))  # 안전장치용
    # 실제 redirect는 상대경로로 보낼 거라 next_path는 아래처럼 단순 처리
    next_path = request.url.path.rsplit("/", 1)[0]  # .../manage

    email, status_or_resp = _require_admin_or_redirect(request, next_path)
    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    kind = (kind or "").strip()
    name = (name or "").strip()
    params = _parse_list(params_text)
    urls = _parse_list(urls_text)

    if not kind:
        return RedirectResponse(url=next_path, status_code=303)
    if not params:
        return RedirectResponse(url=next_path, status_code=303)

    # params 유니크 검사
    exists = conf_col.find_one({"$or": [{"params": {"$in": params}}, {"param": {"$in": params}}]}, {"_id": 1})
    if exists:
        docs = list(conf_col.find({}, {"_id": 0}))
        for d in docs:
            d["params"] = _normalize_params(d)
            d.pop("param", None)
            d["urls"] = d.get("urls") or []
        return templates.TemplateResponse(
            "admin/admin_conferences.html",
            {
                "request": request,
                "email": email,
                "error": "이미 사용 중인 param이 포함되어 있습니다.",
                "success": None,
                "conferences": docs,
            },
            status_code=409,
        )

    now = _now()
    conf_col.insert_one({
        "kind": kind,
        "name": name,
        "params": params,
        "urls": urls,
        "created_at": now,
        "updated_at": now,
        "meta": {"created_by": email},
    })
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/manage/{base_param}/urls/add", response_class=HTMLResponse)
async def conf_manage_add_url(request: Request, base_param: str, url: str = Form(...)):
    next_path = "/conferences/manage"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)
    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    url = (url or "").strip()
    if url:
        conf_col.update_one(
            {"$or": [{"params": base_param}, {"param": base_param}]},
            {"$addToSet": {"urls": url}, "$set": {"updated_at": _now()}},
        )
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/manage/{base_param}/urls/delete", response_class=HTMLResponse)
async def conf_manage_delete_url(request: Request, base_param: str, url: str = Form(...)):
    next_path = "/conferences/manage"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)
    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    url = (url or "").strip()
    if url:
        conf_col.update_one(
            {"$or": [{"params": base_param}, {"param": base_param}]},
            {"$pull": {"urls": url}, "$set": {"updated_at": _now()}},
        )
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/manage/{base_param:path}/params/add", response_class=HTMLResponse)
async def conf_manage_add_params(request: Request, base_param: str, params_text: str = Form(...)):
    next_path = "/conferences/manage"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)
    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    new_params = _parse_list(params_text)
    if not new_params:
        return RedirectResponse(url=next_path, status_code=303)

    # 다른 문서에서 이미 사용 중인지 검사
    exists = conf_col.find_one(
        {"$or": [{"params": {"$in": new_params}}, {"param": {"$in": new_params}}]},
        {"_id": 1},
    )
    if exists:
        docs = list(conf_col.find({}, {"_id": 0}))
        for d in docs:
            d["params"] = _normalize_params(d)
            d.pop("param", None)
            d["urls"] = d.get("urls") or []
        return templates.TemplateResponse(
            "admin/admin_conferences.html",
            {
                "request": request,
                "email": email,
                "error": "추가하려는 param 중 이미 사용 중인 값이 있습니다.",
                "success": None,
                "conferences": docs,
            },
            status_code=409,
        )

    conf_col.update_one(
        {"$or": [{"params": base_param}, {"param": base_param}]},
        {"$addToSet": {"params": {"$each": new_params}}, "$set": {"updated_at": _now()}},
    )
    # 구 스키마 필드 제거
    conf_col.update_one({"$or": [{"params": base_param}, {"param": base_param}]}, {"$unset": {"param": ""}})
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/manage/{base_param:path}/params/delete", response_class=HTMLResponse)
async def conf_manage_delete_param(request: Request, base_param: str, param: str = Form(...)):
    next_path = "/conferences/manage"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)
    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    param = (param or "").strip()
    if not param:
        return RedirectResponse(url=next_path, status_code=303)

    doc = conf_col.find_one({"$or": [{"params": base_param}, {"param": base_param}]}, {"_id": 0, "params": 1, "param": 1})
    if not doc:
        return RedirectResponse(url=next_path, status_code=303)

    params = _normalize_params(doc)
    if param not in params:
        return RedirectResponse(url=next_path, status_code=303)

    if len(params) <= 1:
        docs = list(conf_col.find({}, {"_id": 0}))
        for d in docs:
            d["params"] = _normalize_params(d)
            d.pop("param", None)
            d["urls"] = d.get("urls") or []
        return templates.TemplateResponse(
            "admin/admin_conferences.html",
            {
                "request": request,
                "email": email,
                "error": "마지막 param은 삭제할 수 없습니다.",
                "success": None,
                "conferences": docs,
            },
            status_code=400,
        )

    conf_col.update_one(
        {"$or": [{"params": base_param}, {"param": base_param}]},
        {"$pull": {"params": param}, "$set": {"updated_at": _now()}},
    )
    return RedirectResponse(url=next_path, status_code=303)


@router.post("/manage/{base_param:path}/delete", response_class=HTMLResponse)
async def conf_manage_delete_conference(request: Request, base_param: str):
    next_path = "/conferences/manage"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)
    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp
    if status_or_resp is None:
        return RedirectResponse(url=next_path, status_code=303)

    conf_col.delete_one({"$or": [{"params": base_param}, {"param": base_param}]})
    return RedirectResponse(url=next_path, status_code=303)


@router.get("/api/kinds")
async def get_kinds():
    # distinct는 동기지만 작은 데이터라 ok
    kinds = conf_col.distinct("kind")
    return {"kinds": kinds}


@router.get("/api/by-kind/{kind}")
async def get_conferences_by_kind(kind: str):
    docs = list(conf_col.find({"kind": kind}, {"_id": 0}))
    if not docs:
        raise HTTPException(404, "No conferences for this kind")

    # 응답에서 params 보장(구 스키마 문서도 포함)
    for d in docs:
        d["params"] = _normalize_params(d)
        d.pop("param", None)  # 구 필드 숨기고 싶으면 유지, 필요하면 제거하지 말 것

    return docs


@router.get("/api/{param}")
async def get_conference(param: str):
    doc = _find_by_param(param)
    if not doc:
        raise HTTPException(404, "Conference not found")

    doc["params"] = _normalize_params(doc)
    doc.pop("param", None)
    return doc


@router.post("/api/{param}/urls")
async def add_conference_url(param: str, body: AddUrlRequest):
    # params 배열 / param 단일 모두 대응
    result = conf_col.update_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"$addToSet": {"urls": body.url}},  # 중복 방지
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    return {"status": "added", "param": param, "url": body.url}


@router.delete("/api/{param}/urls")
async def delete_conference_url(param: str, url: str = Query(...)):
    result = conf_col.update_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"$pull": {"urls": url}},
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    return {"status": "deleted", "param": param, "url": url}


@router.post("/api/")
async def create_conference(body: CreateConferenceRequest):
    data = body.dict()

    params = data.get("params")
    if params is None:
        # 혹시 스키마가 아직 param만 받는다면 여기서 변환
        p = data.get("param")
        if isinstance(p, str) and p.strip():
            params = [p.strip()]
        else:
            params = []
    if not isinstance(params, list) or not any(str(x).strip() for x in params):
        raise HTTPException(422, "params must be a non-empty list")

    params = [str(x).strip() for x in params if str(x).strip()]
    data["params"] = params
    data.pop("param", None)  # 구 필드는 저장하지 않음(원하면 제거)

    if conf_col.find_one({"$or": [{"params": {"$in": params}}]}):
        raise HTTPException(409, "one of params already exists")

    conf_col.insert_one(data)
    return {"status": "created", "params": params}


@router.delete("/api/{param}")
async def delete_conference(param: str):
    # params 배열 / param 단일 모두 대응해서 삭제
    result = conf_col.delete_one({"$or": [{"params": param}, {"param": param}]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Conference not found")
    return {"status": "deleted", "param": param}


@router.post("/api/{param}/params")
async def add_params_batch(param: str, body: AddParamsRequest):
    new_params = [p.strip() for p in body.params if p.strip()]
    if not new_params:
        raise HTTPException(422, "params is empty")

    # 다른 문서에서 이미 쓰는 param이면 막기 (전체 검사)
    exists = conf_col.find_one(
        {"$or": [{"params": {"$in": new_params}}, {"param": {"$in": new_params}}]},
        {"_id": 1}
    )
    if exists:
        raise HTTPException(409, "one of params already exists in another conference")

    result = conf_col.update_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"$addToSet": {"params": {"$each": new_params}}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    conf_col.update_one({"$or": [{"params": param}, {"param": param}]}, {"$unset": {"param": ""}})
    return {"status": "added", "base": param, "params": new_params}


@router.delete("/api/{param}/params")
async def delete_param(param: str, body: DeleteParamRequest):
    del_param = body.param.strip()
    if not del_param:
        raise HTTPException(422, "param is empty")

    doc = conf_col.find_one({"$or": [{"params": param}, {"param": param}]}, {"_id": 0, "params": 1})
    if not doc:
        raise HTTPException(404, "Conference not found")

    params = doc.get("params") or []
    if del_param not in params:
        raise HTTPException(404, "param not in this conference")

    # params가 1개만 남아있는데 그걸 삭제하려 하면 막기
    if len(params) <= 1:
        raise HTTPException(400, "cannot delete the last param")

    result = conf_col.update_one(
        {"$or": [{"params": param}, {"param": param}]},
        {"$pull": {"params": del_param}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Conference not found")

    return {"status": "deleted", "base": param, "param": del_param}

from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from uuid import uuid4
from datetime import datetime, timezone
import secrets
from pymongo import ReturnDocument
from app.libs.exceptions import NotFoundException
from app.schemas.subscription import (
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
    SubscriptionUnsubscribeRequest,
)
from app.libs.logger import get_client_ip
from app.db import subscription_col, log_col, subscription_auth_col
from app.data import get_conferences_for_ui
from app.core.templates import templates

from fastapi import Response
from fastapi.responses import RedirectResponse
import hashlib
from datetime import timedelta
from app.libs.email import send_email
import os


router = APIRouter()
SESSION_COOKIE = "pcss_sub_session"

def _hash_code(email: str, code: str, secret: str) -> str:
    raw = f"{email}|{code}|{secret}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _get_session_email(request: Request):
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return None
    now = _now()
    doc = subscription_auth_col.find_one(
        {"kind": "session", "session_id": sid, "expires_at": {"$gt": now}},
        {"_id": 0, "email": 1},
    )
    return (doc or {}).get("email")


def _require_login(request: Request):
    email = _get_session_email(request)
    if not email:
        return None
    return email

def _now():
    return datetime.now(timezone.utc)


def _dedup_list(xs):
    out = []
    seen = set()
    for x in xs or []:
        x2 = (x or "").strip()
        if not x2:
            continue
        if x2 not in seen:
            seen.add(x2)
            out.append(x2)
    return out


def _validate_options(opts):
    allowed = {1, 2, 3, 4}
    clean = []
    for x in (opts or []):
        try:
            xi = int(x)
        except Exception:
            continue
        if xi in allowed and xi not in clean:
            clean.append(xi)
    return clean


def _parse_bool(s: str, default: bool = True) -> bool:
    if s is None:
        return default
    s = str(s).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


def _option_labels():
    return [
        (1, "1저자"),
        (2, "2저자"),
        (3, "마지막 저자"),
        (4, "공저자"),
    ]


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("subscription_login.html", {"request": request})


@router.post("/login/send", response_class=HTMLResponse)
async def login_send(request: Request, email: str = Form(...)):
    ip = get_client_ip(request)
    now = _now()
    email_norm = (email or "").strip().lower()

    # 6자리 코드 생성
    code = f"{secrets.randbelow(1000000):06d}"

    # 서버 시크릿(환경변수) 필요
    AUTH_SECRET = os.getenv("SUB_AUTH_SECRET", "dev-secret-change-me")

    code_hash = _hash_code(email_norm, code, AUTH_SECRET)
    expires_at = now + timedelta(minutes=10)

    subscription_auth_col.update_one(
        {"kind": "otp", "email": email_norm},
        {"$set": {
            "kind": "otp",
            "email": email_norm,
            "code_hash": code_hash,
            "expires_at": expires_at,
            "tries": 0,
            "created_at": now,
            "ip": ip,
        }},
        upsert=True,
    )

    send_email(
        receiver=email_norm,
        title="[PCSS] 로그인 인증 코드",
        text=f"PCSS 구독 관리 페이지 로그인 인증 코드입니다: {code}\n"
    )

    return templates.TemplateResponse(
        "subscription_login_verify.html",
        {"request": request, "email": email_norm, "message": "인증 코드를 메일로 보냈습니다."},
    )


@router.post("/login/verify", response_class=HTMLResponse)
async def login_verify(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
):
    ip = get_client_ip(request)
    now = _now()
    email_norm = (email or "").strip().lower()
    code = (code or "").strip()

    AUTH_SECRET = os.getenv("SUB_AUTH_SECRET", "dev-secret-change-me")

    otp = subscription_auth_col.find_one(
        {"kind": "otp", "email": email_norm, "expires_at": {"$gt": now}},
        {"_id": 0},
    )
    if not otp:
        return templates.TemplateResponse(
            "subscription_login_verify.html",
            {"request": request, "email": email_norm, "error": "코드가 만료되었거나 없습니다."},
        )

    # 시도 횟수 제한
    tries = int(otp.get("tries", 0))
    if tries >= 5:
        return templates.TemplateResponse(
            "subscription_login_verify.html",
            {"request": request, "email": email_norm, "error": "시도 횟수를 초과했습니다. 다시 요청하세요."},
        )

    expected = otp.get("code_hash")
    given = _hash_code(email_norm, code, AUTH_SECRET)

    if not expected or not secrets.compare_digest(expected, given):
        subscription_auth_col.update_one(
            {"kind": "otp", "email": email_norm},
            {"$inc": {"tries": 1}},
        )
        return templates.TemplateResponse(
            "subscription_login_verify.html",
            {"request": request, "email": email_norm, "error": "인증 코드가 올바르지 않습니다."},
        )

    # OTP 삭제(또는 만료 처리)
    subscription_auth_col.delete_one({"kind": "otp", "email": email_norm})

    # 세션 발급
    session_id = secrets.token_urlsafe(32)
    sess_expires = now + timedelta(days=14)

    subscription_auth_col.insert_one({
        "kind": "session",
        "session_id": session_id,
        "email": email_norm,
        "expires_at": sess_expires,
        "created_at": now,
        "ip": ip,
    })

    # 쿠키 설정 (로컬/HTTPS 환경에 맞게 secure 조정)
    response = RedirectResponse(url="/subscriptions/manage", status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,  # https 배포면 True 권장
        max_age=14 * 24 * 3600,
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        subscription_auth_col.delete_many({"kind": "session", "session_id": sid})
    resp = RedirectResponse(url="/subscriptions/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# =========================
# Pages (HTML)
# =========================

@router.get("/manage", response_class=HTMLResponse)
async def manage_page(request: Request):
    email_norm = _require_login(request)
    if not email_norm:
        return RedirectResponse("/subscriptions/login", status_code=302)

    now = _now()
    doc = subscription_col.find_one({"email": email_norm}, {"_id": 0})

    # 첫 로그인: 구독 문서가 없으면 기본값으로 생성
    if not doc:
        default_doc = {
            "subscription_id": str(uuid4()),
            "email": email_norm,
            "conferences": [],
            "options": [1],
            "threshold": 0.8,
            "is_enabled": True,
            "created_at": now,   # insert 시에만
        }

        doc = subscription_col.find_one_and_update(
            {"email": email_norm},
            {
                "$setOnInsert": default_doc,
                "$set": {"updated_at": now},  # insert / update 공통
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )


    return templates.TemplateResponse(
        "manage_subscription.html",
        {
            "request": request,
            "error": None,
            "success": None,
            "email": email_norm,
            "subscription": doc,
            "conferences": get_conferences_for_ui(),
            "options": _option_labels(),
        },
    )



@router.post("/manage/update", response_class=HTMLResponse)
async def manage_update(
    request: Request,
    conferences: list[str] = Form([]),
    options: list[str] = Form([]),
    threshold: float = Form(0.8),
    is_enabled: str = Form("true"),
):
    email_norm = _require_login(request)
    if not email_norm:
        return RedirectResponse("/subscriptions/login", status_code=302)

    now = _now()
    patch = {
        "email": email_norm,
        "conferences": _dedup_list(conferences),
        "options": _validate_options(options),
        "threshold": float(threshold),
        "is_enabled": bool(_parse_bool(is_enabled, default=True)),
        "updated_at": now,
    }

    subscription_col.update_one(
        {"email": email_norm},
        {"$set": patch, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    clean_options = _validate_options(options)
    if len(clean_options) == 0:
        # 현재 구독 정보 다시 로드해서 그대로 보여주고 에러만 띄움
        doc = subscription_col.find_one({"email": email_norm}, {"_id": 0})
        return templates.TemplateResponse(
            "manage_subscription.html",
            {
                "request": request,
                "error": "옵션은 최소 1개 이상 선택해야 합니다.",
                "success": None,
                "email": email_norm,
                "subscription": doc,
                "conferences": get_conferences_for_ui(),
                "options": _option_labels(),
                "default_threshold": 0.8,
                "default_selected_options": [1, 2, 3, 4],
            },
            status_code=400,
        )


@router.post("/manage/unsubscribe", response_class=HTMLResponse)
async def manage_unsubscribe(request: Request):
    email_norm = _require_login(request)
    if not email_norm:
        return RedirectResponse("/subscriptions/login", status_code=302)

    now = _now()
    subscription_col.update_one(
        {"email": email_norm},
        {"$set": {"is_enabled": False, "updated_at": now}},
    )
    return templates.TemplateResponse(
        "unsubscribe_done.html",
        {"request": request, "error": None, "email": email_norm},
    )


# =========================
# JSON API
# =========================

@router.post("/create")
async def create_subscription(req: SubscriptionCreateRequest, request: Request):
    ip = get_client_ip(request)
    now = _now()

    email = str(req.email).lower()

    # subscription_id 유지/생성
    existing = subscription_col.find_one({"email": email}, {"_id": 0, "subscription_id": 1})
    subscription_id = (existing or {}).get("subscription_id") or str(uuid4())

    manage_token = secrets.token_urlsafe(32)

    doc = {
        "subscription_id": subscription_id,
        "email": email,
        "conferences": _dedup_list(req.conferences),
        "options": _validate_options(req.options),
        "threshold": float(req.threshold),
        "is_enabled": bool(req.is_enabled),
        "manage_token": manage_token,
        "updated_at": now,
        "meta": {
            "created_ip": ip,
            "user_agent": request.headers.get("user-agent", ""),
            "referer": request.headers.get("referer", ""),
        },
    }

    subscription_col.update_one(
        {"email": email},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    try:
        if ip not in ["127.0.0.1", "::1"]:
            log_col.insert_one({
                "ts": now,
                "type": "subscription_create",
                "ip": ip,
                "email": email,
                "conferences": doc["conferences"],
                "options": doc["options"],
                "threshold": doc["threshold"],
                "is_enabled": doc["is_enabled"],
                "user_agent": request.headers.get("user-agent", ""),
                "referer": request.headers.get("referer", ""),
            })
    except Exception:
        pass

    return JSONResponse({
        "status": "ok",
        "email": email,
        "manage_token": manage_token,
        "subscription_id": subscription_id,
    })


@router.get("/get/{email}")
async def get_subscription(email: str):
    doc = subscription_col.find_one(
        {"email": email.lower()},
        {"_id": 0, "manage_token": 0},
    )
    if not doc:
        raise NotFoundException("subscription not found")
    return JSONResponse(doc)


@router.post("/update")
async def update_subscription(req: SubscriptionUpdateRequest, request: Request):
    ip = get_client_ip(request)
    now = _now()
    email = str(req.email).lower()

    existing = subscription_col.find_one({"email": email}, {"_id": 0})
    if not existing:
        raise NotFoundException("subscription not found")

    if existing.get("manage_token") != req.manage_token:
        return JSONResponse({"status": "forbidden"}, status_code=403)

    patch = {"updated_at": now}

    if req.conferences is not None:
        patch["conferences"] = _dedup_list(req.conferences)
    if req.options is not None:
        clean_options = _validate_options(req.options)
        if len(clean_options) == 0:
            return JSONResponse(
                {"status": "bad_request", "message": "옵션은 최소 1개 이상 선택해야 합니다."},
                status_code=400,
            )
        patch["options"] = clean_options
    if req.threshold is not None:
        patch["threshold"] = float(req.threshold)
    if req.is_enabled is not None:
        patch["is_enabled"] = bool(req.is_enabled)

    subscription_col.update_one({"email": email}, {"$set": patch})

    try:
        if ip not in ["127.0.0.1", "::1"]:
            log_col.insert_one({
                "ts": now,
                "type": "subscription_update",
                "ip": ip,
                "email": email,
                "patch": {k: v for k, v in patch.items() if k != "updated_at"},
                "user_agent": request.headers.get("user-agent", ""),
                "referer": request.headers.get("referer", ""),
            })
    except Exception:
        pass

    doc = subscription_col.find_one({"email": email}, {"_id": 0, "manage_token": 0})
    return JSONResponse({"status": "ok", "subscription": doc})


@router.post("/unsubscribe")
async def unsubscribe(req: SubscriptionUnsubscribeRequest, request: Request):
    ip = get_client_ip(request)
    now = _now()
    email = str(req.email).lower()

    existing = subscription_col.find_one({"email": email}, {"_id": 0})
    if not existing:
        raise NotFoundException("subscription not found")

    if existing.get("manage_token") != req.manage_token:
        return JSONResponse({"status": "forbidden"}, status_code=403)

    subscription_col.update_one(
        {"email": email},
        {"$set": {"is_enabled": False, "updated_at": now}},
    )

    try:
        if ip not in ["127.0.0.1", "::1"]:
            log_col.insert_one({
                "ts": now,
                "type": "subscription_unsubscribe",
                "ip": ip,
                "email": email,
                "user_agent": request.headers.get("user-agent", ""),
                "referer": request.headers.get("referer", ""),
            })
    except Exception:
        pass

    return JSONResponse({"status": "ok", "email": email, "is_enabled": False})

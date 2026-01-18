# app/libs/auth.py
import hashlib
import os
import secrets
from datetime import datetime, timezone
from fastapi import Request
from app.db import subscription_auth_col  # 필요하면 auth_col로 rename

SESSION_COOKIE = "pcss_sub_session"

def now_utc():
    return datetime.now(timezone.utc)

def auth_secret() -> str:
    # 운영에서는 기본값 쓰지 말고 필수로 두는 걸 추천
    return os.getenv("SUB_AUTH_SECRET", "dev-secret-change-me")

def hash_code(email: str, code: str) -> str:
    raw = f"{email}|{code}|{auth_secret()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def get_session_email(request: Request) -> str | None:
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        return None
    now = now_utc()
    doc = subscription_auth_col.find_one(
        {"kind": "session", "session_id": sid, "expires_at": {"$gt": now}},
        {"_id": 0, "email": 1},
    )
    return (doc or {}).get("email")

def require_login(request: Request) -> str | None:
    # 일단 현재 스타일대로 None 반환
    return get_session_email(request)

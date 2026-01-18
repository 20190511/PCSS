from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone

from app.core.templates import templates
from app.db import log_col
from app.libs.logger import get_client_ip


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    user = request.session.get("user")  # 없으면 None

    try:
        ip = get_client_ip(request)
        if ip not in ["127.0.0.1", "::1"]:
            log_col.insert_one({
                "ts": datetime.now(timezone.utc),
                "type": "homepage",
                "ip": ip,
                "method": request.method,
                "path": request.url.path,
                "query": dict(request.query_params),
                "user_agent": request.headers.get("user-agent", ""),
                "referer": request.headers.get("referer", ""),
            })
    except Exception:
        print("Failed to log homepage visit event")

    return templates.TemplateResponse(
        "homepage.html",
        {
            "request": request,
            "user": user,   
        }
    )


from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.core.templates import templates
from app.libs.auth import _require_admin_or_redirect

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # 관리자 권한 확인 로직 (기존 코드 패턴 유지)
    next_path = "/admin/dashboard"
    email, status_or_resp = _require_admin_or_redirect(request, next_path)

    # 1. 로그인 안 된 경우 -> 로그인 페이지로 리다이렉트
    if isinstance(status_or_resp, RedirectResponse):
        return status_or_resp

    # 2. 로그인은 됐으나 관리자가 아닌 경우 -> 에러 페이지 표시 (또는 403)
    if status_or_resp is None:
        return templates.TemplateResponse(
            "admin/access_denied.html", 
            {
                "request": request,
                "error": "관리자 권한이 없습니다."
            },
            status_code=403,
        )

    # 3. 관리자 인증 성공 -> 대시보드 렌더링
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "email": email
        },
    )
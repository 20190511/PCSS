from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.paths import STATIC_DIR, TEMPLATES_DIR
from app.routes.author_routes import router as author_router
from app.routes.home_routes import router as home_router
from app.routes.subscription_routes import router as subscription_router
from app.routes.auth_routes import router as auth_router
from app.routes.conf_routes import router as conf_router
from app.routes.search_routes import router as search_router
from app.routes.admin_routes import router as admin_router
from app.routes.board_routes import router as board_router
from app.routes.log_routes import router as log_router
from app.db.mongo import get_mongo_client
from app.db import errors_col
from app.libs.logger import get_client_ip
from app.libs.auth import get_session_email
from datetime import datetime, timezone
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware  
from starlette.responses import RedirectResponse
from app.core.templates import templates 
import traceback

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PCSS API", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://pcss.r-e.kr",
        "https://pcss.r-e.kr",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    await get_mongo_client()
    
class AccessControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. 예외 경로 설정 (무한 루프 방지 및 필수 리소스 허용)
        # /static: 스타일/JS 로딩을 위해 필수
        # /auth: 로그인 페이지 및 인증 로직은 누구나 접근 가능해야 함
        # /docs, /openapi.json: API 문서 (필요 시 제거 가능)
        if request.url.path.startswith(("/static", "/auth", "/favicon.ico", "/docs", "/openapi.json")):
            return await call_next(request)

        # 2. IP 검사
        ip = get_client_ip(request)
        print(f"Incoming request from IP: {ip} to {request.url.path}")
        # 로컬호스트 또는 POSTECH IP(141.223.*) 인지 확인
        is_internal = ip.startswith("141.223.") or ip in ["127.0.0.1", "::1"]

        if is_internal:
            # 내부망이면 통과
            return await call_next(request)

        # 3. 외부망일 경우 로그인 세션 검사
        email = get_session_email(request)
        if email:
            # 로그인이 되어 있다면 통과
            return await call_next(request)

        # 4. 조건 불충족 시 로그인 페이지로 강제 리다이렉트
        # next 파라미터에 현재 가려던 주소를 담아서 보냄
        return RedirectResponse(url=f"/auth/login?next={request.url.path}", status_code=302)

# 미들웨어 등록
app.add_middleware(AccessControlMiddleware)

app.include_router(home_router)
app.include_router(conf_router, prefix="/conferences")
app.include_router(author_router, prefix="/author")
app.include_router(subscription_router, prefix="/subscriptions")
app.include_router(auth_router, prefix="/auth")
app.include_router(search_router, prefix="/api/search")
app.include_router(admin_router, prefix="/admin")
app.include_router(board_router, prefix="/board")
app.include_router(log_router, prefix="/logs")

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    return templates.TemplateResponse(
        "errors/404.html",  # 미리 만들어둔 404 템플릿 경로
        {
            "request": request,
            "error_message": "" 
        },
        status_code=404
    )
    
@app.exception_handler(500)
async def custom_500_handler(request: Request, exc: Exception):
    try:
        ip = get_client_ip(request)
    
        error_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        # DB에 에러 로그 저장
        errors_col.insert_one({
            "ts": datetime.now(timezone.utc),
            "type": "server_error",
            "ip": ip,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "error_message": str(exc),
            "traceback": error_trace, # 디버깅용 상세 정보
            "user_agent": request.headers.get("user-agent", ""),
        })
    except Exception as log_error:
        print(f"Failed to log 500 error to DB: {log_error}")

    return templates.TemplateResponse(
        "errors/500.html",
        {
            "request": request,
            "error_message": "서버 내부에서 오류가 발생했습니다. 관리자에게 문의하거나 잠시 후 다시 시도해주세요."
        },
        status_code=500
    )
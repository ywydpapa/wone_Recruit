import asyncio
import json
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
import dotenv

from core.db import get_sqlite
from core.logger import log
from core.deps import templates
from core.csrf import ensure_token, verify_csrf

dotenv.load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from init_db import migrate
    from core.jobs import close_expired_jobs, run_scheduler
    migrate()
    close_expired_jobs()
    task = asyncio.create_task(run_scheduler())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan, dependencies=[Depends(verify_csrf)])


@app.exception_handler(StarletteHTTPException)
async def on_http_err(request: Request, exc: StarletteHTTPException):
    status = exc.status_code
    if status == 403:
        tpl = "errors/403.html"
        title = "접근 권한 없음"
    elif status == 404:
        tpl = "errors/404.html"
        title = "페이지를 찾을 수 없음"
    else:
        tpl = "errors/500.html"
        title = "서버 오류"
    user_name = request.session.get("name", "")
    user_role = request.session.get("role", "")
    return templates.TemplateResponse(
        request=request, name=tpl,
        status_code=status,
        context={
            "request": request, "page_title": title,
            "user_name": user_name, "user_role": user_role,
            "status_code": status,
            "detail": str(exc.detail) if exc.detail else "",
        },
    )


@app.exception_handler(Exception)
async def on_err(request: Request, exc: Exception):
    log.exception("500 에러: %s %s", request.method, request.url.path)
    user_name = request.session.get("name", "")
    user_role = request.session.get("role", "")
    return templates.TemplateResponse(
        request=request, name="errors/500.html",
        status_code=500,
        context={
            "request": request, "page_title": "서버 오류",
            "user_name": user_name, "user_role": user_role,
            "status_code": 500,
            "detail": "",
        },
    )

_secret = os.getenv("SESSION_SECRET_KEY")
if not _secret:
    raise RuntimeError("SESSION_SECRET_KEY 환경변수 필수")

class CSRFTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = ensure_token(request)
        request.state.csrf_token = token
        return await call_next(request)


A11Y_DEFAULT = {"high_contrast": False, "font_size": 100, "large_target": False, "easy_mode": False, "head_mouse": False, "dwell_read": False, "input_delay": 0, "dwell_ms": 1500, "tts_voice": "F1", "tts_speed": "normal"}


class A11yMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        saved = {}
        if request.session.get("logined") and not request.url.path.startswith("/static"):
            conn = get_sqlite()
            try:
                row = conn.execute("SELECT accessibility_settings FROM users WHERE id=?", (request.session.get("id"),)).fetchone()
            finally:
                conn.close()
            if row and row["accessibility_settings"]:
                saved = json.loads(row["accessibility_settings"])
        request.state.a11y = {**A11Y_DEFAULT, **saved}
        request.state.dwell_sec = f"{request.state.a11y['dwell_ms'] / 1000:g}"
        return await call_next(request)


class ForcePasswordChangeMiddleware(BaseHTTPMiddleware):
    _ALLOWED = ("/change-password", "/logout", "/static")

    async def dispatch(self, request: Request, call_next):
        if request.session.get("must_change_password"):
            path = request.url.path
            if not any(path.startswith(p) for p in self._ALLOWED):
                return RedirectResponse(url="/change-password", status_code=303)
        return await call_next(request)


app.add_middleware(A11yMiddleware)
app.add_middleware(ForcePasswordChangeMiddleware)
app.add_middleware(CSRFTokenMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=_secret,
    https_only=os.getenv("ENVIRONMENT") == "production",
    same_site="strict",
)

os.makedirs("static/css", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

from routers import auth, dashboard, company, seeker, info, operator, resume, community, manager, messages, inquiry, accessibility, refs, notice, consult, status
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(company.router)
app.include_router(company.api_router)
app.include_router(seeker.router)
app.include_router(resume.router)
app.include_router(info.router)
app.include_router(operator.router)
app.include_router(community.router)
app.include_router(messages.router)
app.include_router(manager.router)
app.include_router(inquiry.router)
app.include_router(accessibility.router)
app.include_router(refs.router)
app.include_router(notice.router)
app.include_router(consult.router)
app.include_router(status.router)

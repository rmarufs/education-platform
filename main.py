# Точка входа в приложение FastAPI
import os
import logging
from fastapi import FastAPI, Request, status, Depends
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.config import (
    APP_ENV,
    AUTO_APPLY_MIGRATIONS,
    ENABLE_API_DOCS,
    IS_PRODUCTION,
    PLATFORM_NAME,
    SECRET_KEY,
)
from app.database import SessionLocal, get_db
from app.models.user import User
from app.routers import auth, users, courses
from app.routers import modules, lessons, reviews, comments, profile, pages
from app.routers import admin
from app.routers import organization
from app.routers import groups
from app.routers import push
from app.utils.csrf import CSRFMiddleware

logger = logging.getLogger(__name__)

# Создаём папку data если её нет
os.makedirs("data", exist_ok=True)

app = FastAPI(
    title=PLATFORM_NAME,
    docs_url="/api/docs" if ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_API_DOCS else None,
)

# ── Rate Limiting (SlowAPI) ───────────────────────────────────────────────────
from slowapi.errors import RateLimitExceeded
from app.utils.rate_limit import limiter

app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Слишком много попыток. Пожалуйста, подождите. / Кӯшишҳои аз ҳад зиёд. Лутфан, интизор шавед."},
    )

# ── Middleware ──────────────────────────────────────────────────────────────

# Сжатие ответов (gzip) для CSS, JS, HTML - улучшает скорость загрузки на 3-5×
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    )
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    if IS_PRODUCTION and (request.url.scheme == "https" or forwarded_proto == "https"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Middleware для сессий на основе куков (укрепленные настройки безопасности)
# https_only=True обязателен на проде (HTTPS), на локалке отключаем
app.add_middleware(CSRFMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=60 * 60 * 24 * 7,
    https_only=IS_PRODUCTION,
    same_site="lax"
)

# Статические файлы (CSS, JS, изображения)
class PublicStaticFiles(StaticFiles):
    _blocked_prefixes = ("documents/", "uploads/applications/")
    _blocked_exact = ("documents", "uploads/applications")

    async def get_response(self, path, scope):
        normalized_path = path.replace("\\", "/").lstrip("/")
        if normalized_path in self._blocked_exact or normalized_path.startswith(self._blocked_prefixes):
            raise StarletteHTTPException(status_code=404)
        return await super().get_response(path, scope)


app.mount("/static", PublicStaticFiles(directory="static"), name="static")

from app.ui import templates



# ── Middleware для кэширования пользователя в контексте запроса ────────────────

async def _get_request_user(request: Request, db=Depends(get_db)) -> User | None:
    """
    Получить текущего пользователя из сессии. 
    Кэширует результат в request.state чтобы избежать повторных запросов к БД.
    """
    # Проверяем если уже загружали пользователя в этом запросе
    if hasattr(request.state, "user"):
        return request.state.user
    
    user_id = request.session.get("user_id")
    if not user_id:
        request.state.user = None
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    request.state.user = user
    return user


def _load_request_user(request: Request):
    """
    DEPRECATED: Используется только в error handlers для совместимости.
    В производстве используйте _get_request_user с Depends().
    """
    # Сначала проверярем cache в request.state
    if hasattr(request.state, "user"):
        return request.state.user
    
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def _render_error_page(
    request: Request,
    status_code: int,
    title: str,
    message: str,
    user=None,
):
    """Отрендерить страницу ошибки."""
    # Если user не передан, пытаемся получить из кэша request.state
    if user is None:
        user = getattr(request.state, "user", None)
        # Если нет в кэше, то пытаемся загрузить (fallback)
        if user is None:
            user = _load_request_user(request)
    
    return templates.TemplateResponse(
        f"errors/{status_code}.html",
        {
            "request": request,
            "user": user,
            "status_code": status_code,
            "error_title": title,
            "error_message": message,
        },
        status_code=status_code,
    )

# ── Роутеры ────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(modules.router)
app.include_router(lessons.router)

app.include_router(reviews.router)
app.include_router(comments.router)
app.include_router(profile.router)
app.include_router(pages.router)
app.include_router(admin.router)
app.include_router(organization.router)
app.include_router(groups.router)
app.include_router(push.router)

@app.get("/sw.js")
async def get_service_worker():
    """Отдаёт Service Worker с корня для максимального scope."""
    return FileResponse("static/js/sw.js", media_type="application/javascript")

# ── Инициализация БД при старте ──────────────────────────────────────────────

def _run_alembic_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@app.on_event("startup")
def on_startup():
    logger.info(
        "%s startup: env=%s, docs_enabled=%s, auto_migrations=%s",
        PLATFORM_NAME,
        APP_ENV,
        ENABLE_API_DOCS,
        AUTO_APPLY_MIGRATIONS,
    )

    if not AUTO_APPLY_MIGRATIONS:
        logger.info("Automatic Alembic migrations are disabled for this environment.")
        return

    try:
        _run_alembic_migrations()
    except Exception:
        logger.exception("Alembic migration failed during startup; aborting application startup.")
        raise

    logger.info("Alembic migrations applied successfully.")

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return _render_error_page(
            request,
            status.HTTP_403_FORBIDDEN,
            "Доступ запрещён",
            "У вас нет прав для просмотра этой страницы.",
        )
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        return _render_error_page(
            request,
            status.HTTP_404_NOT_FOUND,
            "Страница не найдена",
            "Похоже, такой страницы больше нет или ссылка неверна.",
        )
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error")
    return _render_error_page(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Что-то пошло не так",
        "Мы уже получили информацию об ошибке. Попробуйте обновить страницу чуть позже.",
    )

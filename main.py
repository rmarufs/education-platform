# Точка входа в приложение FastAPI
import os
import logging
from functools import lru_cache
from fastapi import FastAPI, Request, status, Depends
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.gzip import GZipMiddleware
from sqlalchemy.orm import joinedload

from app.config import SECRET_KEY, PLATFORM_NAME
from app.database import init_db, SessionLocal, get_db
from app.models.course import Course
from app.models.user import User
from app.models.category import Category
from app.routers import auth, users, courses
from app.routers import modules, lessons, reviews, comments, profile, pages
from app.routers import quizzes  # QUIZ SYSTEM - RESTORED
from app.routers import admin

# Создаём папку data если её нет
os.makedirs("data", exist_ok=True)

app = FastAPI(title=PLATFORM_NAME, docs_url="/api/docs")

# ── Middleware ──────────────────────────────────────────────────────────────

# Сжатие ответов (gzip) для CSS, JS, HTML - улучшает скорость загрузки на 3-5×
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Middleware для сессий на основе куков (подписаны SECRET_KEY)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 24 * 7)

# Статические файлы (CSS, JS, изображения)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


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

app.include_router(quizzes.router)  # QUIZ SYSTEM - RESTORED
app.include_router(quizzes.dashboard_router)  # QUIZ SYSTEM - RESTORED
app.include_router(reviews.router)
app.include_router(comments.router)
app.include_router(profile.router)
app.include_router(pages.router)
app.include_router(admin.router)


# ── Главная страница ─────────────────────────────────────────────────────────

# Кэш для популярных курсов (TTL 15 минут)
_popular_courses_cache = {"data": None, "timestamp": 0}

def _get_popular_courses_cached(db):
    """Получить популярные курсы с кэшированием на 15 минут."""
    import time
    now = time.time()
    # Проверяем кэш (15 минут = 900 секунд)
    if _popular_courses_cache["data"] is not None and (now - _popular_courses_cache["timestamp"]) < 900:
        return _popular_courses_cache["data"]
    
    # Запрашиваем из БД если кэш истёк
    courses = (
        db.query(Course)
        .options(joinedload(Course.teacher), joinedload(Course.category))
        .order_by(Course.rating.desc())
        .limit(10)
        .all()
    )
    _popular_courses_cache["data"] = courses
    _popular_courses_cache["timestamp"] = now
    return courses


def _get_categories_cached(db):
    """Получить категории с кэшированием на 1 час."""
    import time
    if not hasattr(_get_categories_cached, "_cache"):
        _get_categories_cached._cache = {"data": None, "timestamp": 0}
    
    now = time.time()
    cache = _get_categories_cached._cache
    # 1 час = 3600 секунд
    if cache["data"] is not None and (now - cache["timestamp"]) < 3600:
        return cache["data"]
    
    categories = db.query(Category).order_by(Category.name).all()
    cache["data"] = categories
    cache["timestamp"] = now
    return categories


@app.get("/", response_class=HTMLResponse)
def index(request: Request, user: User | None = Depends(_get_request_user), db=Depends(get_db)):
    """Главная страница с популярными курсами."""
    popular_courses = _get_popular_courses_cached(db)
    categories = _get_categories_cached(db)
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "courses": popular_courses,
            "user": user,
            "categories": categories
        }
    )


# ── Инициализация БД при старте ──────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_db()
    print(f"✅ {PLATFORM_NAME} запущен. База данных инициализирована.")


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
    logger.exception("Unhandled application error", exc_info=exc)
    return _render_error_page(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Что-то пошло не так",
        "Мы уже получили информацию об ошибке. Попробуйте обновить страницу чуть позже.",
    )

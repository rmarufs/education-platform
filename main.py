# Точка входа в приложение FastAPI
import os
import logging
from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import joinedload

from app.config import SECRET_KEY, PLATFORM_NAME
from app.database import init_db, SessionLocal
from app.models.course import Course
from app.models.user import User
from app.routers import auth, users, courses
from app.routers import modules, lessons, quizzes, reviews, comments, profile, pages
from app.routers import admin

# Создаём папку data если её нет
os.makedirs("data", exist_ok=True)

app = FastAPI(title=PLATFORM_NAME, docs_url="/api/docs")

# Middleware для сессий на основе куков (подписаны SECRET_KEY)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 24 * 7)

# Статические файлы (CSS, JS, изображения)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


def _load_request_user(request: Request):
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
):
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

# Подключаем все роутеры
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(modules.router)
app.include_router(lessons.router)
app.include_router(quizzes.router)
app.include_router(reviews.router)
app.include_router(comments.router)
app.include_router(profile.router)
app.include_router(pages.router)
app.include_router(admin.router)


# ── Главная страница ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    db = SessionLocal()
    try:
        popular_courses = (
            db.query(Course)
            .options(joinedload(Course.teacher), joinedload(Course.category))
            .order_by(Course.rating.desc())
            .limit(6)
            .all()
        )
        user_id = request.session.get("user_id")
        user = db.query(User).filter(User.id == user_id).first() if user_id else None
        from app.models.category import Category
        categories = db.query(Category).order_by(Category.name).all()
    finally:
        db.close()

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "courses": popular_courses, "user": user, "categories": categories}
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

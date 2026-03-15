# Точка входа в приложение FastAPI
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import joinedload

from app.config import SECRET_KEY, PLATFORM_NAME
from app.database import init_db, SessionLocal
from app.models.course import Course
from app.models.module import Module
from app.models.user import User
from app.routers import auth, users, courses
from app.routers import modules, lessons, quizzes, reviews, comments, profile

# Создаём папку data если её нет
os.makedirs("data", exist_ok=True)

app = FastAPI(title=PLATFORM_NAME, docs_url="/api/docs")

# Middleware для сессий на основе куков (подписаны SECRET_KEY)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 24 * 7)

# Статические файлы (CSS, JS, изображения)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

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


# ── Главная страница ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    db = SessionLocal()
    try:
        # joinedload загружает teacher сразу — иначе DetachedInstanceError в шаблоне
        popular_courses = (
            db.query(Course)
            .options(joinedload(Course.teacher))
            .order_by(Course.rating.desc())
            .limit(6)
            .all()
        )
        user_id = request.session.get("user_id")
        user = db.query(User).filter(User.id == user_id).first() if user_id else None
        from app.models.category import Category
        categories = db.query(Category).all()
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

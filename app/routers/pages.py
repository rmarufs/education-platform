# Роутер статических страниц: О нас, Как это работает, Контакты, Поиск, Профиль преподавателя
import re
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func

from app.database import get_db
from app.deps.auth import get_user
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.category import Category
from app.models.review import Review
from app.models.progress import Progress
from app.models.contact import ContactMessage
from app.models.organization import Organization, OrganizationTeacher

router = APIRouter()
from app.ui import templates


from app.utils.text import plain_text


# ── Главная страница ─────────────────────────────────────────────────────────

# Кэш удален из-за ошибки DetachedInstanceError.
# Запрос 10 курсов отрабатывает за доли миллисекунд.
def _get_popular_courses_cached(db):
    """Получить популярные курсы из БД."""
    return (
        db.query(Course)
        .options(
            joinedload(Course.teacher)
                .selectinload(User.employer_organizations)
                .joinedload(OrganizationTeacher.organization),
            joinedload(Course.category),
        )
        .order_by(Course.rating.desc())
        .limit(10)
        .all()
    )


def invalidate_courses_cache():
    """Заглушка для обратной совместимости."""
    pass


def _get_categories_cached(db):
    """Получить категории из БД."""
    return db.query(Category).order_by(Category.name).all()


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    """Главная страница с популярными курсами."""
    user = get_user(request, db)
    popular_courses = _get_popular_courses_cached(db)
    categories = _get_categories_cached(db)

    return templates.TemplateResponse(
        "pages/index.html",
        {
            "request": request,
            "courses": popular_courses,
            "user": user,
            "categories": categories
        }
    )
# ── Страница "О нас" ────────────────────────────────────────────────────────

@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    return templates.TemplateResponse("pages/about.html", {"request": request, "user": user})


# ── Страница "Как это работает" ──────────────────────────────────────────────

@router.get("/how-it-works", response_class=HTMLResponse)
def how_it_works_page(request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    return templates.TemplateResponse("pages/how_it_works.html", {"request": request, "user": user})


# ── Страница "Контакты" ─────────────────────────────────────────────────────

@router.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    return templates.TemplateResponse("pages/contact.html", {"request": request, "user": user})


@router.post("/contact")
def contact_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
):
    name = name.strip()
    email = email.strip()
    subject = subject.strip()
    message = message.strip()

    if not name or not email or not subject or not message:
        raise HTTPException(status_code=400, detail="Заполните все поля формы")

    msg = ContactMessage(name=name, email=email, subject=subject, message=message)
    db.add(msg)
    db.commit()
    return JSONResponse({"ok": True, "message": "Сообщение отправлено!"})


# ── Поиск курсов ────────────────────────────────────────────────────────────

@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    categories = db.query(Category).order_by(Category.name).all()
    return templates.TemplateResponse("pages/search.html", {
        "request": request, "user": user, "categories": categories
    })


@router.get("/api/search")
def search_api(
    request: Request,
    q: str = "",
    category_id: int = 0,
    level: str = "",
    sort: str = "rating",
    page: int = 1,
    per_page: int = 12,
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    from app.services.search_service import perform_search
    return perform_search(
        db=db,
        user=user,
        q=q,
        category_id=category_id,
        level=level,
        sort=sort,
        page=page,
        per_page=per_page,
    )


# ── Публичный профиль преподавателя ──────────────────────────────────────────

@router.get("/teachers/{teacher_id:int}", response_class=HTMLResponse)
def teacher_profile(teacher_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    teacher = db.query(User).filter(User.id == teacher_id).first()
    if not teacher or teacher.role.value != "teacher":
        raise HTTPException(status_code=404, detail="Преподаватель не найден")

    courses = (
        db.query(Course)
        .options(joinedload(Course.teacher))
        .filter(Course.teacher_id == teacher_id)
        .order_by(Course.rating.desc())
        .all()
    )

    avg_rating = db.query(func.avg(Course.rating)).filter(
        Course.teacher_id == teacher_id, Course.rating > 0
    ).scalar()

    teacher_course_ids = [c.id for c in courses]
    if teacher_course_ids:
        from app.models.lesson import Lesson
        from app.models.module import Module
        total_students = (
            db.query(func.count(func.distinct(Progress.student_id)))
            .join(Lesson, Lesson.id == Progress.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .filter(Module.course_id.in_(teacher_course_ids))
            .scalar()
        ) or 0
    else:
        total_students = 0

    return templates.TemplateResponse("profile/teacher_profile.html", {
        "request": request,
        "user": user,
        "teacher": teacher,
        "courses": courses,
        "avg_rating": round(avg_rating or 0, 1),
        "total_students": total_students,
    })

# Роутер статических страниц: О нас, Как это работает, Контакты, Поиск, Профиль преподавателя
import re
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_user
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.category import Category
from app.models.review import Review
from app.models.progress import Progress
from app.models.contact import ContactMessage
from app.models.organization import Organization, OrganizationTeacher

router = APIRouter()
from app.ui import templates


def _plain_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]+>", "", value).strip()
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
    # Данные текущего пользователя
    from app.dependencies import get_user
    from app.models.organization import OrganizationStudent
    user = get_user(request, db)
    user_is_student = bool(user and user.is_student)
    user_org_id = None
    if user_is_student:
        student_org_link = db.query(OrganizationStudent).filter(OrganizationStudent.student_id == user.id).first()
        if student_org_link:
            user_org_id = student_org_link.organization_id

    query = db.query(Course).options(
        joinedload(Course.teacher),
        joinedload(Course.category),
        selectinload(Course.modules),
    )

    if q:
        query = query.filter(
            (Course.title.ilike(f"%{q}%")) | (Course.description.ilike(f"%{q}%"))
        )
    if category_id:
        query = query.filter(Course.category_id == category_id)
    if level:
        query = query.filter(Course.level == level)

    # Сортировка
    if sort == "newest":
        query = query.order_by(Course.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(Course.created_at.asc())
    else:
        query = query.order_by(Course.rating.desc())

    total = query.count()
    courses = query.offset((page - 1) * per_page).limit(per_page).all()

    from app.models.organization import Organization
    organizations = []
    
    # Поиск организаций: если запрос пуст, показываем популярные (например, первые 3 одобренные)
    org_query = db.query(Organization).filter(Organization.status == "approved")
    if q:
        org_query = org_query.filter(Organization.name.ilike(f"%{q}%"))
        orgs = org_query.limit(10).all()
    else:
        orgs = org_query.limit(3).all()

    organizations = [
        {
            "id": o.id,
            "name": o.name,
            "description": _plain_text(o.description)[:120] if o.description else "Организация",
            "logo_url": o.logo_url
        }
        for o in orgs
    ]

    # Поиск преподавателей
    teachers_result = []
    if q:
        found_teachers = (
            db.query(User)
            .filter(
                User.role == UserRole.teacher,
                User.is_active == True,
                User.name.ilike(f"%{q}%"),
            )
            .limit(8)
            .all()
        )
        teacher_ids = [t.id for t in found_teachers]
        org_map = {}
        if teacher_ids:
            links = (
                db.query(OrganizationTeacher)
                .options(joinedload(OrganizationTeacher.organization))
                .filter(
                    OrganizationTeacher.teacher_id.in_(teacher_ids),
                    OrganizationTeacher.status == "accepted",
                )
                .all()
            )
            for link in links:
                org_map[link.teacher_id] = link
        for t in found_teachers:
            org_link = org_map.get(t.id)
            teachers_result.append({
                "id": t.id,
                "name": t.name,
                "bio": (t.bio[:100] if t.bio else None),
                "avatar": getattr(t, "avatar_url", None),
                "org_name": org_link.organization.name if org_link else None,
                "org_id": org_link.organization_id if org_link else None,
            })

    import logging
    logger = logging.getLogger("search_api")
    logger.info(f"Search query: q='{q}', category_id={category_id}, level='{level}', sort='{sort}', user_is_student={user_is_student}")
    logger.info(f"Results found: courses={total}, organizations={len(organizations)}, teachers={len(teachers_result)}")

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "courses": [
            {
                "id": c.id,
                "title": c.title,
                "description": _plain_text(c.description)[:120],
                "image": c.image,
                "teacher_name": c.teacher.name,
                "rating": c.rating,
                "level": c.level,
                "category": c.category.name if c.category else None,
                "created_at": c.created_at.strftime("%d.%m.%Y"),
                "modules_count": len(c.modules) if c.modules else 0,
                "teacher_orgs": [{"id": ot.organization_id, "name": ot.organization.name} for ot in c.teacher.employer_organizations if ot.status == 'accepted'] if hasattr(c.teacher, 'employer_organizations') else []
            }
            for c in courses
        ],
        "organizations": organizations,
        "teachers": teachers_result,
        "user_is_student": user_is_student,
        "user_org_id": user_org_id,
    }


# ── Публичный профиль преподавателя ──────────────────────────────────────────

@router.get("/teachers/{teacher_id}", response_class=HTMLResponse)
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

# Роутер админ-панели
import os
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.progress import Progress

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


def get_admin(request: Request, db: Session) -> User:
    """Проверяет, что текущий пользователь — админ."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user


# ── Главная админ-панели ─────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def admin_index(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    stats = {
        "total_users": db.query(func.count(User.id)).scalar(),
        "students": db.query(func.count(User.id)).filter(User.role == UserRole.student).scalar(),
        "teachers": db.query(func.count(User.id)).filter(User.role == UserRole.teacher).scalar(),
        "pending": db.query(func.count(User.id)).filter(User.role == UserRole.teacher_pending).scalar(),
        "courses": db.query(func.count(Course.id)).scalar(),
    }

    return templates.TemplateResponse("admin/index.html", {
        "request": request,
        "user": admin,
        "stats": stats,
    })


# ── Заявки преподавателей ────────────────────────────────────────────────────

@router.get("/teachers", response_class=HTMLResponse)
def admin_teachers(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    pending_teachers = (
        db.query(User)
        .filter(User.role == UserRole.teacher_pending)
        .order_by(User.created_at.desc())
        .all()
    )

    return templates.TemplateResponse("admin/teachers.html", {
        "request": request,
        "user": admin,
        "teachers": pending_teachers,
    })


@router.post("/teachers/{user_id}/approve")
def approve_teacher(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    teacher = db.query(User).filter(User.id == user_id, User.role == UserRole.teacher_pending).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    teacher.role = UserRole.teacher
    db.commit()

    return RedirectResponse("/admin/teachers", status_code=302)


@router.post("/teachers/{user_id}/reject")
def reject_teacher(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    teacher = db.query(User).filter(User.id == user_id, User.role == UserRole.teacher_pending).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    # Удаляем документ, если есть
    if teacher.documents:
        file_path = teacher.documents.lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)
        teacher.documents = None

    teacher.role = UserRole.student
    db.commit()

    return RedirectResponse("/admin/teachers", status_code=302)


# ── Управление пользователями ────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
def admin_users(request: Request, q: str = "", db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    query = db.query(User).order_by(User.created_at.desc())
    if q:
        query = query.filter(
            (User.name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )
    users = query.all()

    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "user": admin,
        "users_list": users,
        "q": q,
    })


@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404)

    # Нельзя заблокировать самого себя
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать свой аккаунт")

    target.is_active = not target.is_active
    db.commit()

    return RedirectResponse("/admin/users", status_code=302)


@router.post("/users/{user_id}/delete")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404)

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить свой аккаунт")

    # Удаляем документ, если есть
    if target.documents:
        file_path = target.documents.lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)

    db.delete(target)
    db.commit()

    return RedirectResponse("/admin/users", status_code=302)


# ── Управление курсами ──────────────────────────────────────────────────────

@router.get("/courses", response_class=HTMLResponse)
def admin_courses(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    courses = (
        db.query(Course)
        .options(joinedload(Course.teacher))
        .order_by(Course.created_at.desc())
        .all()
    )

    # Подсчитаем кол-во студентов для каждого курса
    course_data = []
    for course in courses:
        # Считаем уникальных студентов через Progress
        from app.models.module import Module
        from app.models.lesson import Lesson
        lesson_ids = (
            db.query(Lesson.id)
            .join(Module, Module.id == Lesson.module_id)
            .filter(Module.course_id == course.id)
            .all()
        )
        lesson_id_list = [lid[0] for lid in lesson_ids]

        student_count = 0
        if lesson_id_list:
            student_count = (
                db.query(func.count(func.distinct(Progress.student_id)))
                .filter(Progress.lesson_id.in_(lesson_id_list))
                .scalar()
            ) or 0

        course_data.append({
            "course": course,
            "student_count": student_count,
        })

    return templates.TemplateResponse("admin/courses.html", {
        "request": request,
        "user": admin,
        "course_data": course_data,
    })


@router.post("/courses/{course_id}/delete")
def admin_delete_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404)

    db.delete(course)
    db.commit()

    return RedirectResponse("/admin/courses", status_code=302)

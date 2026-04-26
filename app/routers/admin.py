# Роутер админ-панели
import os
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import csv
import io
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app.database import get_db
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.progress import Progress
from app.models.module import Module
from app.models.lesson import Lesson

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
        .options(joinedload(Course.teacher), joinedload(Course.modules).joinedload(Module.lessons))
        .order_by(Course.created_at.desc())
        .all()
    )

    course_ids = [course.id for course in courses]
    student_count_map = {
        course_id: count
        for course_id, count in (
            db.query(
                Module.course_id,
                func.count(func.distinct(Progress.student_id)),
            )
            .join(Lesson, Lesson.module_id == Module.id)
            .outerjoin(Progress, Progress.lesson_id == Lesson.id)
            .filter(Module.course_id.in_(course_ids))
            .group_by(Module.course_id)
            .all()
        )
    } if course_ids else {}

    course_data = [
        {
            "course": course,
            "student_count": student_count_map.get(course.id, 0),
        }
        for course in courses
    ]

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


# ── Экспорт данных ──────────────────────────────────────────────────────────

@router.get("/export-assessments")
def export_assessments(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)
    
    from app.models.assessment import AssessmentResponse
    responses = db.query(AssessmentResponse).options(joinedload(AssessmentResponse.user)).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовки CSV
    writer.writerow([
        "ID пользователя", 
        "Имя", 
        "Email", 
        "Q1: Опыт онлайн-курсов (1-Да,много; 2-Да,1-2; 3-Нет)", 
        "Q2: Частота самообучения (1-Часто; 2-Иногда; 3-Редко)", 
        "Q3: Доводит до конца (1-Всегда; 2-Иногда; 3-Редко)", 
        "Q4: Комфорт без наставника (1-Комфортно; 2-Нормально; 3-Сложно)", 
        "Q5: Трудности (1-Мотивация; 2-Сложность; 3-Нет трудностей)",
        "Дата ответа"
    ])
    
    for r in responses:
        writer.writerow([
            r.user.id if r.user else "",
            r.user.name if r.user else "Удален",
            r.user.email if r.user else "",
            r.q1_answer,
            r.q2_answer,
            r.q3_answer,
            r.q4_answer,
            r.q5_answer,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
        ])
    
    # Возвращаем файл
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), 
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assessments.csv"}
    )

# Роутер модулей курса (только для преподавателей)
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.module import Module

router = APIRouter(prefix="/modules")


def get_teacher(request: Request, db: Session) -> User:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role.value != "teacher":
        raise HTTPException(status_code=403, detail="Только преподаватели")
    return user


# ── Создать модуль ─────────────────────────────────────────────
@router.post("/create")
def create_module(
    request: Request,
    course_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    teacher = get_teacher(request, db)
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    # Определяем порядковый номер
    max_order = db.query(Module).filter(Module.course_id == course_id).count()
    module = Module(
        course_id=course_id,
        title=title,
        description=description or None,
        order_index=max_order,
    )
    db.add(module)
    db.commit()
    return RedirectResponse(f"/courses/{course_id}/manage", status_code=302)


# ── Редактировать модуль ───────────────────────────────────────
@router.post("/{module_id}/edit")
def edit_module(
    module_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    teacher = get_teacher(request, db)
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404)
    # Проверяем что это курс этого преподавателя
    course = db.query(Course).filter(Course.id == module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    module.title = title
    module.description = description or None
    db.commit()
    return RedirectResponse(f"/courses/{module.course_id}/manage", status_code=302)


# ── Удалить модуль ─────────────────────────────────────────────
@router.post("/{module_id}/delete")
def delete_module(
    module_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    teacher = get_teacher(request, db)
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404)
    course = db.query(Course).filter(Course.id == module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    course_id = module.course_id
    db.delete(module)
    db.commit()
    return RedirectResponse(f"/courses/{course_id}/manage", status_code=302)

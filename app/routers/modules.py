# Роутер модулей курса (только для преподавателей)
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_teacher
from app.models.user import User
from app.models.course import Course
from app.models.module import Module

router = APIRouter(prefix="/modules")


def _get_manageable_course(course_id: int, user: User, db: Session) -> Course | None:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return None
    if user.is_admin or course.teacher_id == user.id:
        return course
    return None


# ── Создать модуль ─────────────────────────────────────────────
@router.post("/create")
def create_module(
    request: Request,
    course_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Введите название курса")

    teacher = require_teacher(request, db)
    course = _get_manageable_course(course_id, teacher, db)
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
@router.post("/{module_id:int}/edit")
def edit_module(
    module_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Введите название курса")

    teacher = require_teacher(request, db)
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404)
    # Проверяем что это курс этого преподавателя
    course = _get_manageable_course(module.course_id, teacher, db)
    if not course:
        raise HTTPException(status_code=403)

    module.title = title
    module.description = description or None
    db.commit()
    return RedirectResponse(f"/courses/{module.course_id}/manage", status_code=302)


# ── Удалить модуль ─────────────────────────────────────────────
@router.post("/{module_id:int}/delete")
def delete_module(
    module_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404)
    course = _get_manageable_course(module.course_id, teacher, db)
    if not course:
        raise HTTPException(status_code=403)

    course_id = module.course_id
    db.delete(module)
    db.commit()
    return RedirectResponse(f"/courses/{course_id}/manage", status_code=302)

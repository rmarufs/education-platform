# Роутер уроков
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.user import User
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.material import Material
from app.models.progress import Progress
from app.models.comment import Comment

router = APIRouter(prefix="/lessons")
templates = Jinja2Templates(directory="templates")


def get_user(request: Request, db: Session):
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(User).filter(User.id == uid).first()


def require_teacher(request: Request, db: Session):
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role.value != "teacher":
        raise HTTPException(status_code=403)
    return user


# ── Страница урока ─────────────────────────────────────────────
@router.get("/{lesson_id}", response_class=HTMLResponse)
def lesson_page(lesson_id: int, request: Request, db: Session = Depends(get_db)):
    lesson = (
        db.query(Lesson)
        .options(
            joinedload(Lesson.module),
            joinedload(Lesson.materials),
            joinedload(Lesson.quiz),
            joinedload(Lesson.comments).joinedload(Comment.author),
            joinedload(Lesson.comments).joinedload(Comment.replies).joinedload(Comment.author),
        )
        .filter(Lesson.id == lesson_id)
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    user = get_user(request, db)

    # Прогресс студента
    progress = None
    if user and user.role.value == "student":
        progress = db.query(Progress).filter(
            Progress.student_id == user.id,
            Progress.lesson_id == lesson_id
        ).first()

    # Все уроки курса для навигации
    from app.models.course import Course
    course = db.query(Course).filter(
        Course.id == lesson.module.course_id
    ).options(joinedload(Course.modules).joinedload(Module.lessons)).first()

    return templates.TemplateResponse("lesson_page.html", {
        "request": request,
        "lesson": lesson,
        "user": user,
        "progress": progress,
        "course": course,
        "top_comments": [c for c in lesson.comments if c.parent_comment_id is None],
    })


# ── Создать урок ───────────────────────────────────────────────
@router.post("/create")
def create_lesson(
    request: Request,
    module_id: int = Form(...),
    title: str = Form(...),
    video_url: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404)
    from app.models.course import Course
    course = db.query(Course).filter(Course.id == module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    max_order = db.query(Lesson).filter(Lesson.module_id == module_id).count()
    lesson = Lesson(
        module_id=module_id,
        title=title,
        video_url=video_url or None,
        description=description or None,
        order_index=max_order,
    )
    db.add(lesson)
    db.commit()
    return RedirectResponse(f"/courses/{module.course_id}/manage", status_code=302)


# ── Редактировать урок ─────────────────────────────────────────
@router.post("/{lesson_id}/edit")
def edit_lesson(
    lesson_id: int,
    request: Request,
    title: str = Form(...),
    video_url: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404)
    from app.models.course import Course
    course = db.query(Course).filter(Course.id == lesson.module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    lesson.title = title
    lesson.video_url = video_url or None
    lesson.description = description or None
    db.commit()
    return RedirectResponse(f"/courses/{lesson.module.course_id}/manage", status_code=302)


# ── Добавить материал к уроку ──────────────────────────────────
@router.post("/{lesson_id}/material")
def add_material(
    lesson_id: int,
    request: Request,
    title: str = Form(""),
    file_url: str = Form(...),
    file_type: str = Form("pdf"),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404)
    from app.models.course import Course
    course = db.query(Course).filter(Course.id == lesson.module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    material = Material(lesson_id=lesson_id, title=title, file_url=file_url, file_type=file_type)
    db.add(material)
    db.commit()
    return RedirectResponse(f"/courses/{lesson.module.course_id}/manage", status_code=302)


# ── Отметить урок завершённым (студент) ───────────────────────
@router.post("/{lesson_id}/complete")
def complete_lesson(lesson_id: int, request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role.value != "student":
        raise HTTPException(status_code=403)

    progress = db.query(Progress).filter(
        Progress.student_id == uid, Progress.lesson_id == lesson_id
    ).first()

    if not progress:
        progress = Progress(student_id=uid, lesson_id=lesson_id, completed=True, completed_at=datetime.utcnow())
        db.add(progress)
    else:
        progress.completed = True
        progress.completed_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(f"/lessons/{lesson_id}", status_code=302)

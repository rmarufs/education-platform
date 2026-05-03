# Роутер уроков
import os
import uuid
import shutil
import base64
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models.user import User
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.material import Material
from app.models.progress import Progress
from app.models.comment import Comment
from app.models.course import Course
from app.quiz_flow import lesson_quiz_unlocked, next_after_lesson

router = APIRouter(prefix="/lessons")
templates = Jinja2Templates(directory="templates")
def obfuscate_yt(s: str) -> str:
    if not s:
        return ""
    # Reverse string + Caesar shift + Base64
    shifted = "".join(chr(ord(c) + 3) for c in s[::-1])
    return base64.b64encode(shifted.encode("utf-8")).decode("utf-8")

templates.env.filters["b64encode"] = obfuscate_yt
MATERIAL_UPLOAD_DIR = os.path.join("static", "materials")
MATERIAL_UPLOAD_MAX_BYTES = 15 * 1024 * 1024
MATERIAL_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx"}


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
    if not user or user.role.value not in ("teacher", "admin"):
        raise HTTPException(status_code=403)
    return user


def _validate_material_upload(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in MATERIAL_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Недопустимый тип файла")

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > MATERIAL_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Файл слишком большой")
    return ext


def _save_uploaded_files(files, lesson_id, db):
    """Сохраняет загруженные файлы как материалы урока."""
    if not files:
        return
    os.makedirs(MATERIAL_UPLOAD_DIR, exist_ok=True)
    for file in files:
        if not file.filename:
            continue
        ext = _validate_material_upload(file)
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        save_path = os.path.join(MATERIAL_UPLOAD_DIR, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        material = Material(
            lesson_id=lesson_id,
            title=file.filename,
            file_url="/" + save_path,
            file_type=ext,
        )
        db.add(material)
    db.commit()


# ── Создать урок ───────────────────────────────────────────────
@router.post("/create")
async def create_lesson(
    request: Request,
    module_id: int = Form(...),
    title: str = Form(...),
    video_url: str = Form(""),
    description: str = Form(""),
    files: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Введите название урока")
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404)
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
    db.refresh(lesson)

    # Сохраняем загруженные файлы
    _save_uploaded_files(files, lesson.id, db)

    return RedirectResponse(f"/courses/{module.course_id}/manage", status_code=302)


# ── Страница урока ─────────────────────────────────────────────
@router.get("/{lesson_id}", response_class=HTMLResponse)
def lesson_page(lesson_id: int, request: Request, db: Session = Depends(get_db)):
    lesson = (
        db.query(Lesson)
        .options(
            joinedload(Lesson.module),
            selectinload(Lesson.materials),
            joinedload(Lesson.quiz),
            selectinload(Lesson.comments).joinedload(Comment.author),
            selectinload(Lesson.comments).selectinload(Comment.replies).joinedload(Comment.author),
        )
        .filter(Lesson.id == lesson_id)
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    user = get_user(request, db)

    course = (
        db.query(Course)
        .options(selectinload(Course.modules).selectinload(Module.lessons))
        .filter(Course.id == lesson.module.course_id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    course_lesson_ids = [
        course_lesson.id
        for module in course.modules
        for course_lesson in module.lessons
    ]

    # Прогресс студента
    progress = None
    progress_data = {}
    lesson_quiz_visible = False
    continue_url = None
    if user and user.role.value == "student":
        progress = db.query(Progress).filter(
            Progress.student_id == user.id,
            Progress.lesson_id == lesson_id
        ).first()
        all_progress = (
            db.query(Progress)
            .filter(
                Progress.student_id == user.id,
                Progress.lesson_id.in_(course_lesson_ids),
            )
            .all()
        )
        progress_data = {p.lesson_id: p.completed for p in all_progress}
        lesson_quiz_visible = bool(lesson.quiz and lesson_quiz_unlocked(db, user.id, lesson))
        if progress and progress.completed:
            continue_url = next_after_lesson(db, user.id, lesson.id)

    return templates.TemplateResponse("lesson_page.html", {
        "request": request,
        "lesson": lesson,
        "user": user,
        "progress": progress,
        "progress_data": progress_data,
        "lesson_quiz_visible": lesson_quiz_visible,
        "continue_url": continue_url,
        "course": course,
        "top_comments": [c for c in lesson.comments if c.parent_comment_id is None],
    })


# ── Редактировать урок ─────────────────────────────────────────
@router.post("/{lesson_id}/edit")
async def edit_lesson(
    lesson_id: int,
    request: Request,
    title: str = Form(...),
    video_url: str = Form(""),
    description: str = Form(""),
    files: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Введите название урока")
    lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404)
    course = db.query(Course).filter(Course.id == lesson.module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    lesson.title = title
    lesson.video_url = video_url or None
    lesson.description = description or None
    db.commit()

    # Сохраняем новые загруженные файлы
    _save_uploaded_files(files, lesson.id, db)

    return RedirectResponse(f"/courses/{lesson.module.course_id}/manage", status_code=302)


# ── Удалить урок ───────────────────────────────────────────────
@router.post("/{lesson_id}/delete")
def delete_lesson(lesson_id: int, request: Request, db: Session = Depends(get_db)):
    teacher = require_teacher(request, db)
    lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404)
    course = db.query(Course).filter(Course.id == lesson.module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403, detail="Not authorized to delete this lesson")
    
    course_id = lesson.module.course_id
    db.delete(lesson)
    db.commit()
    return RedirectResponse(f"/courses/{course_id}/manage", status_code=302)


# ── Добавить материал к уроку (через URL) ──────────────────────
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
    course = db.query(Course).filter(Course.id == lesson.module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    material = Material(lesson_id=lesson_id, title=title, file_url=file_url, file_type=file_type)
    db.add(material)
    db.commit()
    return RedirectResponse(f"/courses/{lesson.module.course_id}/manage", status_code=302)


# ── Загрузить файл к уроку ─────────────────────────────────────
@router.post("/{lesson_id}/upload")
async def upload_lesson_material(
    lesson_id: int,
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    teacher = require_teacher(request, db)
    lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404)
    course = db.query(Course).filter(Course.id == lesson.module.course_id, Course.teacher_id == teacher.id).first()
    if not course:
        raise HTTPException(status_code=403)

    _save_uploaded_files(files, lesson.id, db)
    return RedirectResponse(f"/lessons/{lesson_id}", status_code=302)


# ── Отметить урок завершённым (студент) ───────────────────────
@router.post("/{lesson_id}/complete")
def complete_lesson(lesson_id: int, request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role.value != "student":
        raise HTTPException(status_code=403)

    lesson_exists = db.query(Lesson.id).filter(Lesson.id == lesson_id).first()
    if not lesson_exists:
        raise HTTPException(status_code=404, detail="Урок не найден")

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
    return RedirectResponse(next_after_lesson(db, user.id, lesson_id), status_code=302)


@router.get("/{lesson_id}/continue")
def continue_lesson(lesson_id: int, request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/login", status_code=302)

    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role.value != "student":
        raise HTTPException(status_code=403)

    progress = db.query(Progress).filter(
        Progress.student_id == uid,
        Progress.lesson_id == lesson_id,
        Progress.completed == True,  # noqa: E712
    ).first()
    if not progress:
        return RedirectResponse(f"/lessons/{lesson_id}", status_code=302)

    return RedirectResponse(next_after_lesson(db, user.id, lesson_id), status_code=302)

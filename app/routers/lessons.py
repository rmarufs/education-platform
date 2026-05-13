# Роутер уроков
import os
import uuid
import shutil
import base64
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_user, is_student, is_teacher, is_admin
from app.models.user import User
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.material import Material
from app.models.progress import Progress
from app.models.comment import Comment
from app.models.course import Course
from app.models.review import Review
from app.quiz_flow import lesson_quiz_unlocked, next_after_lesson

router = APIRouter(prefix="/lessons")
from app.ui import templates
MATERIAL_UPLOAD_DIR = os.path.join("static", "materials")
MATERIAL_UPLOAD_MAX_BYTES = 15 * 1024 * 1024
MATERIAL_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx"}


def require_teacher(request: Request, db: Session):
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    if not (is_teacher(user) or is_admin(user)):
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
        video_url=video_url.strip() if video_url and video_url.strip() else None,
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

    # Проверка прав доступа (IDOR Protection)
    if not user:
        return RedirectResponse("/login", status_code=302)
    
    if user.is_admin:
        pass # Администратор имеет полный доступ
    elif user.is_teacher:
        if course.teacher_id != user.id:
            raise HTTPException(status_code=403, detail="Доступ запрещён. Вы не являетесь преподавателем этого курса.")
    elif user.is_student:
        # TODO: Здесь должна быть логика проверки записи (Enrollment) на курс.
        # Поскольку таблица Enrollment пока не создана, мы используем заглушку is_enrolled = True.
        # После создания таблицы: is_enrolled = db.query(Enrollment).filter(...).first()
        is_enrolled = True 
        if not is_enrolled:
            raise HTTPException(status_code=403, detail="Доступ запрещён. Вы не записаны на этот курс. Перейдите к оплате.")
    else:
        raise HTTPException(status_code=403, detail="Доступ запрещён.")

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
    if is_student(user):
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
            
        teacher_id = course.teacher_id
        has_reviewed = db.query(Review).filter(
            Review.student_id == user.id,
            Review.teacher_id == teacher_id
        ).first() is not None

        if not has_reviewed:
            completed_teacher_lessons = (
                db.query(func.count(Progress.id))
                .join(Lesson, Progress.lesson_id == Lesson.id)
                .join(Module, Lesson.module_id == Module.id)
                .join(Course, Module.course_id == Course.id)
                .filter(
                    Progress.student_id == user.id,
                    Progress.completed == True,
                    Course.teacher_id == teacher_id
                )
                .scalar()
            )
            if completed_teacher_lessons >= 2:
                show_review_form = True

    return templates.TemplateResponse("lessons/lesson_page.html", {
        "request": request,
        "lesson": lesson,
        "user": user,
        "progress": progress,
        "progress_data": progress_data,
        "lesson_quiz_visible": lesson_quiz_visible,
        "continue_url": continue_url,
        "show_review_form": locals().get('show_review_form', False),
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
    lesson.video_url = video_url.strip() if video_url and video_url.strip() else None
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
    if not is_student(user):
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
    if not is_student(user):
        raise HTTPException(status_code=403)

    progress = db.query(Progress).filter(
        Progress.student_id == uid,
        Progress.lesson_id == lesson_id,
        Progress.completed == True,  # noqa: E712
    ).first()
    if not progress:
        return RedirectResponse(f"/lessons/{lesson_id}", status_code=302)

    return RedirectResponse(next_after_lesson(db, user.id, lesson_id), status_code=302)

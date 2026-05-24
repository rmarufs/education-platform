# Роутер уроков
import os
import uuid
import shutil
import base64
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func

from app.database import get_db
from app.dependencies import can_access_course_content, get_user, is_student, is_teacher, is_admin
from app.models.user import User
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.material import Material
from app.models.progress import Progress
from app.models.comment import Comment
from app.models.course import Course
from app.models.review import Review
from app.course_flow import next_after_lesson
from app.utils.image import upload_lesson_image
from app.utils.uploads import validate_upload_file

router = APIRouter(prefix="/lessons")
from app.ui import templates
MATERIAL_UPLOAD_DIR = os.path.join("static", "materials")
MATERIAL_UPLOAD_MAX_BYTES = 15 * 1024 * 1024
MATERIAL_EXTENSIONS = {"pdf", "doc", "docx"}
LESSON_COVER_MAX_BYTES = 5 * 1024 * 1024
LESSON_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def require_teacher(request: Request, db: Session):
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    if not (is_teacher(user) or is_admin(user)):
        raise HTTPException(status_code=403)
    return user


def _get_manageable_course(course_id: int, user: User, db: Session) -> Course | None:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return None
    if is_admin(user) or course.teacher_id == user.id:
        return course
    return None


def _validate_material_upload(file: UploadFile) -> str:
    upload = validate_upload_file(
        file,
        allowed_extensions=MATERIAL_EXTENSIONS,
        max_bytes=MATERIAL_UPLOAD_MAX_BYTES,
        missing_message="Файл не выбран",
    )
    return upload.extension.lstrip(".")


def _validate_lesson_cover_upload(file: UploadFile) -> None:
    if not file or not file.filename:
        return
    validate_upload_file(
        file,
        allowed_extensions=LESSON_COVER_EXTENSIONS,
        max_bytes=LESSON_COVER_MAX_BYTES,
        invalid_type_message="Разрешены только JPG, JPEG, PNG и WEBP",
        too_large_message="Изображение должно быть не больше 5MB",
    )


def _save_uploaded_files(files, lesson_id, db):
    """Сохраняет загруженные файлы как материалы урока."""
    if not files:
        return
    os.makedirs(MATERIAL_UPLOAD_DIR, exist_ok=True)
    for file in files:
        if not file.filename:
            continue
        upload = validate_upload_file(
            file,
            allowed_extensions=MATERIAL_EXTENSIONS,
            max_bytes=MATERIAL_UPLOAD_MAX_BYTES,
            missing_message="Файл не выбран",
        )
        ext = upload.extension.lstrip(".")
        filename = f"{uuid.uuid4().hex}_{upload.safe_filename}"
        save_path = os.path.join(MATERIAL_UPLOAD_DIR, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        material = Material(
            lesson_id=lesson_id,
            title=upload.original_filename,
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
    cover: UploadFile = File(None),
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
    course = _get_manageable_course(module.course_id, teacher, db)
    if not course:
        raise HTTPException(status_code=403)
    video_url_value = video_url.strip() if video_url and video_url.strip() else None
    has_cover_upload = bool(cover and cover.filename)
    if video_url_value and has_cover_upload:
        raise HTTPException(status_code=400, detail="Можно добавить либо видео, либо картинку")
    if has_cover_upload:
        _validate_lesson_cover_upload(cover)

    max_order = db.query(Lesson).filter(Lesson.module_id == module_id).count()
    lesson = Lesson(
        module_id=module_id,
        title=title,
        video_url=video_url_value,
        description=description or None,
        order_index=max_order,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    if has_cover_upload:
        cover_url = upload_lesson_image(
            cover.file,
            public_id=f"lessons/lesson_{lesson.id}",
        )
        if cover_url:
            lesson.cover_url = cover_url
            db.commit()

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
    
    if not can_access_course_content(user, course, db):
        if user.is_teacher:
            raise HTTPException(status_code=403, detail="Доступ запрещён. Вы не являетесь преподавателем этого курса.")
        if user.is_student:
            raise HTTPException(status_code=403, detail="Доступ запрещён. Вы не записаны на этот курс. Перейдите к оплате.")
        raise HTTPException(status_code=403, detail="Доступ запрещён.")

    course_lesson_ids = [
        course_lesson.id
        for module in course.modules
        for course_lesson in module.lessons
    ]
    next_lesson_url = f"/courses/{course.id}"
    for index, course_lesson_id in enumerate(course_lesson_ids):
        if course_lesson_id == lesson_id and index < len(course_lesson_ids) - 1:
            next_lesson_url = f"/lessons/{course_lesson_ids[index + 1]}"
            break

    # Прогресс студента
    progress = None
    progress_data = {}
    lesson_test_visible = False
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
        lesson_test_visible = bool(progress and progress.completed)
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
        "lesson_test_visible": lesson_test_visible,
        "continue_url": continue_url,
        "next_lesson_url": next_lesson_url,
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
    cover: UploadFile = File(None),
    remove_cover: str = Form("0"),
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
    course = _get_manageable_course(lesson.module.course_id, teacher, db)
    if not course:
        raise HTTPException(status_code=403)
    video_url_value = video_url.strip() if video_url and video_url.strip() else None
    has_cover_upload = bool(cover and cover.filename)
    if video_url_value and has_cover_upload:
        raise HTTPException(status_code=400, detail="Можно добавить либо видео, либо картинку")
    if has_cover_upload:
        _validate_lesson_cover_upload(cover)

    lesson.title = title
    lesson.video_url = video_url_value
    lesson.description = description or None
    if video_url_value or remove_cover == "1":
        lesson.cover_url = None
    if has_cover_upload:
        cover_url = upload_lesson_image(
            cover.file,
            public_id=f"lessons/lesson_{lesson.id}",
        )
        if cover_url:
            lesson.cover_url = cover_url
            lesson.video_url = None
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
    course = _get_manageable_course(lesson.module.course_id, teacher, db)
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
    course = _get_manageable_course(lesson.module.course_id, teacher, db)
    if not course:
        raise HTTPException(status_code=403)
    file_type = file_type.lower().strip()
    if file_type not in MATERIAL_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Недопустимый тип файла")

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
    course = _get_manageable_course(lesson.module.course_id, teacher, db)
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

    lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    course = db.query(Course).filter(Course.id == lesson.module.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    if not can_access_course_content(user, course, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён.")

    progress = db.query(Progress).filter(
        Progress.student_id == uid, Progress.lesson_id == lesson_id
    ).first()

    if not progress:
        progress = Progress(student_id=uid, lesson_id=lesson_id, completed=True, completed_at=datetime.utcnow())
        db.add(progress)
    elif not progress.completed:
        progress.completed = True
        progress.completed_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        progress = db.query(Progress).filter(Progress.student_id == uid, Progress.lesson_id == lesson_id).first()
        if progress and not progress.completed:
            progress.completed = True
            progress.completed_at = datetime.utcnow()
            db.commit()
    return RedirectResponse(f"/lessons/{lesson_id}", status_code=302)


@router.get("/{lesson_id}/continue")
def continue_lesson(lesson_id: int, request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/login", status_code=302)

    user = db.query(User).filter(User.id == uid).first()
    if not is_student(user):
        raise HTTPException(status_code=403)

    lesson = db.query(Lesson).options(joinedload(Lesson.module)).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    course = db.query(Course).filter(Course.id == lesson.module.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    if not can_access_course_content(user, course, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён.")

    progress = db.query(Progress).filter(
        Progress.student_id == uid,
        Progress.lesson_id == lesson_id,
        Progress.completed == True,  # noqa: E712
    ).first()
    if not progress:
        return RedirectResponse(f"/lessons/{lesson_id}", status_code=302)

    return RedirectResponse(next_after_lesson(db, user.id, lesson_id), status_code=302)

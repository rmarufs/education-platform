# Роутер профиля пользователя
import logging

logger = logging.getLogger(__name__)

import cloudinary
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from app.database import get_db
from app.deps.auth import get_user
from app.models.course import Course
from app.models.progress import Progress
from app.models.review import Review
from app.models.lesson import Lesson
from app.models.module import Module
from app.models.organization import Organization
from app.utils.image import compress_and_upload_avatar
from app.utils.uploads import validate_upload_file

router = APIRouter()
from app.ui import templates

AVATAR_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
AVATAR_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)


@router.post("/profile/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    if not user:
        return JSONResponse({"success": False, "error": "User not found"}, status_code=404)

    logger.info(f"Avatar upload started for user {user.id}")

    try:
        validate_upload_file(
            file,
            allowed_extensions=AVATAR_ALLOWED_EXTS,
            max_bytes=AVATAR_MAX_BYTES,
            invalid_type_message="Разрешены только JPG, JPEG, PNG и WEBP",
            too_large_message="Файл не должен превышать 10 МБ",
        )
    except HTTPException as exc:
        logger.warning(f"Invalid avatar upload: {file.filename}, {file.content_type}, {exc.detail}")
        return JSONResponse(
            {"success": False, "error": exc.detail},
            status_code=400,
        )

    file_bytes = await file.read()

    try:
        avatar_url = compress_and_upload_avatar(file_bytes, user.id)
        logger.info(f"Cloudinary result: {avatar_url}")
    except Exception as exc:
        logger.error(f"Avatar upload failed: {exc}")
        return JSONResponse(
            {"success": False, "error": f"Ошибка загрузки: {exc}"},
            status_code=500,
        )

    user.avatar_url = avatar_url
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if org:
            org.logo_url = avatar_url
    db.commit()
    
    logger.info(f"Avatar saved: {user.avatar_url}")

    return JSONResponse({"success": True, "url": avatar_url})


@router.delete("/profile/avatar")
async def delete_avatar(
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

    if not user:
        return JSONResponse({"success": False, "error": "User not found"}, status_code=404)

    # Удаляем из Cloudinary (public_id совпадает с тем, что использовали при загрузке)
    try:
        import cloudinary.uploader as _uploader
        _uploader.destroy(f"avatars/user_{user.id}", invalidate=True, resource_type="image")
    except Exception:
        pass  # Не блокируем удаление из БД, если Cloudinary недоступен

    user.avatar_url = None
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if org:
            org.logo_url = None
    db.commit()

    return JSONResponse({"success": True})



@router.get("/profile", response_class=HTMLResponse)
def profile(request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        return RedirectResponse("/login", status_code=302)

    if not user:
        request.session.clear()
        return RedirectResponse("/login", status_code=302)

    context = {"request": request, "user": user}

    if user.is_teacher:
        # Курсы преподавателя с количеством студентов (упрощённо — без записи)
        courses = (
            db.query(Course)
            .filter(Course.teacher_id == user.id)
            .options(joinedload(Course.modules).joinedload(Module.lessons))
            .all()
        )
        context["courses"] = courses

    elif user.is_student:
        # Пройденные уроки
        completed = (
            db.query(Progress)
            .options(joinedload(Progress.lesson).joinedload(Lesson.module))
            .filter(Progress.student_id == user.id, Progress.completed == True)  # noqa: E712
            .all()
        )
        completed_lesson_ids = {p.lesson_id for p in completed}
        course_ids = {
            p.lesson.module.course_id
            for p in completed
            if p.lesson and p.lesson.module
        }

        # Курсы в которых есть прогресс
        courses_with_progress = []
        if completed_lesson_ids and course_ids:
            all_courses = (
                db.query(Course)
                .options(joinedload(Course.modules).joinedload(Module.lessons))
                .filter(Course.id.in_(course_ids))
                .all()
            )
            for course in all_courses:
                total = sum(len(m.lessons) for m in course.modules)
                done = sum(
                    1 for m in course.modules
                    for l in m.lessons
                    if l.id in completed_lesson_ids
                )
                if done > 0:
                    pct = int(done / total * 100) if total > 0 else 0
                    courses_with_progress.append({
                        "course": course,
                        "done": done,
                        "total": total,
                        "percent": pct,
                    })

        # Отзывы студента
        reviews = db.query(Review).filter(Review.student_id == user.id).all()

        context["courses_with_progress"] = courses_with_progress
        context["reviews"] = reviews

    return templates.TemplateResponse("profile/profile.html", context)

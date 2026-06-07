# Роутер профиля пользователя
import logging

logger = logging.getLogger(__name__)

from app.deps.cloudinary import cloudinary
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps.auth import get_user
from app.models.course import Course
from app.models.progress import Progress
from app.models.review import Review
from app.models.lesson import Lesson
from app.models.module import Module
from app.models.organization import Organization
from app.services import upload_service

router = APIRouter()
from app.ui import templates




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
        avatar_url = await upload_service.upload_user_avatar(file, user, db)
        logger.info(f"Cloudinary result: {avatar_url}")
        logger.info(f"Avatar saved: {user.avatar_url}")
        return JSONResponse({"success": True, "url": avatar_url})
    except HTTPException as exc:
        logger.warning(f"Invalid avatar upload: {file.filename}, {file.content_type}, {exc.detail}")
        return JSONResponse(
            {"success": False, "error": exc.detail},
            status_code=400,
        )
    except Exception as exc:
        logger.error(f"Avatar upload failed: {exc}")
        return JSONResponse(
            {"success": False, "error": f"Ошибка загрузки: {exc}"},
            status_code=500,
        )


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

    upload_service.delete_user_avatar(user, db)

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

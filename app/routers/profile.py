# Роутер профиля пользователя
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.progress import Progress
from app.models.review import Review
from app.models.lesson import Lesson
from app.models.module import Module

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/profile", response_class=HTMLResponse)
def profile(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/login", status_code=302)

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        request.session.clear()
        return RedirectResponse("/login", status_code=302)

    context = {"request": request, "user": user}

    if user.role.value == "teacher":
        # Курсы преподавателя с количеством студентов (упрощённо — без записи)
        courses = (
            db.query(Course)
            .filter(Course.teacher_id == uid)
            .options(joinedload(Course.modules).joinedload(Module.lessons))
            .all()
        )
        context["courses"] = courses

    elif user.role.value == "student":
        # Пройденные уроки
        completed = (
            db.query(Progress)
            .options(joinedload(Progress.lesson).joinedload(Lesson.module))
            .filter(Progress.student_id == uid, Progress.completed == True)  # noqa: E712
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
        reviews = db.query(Review).filter(Review.student_id == uid).all()

        context["courses_with_progress"] = courses_with_progress
        context["reviews"] = reviews

    return templates.TemplateResponse("profile.html", context)

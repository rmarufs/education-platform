# Роутер отзывов и рейтингов курса
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.deps.auth import get_user
from app.models.course import Course
from app.models.review import Review
from app.models.progress import Progress
from app.models.lesson import Lesson
from app.models.module import Module

router = APIRouter()

@router.post("/reviews/submit")
def submit_review(
    request: Request,
    teacher_id: int = Form(...),
    course_id: int = Form(...),
    rating: int = Form(...),
    comment: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        raise HTTPException(status_code=401, detail="Не авторизован")

    if not user or user.role.value != "student":
        raise HTTPException(status_code=403, detail="Только студенты могут оставлять отзывы")

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Рейтинг от 1 до 5")

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
    ) or 0

    # \u0423\u0441\u043b\u043e\u0432\u0438\u0435 1: \u0441\u0442\u0443\u0434\u0435\u043d\u0442 \u043f\u0440\u043e\u0448\u0451\u043b 2+ \u0443\u0440\u043e\u043a\u043e\u0432 \u0443 \u044d\u0442\u043e\u0433\u043e \u043f\u0440\u0435\u043f\u043e\u0434\u0430\u0432\u0430\u0442\u0435\u043b\u044f
    enough_lessons = completed_teacher_lessons >= 2

    # \u0423\u0441\u043b\u043e\u0432\u0438\u0435 2: \u0441\u0442\u0443\u0434\u0435\u043d\u0442 \u043f\u043e\u043b\u043d\u043e\u0441\u0442\u044c\u044e \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u043b \u043a\u0443\u0440\u0441 (\u0434\u0430\u0436\u0435 \u0435\u0441\u043b\u0438 \u0443\u0440\u043e\u043a \u043e\u0434\u0438\u043d)
    course_obj = db.query(Course).filter(Course.id == course_id).first()
    if course_obj:
        total_lessons = (
            db.query(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .filter(Module.course_id == course_id)
            .scalar()
        ) or 0
        done_in_course = (
            db.query(func.count(Progress.id))
            .join(Lesson, Progress.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .filter(
                Progress.student_id == user.id,
                Progress.completed == True,
                Module.course_id == course_id,
            )
            .scalar()
        ) or 0
        course_fully_done = total_lessons > 0 and done_in_course >= total_lessons
    else:
        course_fully_done = False

    if not enough_lessons and not course_fully_done:
        raise HTTPException(status_code=403, detail="Необходимо завершить минимум 2 урока или пройти курс полностью")

    review = db.query(Review).filter(
        Review.student_id == user.id,
        Review.teacher_id == teacher_id
    ).first()

    if review:
        review.rating = rating
        review.text = comment
        review.course_id = course_id
    else:
        review = Review(
            student_id=user.id,
            teacher_id=teacher_id,
            course_id=course_id,
            rating=rating,
            text=comment
        )
        db.add(review)

    db.commit()

    # Пересчитываем средний рейтинг курса
    avg = db.query(func.avg(Review.rating)).filter(Review.course_id == course_id).scalar()
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        course.rating = round(avg or 0, 1)
        db.commit()

    return {"detail": "Отзыв успешно сохранен"}


# ── Оставить отзыв на курс ─────────────────────────────────────
@router.post("/courses/{course_id:int}/review")
def leave_review(
    course_id: int,
    request: Request,
    rating: int = Form(...),
    text: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        return RedirectResponse("/login", status_code=302)

    if not user or user.role.value != "student":
        raise HTTPException(status_code=403, detail="Только студенты могут оставлять отзывы")

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Рейтинг от 1 до 5")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    # Обновляем или создаём отзыв
    review = db.query(Review).filter(
        Review.course_id == course_id, Review.student_id == user.id
    ).first()

    if review:
        review.rating = rating
        review.text = text
    else:
        review = Review(course_id=course_id, student_id=user.id, rating=rating, text=text)
        db.add(review)

    db.commit()

    # Пересчитываем средний рейтинг курса
    avg = db.query(func.avg(Review.rating)).filter(Review.course_id == course_id).scalar()
    course.rating = round(avg or 0, 1)
    db.commit()

    return RedirectResponse(f"/courses/{course_id}", status_code=302)

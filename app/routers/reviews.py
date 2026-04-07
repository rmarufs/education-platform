# Роутер отзывов и рейтингов курса
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.review import Review

router = APIRouter()


# ── Оставить отзыв на курс ─────────────────────────────────────
@router.post("/courses/{course_id}/review")
def leave_review(
    course_id: int,
    request: Request,
    rating: int = Form(...),
    text: str = Form(""),
    db: Session = Depends(get_db),
):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/login", status_code=302)

    user = db.query(User).filter(User.id == uid).first()
    if not user or user.role.value != "student":
        raise HTTPException(status_code=403, detail="Только студенты могут оставлять отзывы")

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Рейтинг от 1 до 5")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    # Обновляем или создаём отзыв
    review = db.query(Review).filter(
        Review.course_id == course_id, Review.student_id == uid
    ).first()

    if review:
        review.rating = rating
        review.text = text
    else:
        review = Review(course_id=course_id, student_id=uid, rating=rating, text=text)
        db.add(review)

    db.commit()

    # Пересчитываем средний рейтинг курса
    avg = db.query(func.avg(Review.rating)).filter(Review.course_id == course_id).scalar()
    course.rating = round(avg or 0, 1)
    db.commit()

    return RedirectResponse(f"/courses/{course_id}", status_code=302)

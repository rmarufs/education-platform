# Роутер комментариев (Q&A под уроками)
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import can_access_course_content, get_user
from app.models.comment import Comment
from app.models.course import Course
from app.models.lesson import Lesson

router = APIRouter()


def _require_lesson_access(lesson: Lesson | None, user, db: Session) -> None:
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    if not lesson.module:
        raise HTTPException(status_code=404, detail="Курс не найден")

    course = db.query(Course).filter(Course.id == lesson.module.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    if not can_access_course_content(user, course, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")


# ── Добавить комментарий к уроку ──────────────────────────────
@router.post("/lessons/{lesson_id}/comment")
def add_comment(
    lesson_id: int,
    request: Request,
    text: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Текст не может быть пустым")

    lesson = (
        db.query(Lesson)
        .options(joinedload(Lesson.module))
        .filter(Lesson.id == lesson_id)
        .first()
    )
    _require_lesson_access(lesson, user, db)

    comment = Comment(lesson_id=lesson_id, user_id=user.id, text=text.strip())
    db.add(comment)
    db.commit()
    return RedirectResponse(f"/lessons/{lesson_id}", status_code=302)


# ── Ответить на комментарий ────────────────────────────────────
@router.post("/comments/{comment_id}/reply")
def reply_comment(
    comment_id: int,
    request: Request,
    text: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    parent = (
        db.query(Comment)
        .options(joinedload(Comment.lesson).joinedload(Lesson.module))
        .filter(Comment.id == comment_id)
        .first()
    )
    if not parent:
        raise HTTPException(status_code=404)
    _require_lesson_access(parent.lesson, user, db)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Текст не может быть пустым")

    # Всегда привязываем ответ к корневому комментарию (максимум 2 уровня)
    root_id = parent.parent_comment_id if parent.parent_comment_id else parent.id

    reply = Comment(
        lesson_id=parent.lesson_id,
        user_id=user.id,
        text=text.strip(),
        parent_comment_id=root_id,
    )
    db.add(reply)
    db.commit()
    return RedirectResponse(f"/lessons/{parent.lesson_id}", status_code=302)

# Роутер комментариев (Q&A под уроками)
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.comment import Comment

router = APIRouter()


# ── Добавить комментарий к уроку ──────────────────────────────
@router.post("/lessons/{lesson_id}/comment")
def add_comment(
    lesson_id: int,
    request: Request,
    text: str = Form(...),
    db: Session = Depends(get_db),
):
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/login", status_code=302)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Текст не может быть пустым")

    comment = Comment(lesson_id=lesson_id, user_id=uid, text=text.strip())
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
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse("/login", status_code=302)

    parent = db.query(Comment).filter(Comment.id == comment_id).first()
    if not parent:
        raise HTTPException(status_code=404)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Текст не может быть пустым")

    reply = Comment(
        lesson_id=parent.lesson_id,
        user_id=uid,
        text=text.strip(),
        parent_comment_id=comment_id,
    )
    db.add(reply)
    db.commit()
    return RedirectResponse(f"/lessons/{parent.lesson_id}", status_code=302)

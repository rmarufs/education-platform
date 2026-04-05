# Зависимости для защиты маршрутов
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Требует, чтобы текущий пользователь был администратором."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user


def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    """Требует, чтобы пользователь был авторизован."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=403, detail="Пользователь не найден")
    return user

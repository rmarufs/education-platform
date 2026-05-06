# Зависимости для защиты маршрутов
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User


def get_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Получает текущего пользователя из сессии."""
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(User).filter(User.id == uid).first()


def is_admin(user: User | None) -> bool:
    return bool(user and user.role.value == "admin")


def is_teacher(user: User | None) -> bool:
    return bool(user and user.role.value == "teacher")


def is_student(user: User | None) -> bool:
    return bool(user and user.role.value == "student")


def is_org(user: User | None) -> bool:
    return bool(user and user.role.value == "organization")


def can(user: User | None, permission: str) -> bool:
    """Проверка наличия разрешения у пользователя на основе его роли."""
    permissions = {
        "edit_course": ["teacher", "admin", "organization"],
        "view_course": ["student", "teacher", "admin", "organization"],
        "manage_users": ["admin", "organization"],
        "submit_review": ["student"],
    }
    return bool(user and user.role.value in permissions.get(permission, []))


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Требует, чтобы текущий пользователь был администратором."""
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user


def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    """Требует, чтобы пользователь был авторизован."""
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user

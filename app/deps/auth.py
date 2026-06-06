"""Preparatory authentication dependencies.

This module is not wired into the existing routers yet. The current
`app/dependencies.py` module remains the active dependency module.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User


ACCESS_DENIED_DETAIL = "Доступ запрещён"


def get_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Get the current user from the session."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def _redirect_exception(location: str) -> HTTPException:
    return HTTPException(status_code=302, headers={"Location": location})


def require_auth(request: Request, db: Session = Depends(get_db)) -> User:
    """Require an authenticated user."""
    user = get_user(request, db)
    if not user:
        raise _redirect_exception("/login")
    return user


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """Require the current user to be an admin."""
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        raise _redirect_exception("/login")
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_DETAIL)
    return user


def require_teacher(request: Request, db: Session = Depends(get_db)) -> User:
    """Require the current user to be a teacher or admin."""
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        raise HTTPException(status_code=401, detail="Необходима авторизация")
    if not user or user.role.value not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Только преподаватели")
    return user


def require_org(request: Request, db: Session = Depends(get_db)) -> User:
    """Require the current user to be an active organization account."""
    user = get_user(request, db)
    if not user:
        raise _redirect_exception("/login")
    if not user.is_org:
        raise _redirect_exception("/")
    if not user.is_active:
        raise _redirect_exception("/register/pending-org")
    return user


def require_student(request: Request, db: Session = Depends(get_db)) -> User:
    """Require the current user to be a student."""
    user = get_user(request, db)
    if not user:
        raise _redirect_exception("/login")
    if not user.is_student:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_DETAIL)
    return user

import json
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.ui import templates
from app.models.group import Group
from app.models.user import User
from app.models.organization import Organization
from app.deps.auth import get_user as _get_user

from app.services.group_journal_service import (
    get_group_for_journal,
    get_journal_data,
    get_group_for_journal_save,
    save_journal_entries,
)

router = APIRouter()

def _can_manage_group_content(user: User, group: Group, db: Session) -> bool:
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        return bool(org and group.organization_id == org.id)
    if user.is_teacher:
        return group.teacher_id == user.id
    return False


def _get_manageable_group(group_id: int, request: Request, db: Session) -> tuple[User, Group]:
    user = _get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user, group


def _journal_redirect(group_id: int, **params) -> RedirectResponse:
    from urllib.parse import urlencode

    query = urlencode({key: value for key, value in params.items() if value})
    location = f"/groups/{group_id}/journal"
    if query:
        location = f"{location}?{query}"
    return RedirectResponse(location, status_code=302)


@router.get("/{group_id:int}/journal", response_class=HTMLResponse)
def group_journal(group_id: int, request: Request, db: Session = Depends(get_db)):
    user, _ = _get_manageable_group(group_id, request, db)
    
    group = get_group_for_journal(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    lessons, members, entries_map, averages = get_journal_data(db, group)

    return templates.TemplateResponse("groups/journal.html", {
        "request": request,
        "user": user,
        "group": group,
        "members": members,
        "lessons": lessons,
        "entries_map": entries_map,
        "averages": averages,
        "success": request.query_params.get("success"),
        "error": request.query_params.get("error"),
    })


@router.post("/{group_id:int}/journal")
async def group_journal_save(group_id: int, request: Request, db: Session = Depends(get_db)):
    user, _ = _get_manageable_group(group_id, request, db)
    
    group = get_group_for_journal_save(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    form_data = await request.form()
    
    success = save_journal_entries(db, group, form_data)
    if not success:
        return _journal_redirect(group.id, error="invalid_grade")

    return _journal_redirect(group.id, success="journal_saved")

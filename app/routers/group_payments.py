from datetime import date
from typing import Optional
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

from app.services.group_payment_service import (
    get_group_for_payments,
    get_payments_data,
    get_group_for_payments_save,
    save_payments,
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


def _payment_redirect(group_id: int, month: date, **params) -> RedirectResponse:
    from urllib.parse import urlencode

    payload = {"month": month.strftime("%Y-%m"), **{key: value for key, value in params.items() if value}}
    return RedirectResponse(f"/groups/{group_id}/payments?{urlencode(payload)}", status_code=302)


@router.get("/{group_id:int}/payments", response_class=HTMLResponse)
def group_payments(group_id: int, request: Request, month: Optional[str] = None, db: Session = Depends(get_db)):
    user, _ = _get_manageable_group(group_id, request, db)
    
    group = get_group_for_payments(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    members, entries_map, payment_status_map, selected_month = get_payments_data(db, group, month)
    can_edit_payments = user.is_org and _can_manage_group_content(user, group, db)

    return templates.TemplateResponse("groups/payments.html", {
        "request": request,
        "user": user,
        "group": group,
        "members": members,
        "entries_map": entries_map,
        "payment_status_map": payment_status_map,
        "selected_month": selected_month,
        "month_value": selected_month.strftime("%Y-%m"),
        "can_edit_payments": can_edit_payments,
        "success": request.query_params.get("success"),
        "error": request.query_params.get("error"),
    })


@router.post("/{group_id:int}/payments")
async def group_payments_save(group_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user or not user.is_org:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    group = get_group_for_payments_save(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    form_data = await request.form()
    
    selected_month = save_payments(db, group, user.id, form_data)

    return _payment_redirect(group.id, selected_month, success="payments_saved")

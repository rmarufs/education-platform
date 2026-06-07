from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps.auth import get_user as _get_user
from app.models.group import Group
from app.models.organization import Organization
from app.ui import templates
from app.utils.group_analytics import build_group_analytics

router = APIRouter()


def _require_login(request: Request, db: Session):
    user = _get_user(request, db)
    if not user:
        return None, RedirectResponse("/login", status_code=302)
    return user, None


@router.get("/analytics", response_class=HTMLResponse)
def groups_analytics(request: Request, db: Session = Depends(get_db)):
    """Journal analytics for an organization or assigned teacher groups."""
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    org = None
    back_url = "/groups/"
    analytics_scope = "organization"

    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Организация не найдена")
        groups = (
            db.query(Group)
            .options(joinedload(Group.organization), joinedload(Group.teacher))
            .filter(Group.organization_id == org.id)
            .order_by(Group.created_at.desc())
            .all()
        )
    elif user.is_teacher:
        analytics_scope = "teacher"
        back_url = "/groups/my"
        groups = (
            db.query(Group)
            .options(joinedload(Group.organization), joinedload(Group.teacher))
            .filter(Group.teacher_id == user.id)
            .order_by(Group.created_at.desc())
            .all()
        )
    else:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    group_analytics = build_group_analytics(db, groups)
    lagging_students = [
        item
        for group_item in group_analytics
        for item in group_item["lagging_students"]
    ]
    lagging_students.sort(
        key=lambda item: (
            item["group"].name.lower(),
            item["average_grade"],
            (item["student"].name or "").lower(),
        )
    )

    return templates.TemplateResponse("groups/analytics.html", {
        "request": request,
        "user": user,
        "org": org,
        "groups": groups,
        "group_analytics": group_analytics,
        "lagging_students": lagging_students,
        "analytics_scope": analytics_scope,
        "back_url": back_url,
    })

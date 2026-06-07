from datetime import datetime
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from app.database import get_db
from app.deps.auth import get_user
from app.models.user import User, UserRole
from app.models.organization import (
    Organization,
    OrganizationAnnouncement,
    OrganizationAnnouncementDismissal,
    OrganizationTeacher,
    OrganizationStudent,
)
from app.models.course import Course
from app.models.group import Group, GroupMember
from app.utils.announcements import VALID_AUDIENCES, get_visible_announcement
from app.utils.datetime_helpers import parse_optional_datetime as _parse_optional_datetime
from app.utils.uploads import validate_upload_file

router = APIRouter()
from app.ui import templates

APPLICATION_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
APPLICATION_ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".webp"}


def _redirect_org_teachers():
    return RedirectResponse("/organization/teachers", status_code=302)


def _redirect_org_students():
    return RedirectResponse("/organization/students", status_code=302)


def require_org(request: Request, db: Session):
    """Проверяет что пользователь — активная одобренная организация."""
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        return None, RedirectResponse("/login", status_code=302)
    if not user or not user.is_org:
        return None, RedirectResponse("/", status_code=302)
    # Если не одобрена — на страницу ожидания
    if not user.is_active:
        return None, RedirectResponse("/register/pending-org", status_code=302)
    return user, None


def require_user(request: Request, db: Session):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        return None, RedirectResponse("/login", status_code=302)
    if not user:
        request.session.clear()
        return None, RedirectResponse("/login", status_code=302)
    return user, None


def _organization_for_user(db: Session, user: User) -> Organization:
    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _get_owned_announcement(db: Session, org_id: int, announcement_id: int) -> OrganizationAnnouncement:
    announcement = db.query(OrganizationAnnouncement).filter(
        OrganizationAnnouncement.id == announcement_id,
        OrganizationAnnouncement.organization_id == org_id,
    ).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return announcement


# ── API: список одобренных организаций для регистрации преподавателя ──────────

@router.get("/api/organizations/list")
def list_organizations_api(db: Session = Depends(get_db)):
    from app.services.organization_service import get_approved_organizations_list
    return JSONResponse({"organizations": get_approved_organizations_list(db)})


# ── API: поиск преподавателей (для кабинета организации и глобального поиска) ─

@router.get("/api/teachers/search")
def search_teachers_api(
    q: str = "",
    request: Request = None,
    db: Session = Depends(get_db)
):
    caller = get_user(request, db) if request else None
    org = None
    if caller and caller.is_org and caller.is_active:
        org = db.query(Organization).filter(Organization.user_id == caller.id).first()

    from app.services.organization_service import search_teachers_for_organization
    result = search_teachers_for_organization(db, q, org)

    return JSONResponse({"teachers": result})


# ── Кабинет организации ──────────────────────────────────────────────────────

@router.get("/dashboard/organization", response_class=HTMLResponse)
def organization_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()

    from app.services.organization_service import get_organization_dashboard_stats
    stats = get_organization_dashboard_stats(db, org.id) if org else {
        "teachers_count": 0, "courses_count": 0, "students_count": 0,
        "incoming_count": 0, "student_requests_count": 0, "groups_count": 0
    }

    return templates.TemplateResponse(
        "organization/dashboard.html",
        {
            "request": request,
            "user": user,
            "org": org,
            **stats
        }
    )


# ── Объявления учебного центра ───────────────────────────────────────────────

@router.get("/organization/announcements", response_class=HTMLResponse)
def organization_announcements(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = _organization_for_user(db, user)
    from app.services.announcement_service import get_organization_announcements
    announcements = get_organization_announcements(db, org.id)

    return templates.TemplateResponse(
        "organization/announcements.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "announcements": announcements,
        },
    )


@router.post("/organization/announcements/create")
def create_organization_announcement(
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    audience: str = Form("all"),
    expires_at: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = _organization_for_user(db, user)
    from app.services.announcement_service import create_organization_announcement_service
    try:
        create_organization_announcement_service(db, org, user, title, body, audience, expires_at)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse("/organization/announcements?success=created", status_code=302)


@router.post("/organization/announcements/{announcement_id:int}/update")
def update_organization_announcement(
    announcement_id: int,
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    audience: str = Form("all"),
    expires_at: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = _organization_for_user(db, user)
    from app.services.announcement_service import update_organization_announcement_service
    try:
        update_organization_announcement_service(db, org.id, announcement_id, title, body, audience, expires_at)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse("/organization/announcements?success=updated", status_code=302)


@router.post("/organization/announcements/{announcement_id:int}/toggle")
def toggle_organization_announcement(
    announcement_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = _organization_for_user(db, user)
    from app.services.announcement_service import toggle_organization_announcement_service
    try:
        toggle_organization_announcement_service(db, org.id, announcement_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RedirectResponse("/organization/announcements?success=updated", status_code=302)


@router.post("/organization/announcements/{announcement_id:int}/delete")
def delete_organization_announcement(
    announcement_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = _organization_for_user(db, user)
    from app.services.announcement_service import delete_organization_announcement_service
    try:
        delete_organization_announcement_service(db, org.id, announcement_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return RedirectResponse("/organization/announcements?success=deleted", status_code=302)


@router.post("/announcements/{announcement_id:int}/dismiss")
def dismiss_organization_announcement(
    announcement_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = require_user(request, db)
    if redirect:
        return redirect

    from app.services.announcement_service import dismiss_organization_announcement_service
    try:
        dismiss_organization_announcement_service(db, user, announcement_id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    referer = request.headers.get("referer") or ""
    parsed_referer = urlparse(referer)
    next_url = parsed_referer.path or "/dashboard"
    if not next_url.startswith("/"):
        next_url = "/dashboard"
    if parsed_referer.query:
        next_url = f"{next_url}?{parsed_referer.query}"
    return RedirectResponse(next_url, status_code=302)


# ── Список преподавателей + входящие заявки ────────────────────────────────

@router.get("/organization/teachers", response_class=HTMLResponse)
def organization_teachers(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()

    from app.services.organization_service import get_organization_teachers_lists
    accepted, pending, rejected = get_organization_teachers_lists(db, org.id) if org else ([], [], [])

    return templates.TemplateResponse(
        "organization/teachers.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "org_teachers": accepted,
            "pending_teachers": pending,
            "rejected_teachers": rejected,
        }
    )

# ── Список учеников + входящие заявки ────────────────────────────────

@router.get("/organization/students", response_class=HTMLResponse)
def organization_students(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()

    from app.services.organization_service import get_organization_students_lists
    accepted_students, pending_students = get_organization_students_lists(db, org.id) if org else ([], [])

    return templates.TemplateResponse(
        "organization/students.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "org_students": accepted_students,
            "pending_students": pending_students,
        }
    )


# ── Пригласить преподавателя (по email или по teacher_id) ─────────────────────

@router.post("/organization/invite")
def invite_teacher(
    request: Request,
    email: str = Form(""),
    teacher_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    from app.services.organization_service import invite_organization_teacher
    status = invite_organization_teacher(db, org.id, teacher_id, email)

    if status == "teacher_not_found":
        if teacher_id:
            return JSONResponse({"error": "teacher_not_found"}, status_code=404)
        return RedirectResponse("/organization/teachers?error=teacher_not_found", status_code=302)
    elif status == "in_other_org":
        if teacher_id:
            return JSONResponse({"error": "in_other_org"}, status_code=400)
        return RedirectResponse("/organization/teachers?error=in_other_org", status_code=302)
    elif status == "already_invited":
        if teacher_id:
            return JSONResponse({"error": "already_invited"}, status_code=409)
        return RedirectResponse("/organization/teachers?error=already_invited", status_code=302)

    return RedirectResponse("/organization/teachers?success=invited", status_code=302)


# ── Принять входящую заявку от преподавателя ──────────────────────────────

@router.post("/organization/teacher/{link_id:int}/accept-incoming")
def accept_incoming_teacher(link_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    
    from app.services.organization_service import accept_incoming_teacher_service
    try:
        accept_incoming_teacher_service(db, org.id, link_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _redirect_org_teachers()


# ── Отклонить входящую заявку ─────────────────────────────────────────────

@router.post("/organization/teacher/{link_id:int}/reject-incoming")
def reject_incoming_teacher(link_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    
    from app.services.organization_service import reject_incoming_teacher_service
    try:
        reject_incoming_teacher_service(db, org.id, link_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _redirect_org_teachers()


# ── Удалить преподавателя из организации ─────────────────────────────────

@router.post("/organization/teacher/{teacher_id:int}/remove")
def remove_teacher(teacher_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404)

    from app.services.organization_service import remove_teacher_from_organization
    remove_teacher_from_organization(db, org.id, teacher_id)

    return _redirect_org_teachers()


# ── Удалить студента из организации ──────────────────────────────────────

@router.post("/organization/student/{student_id:int}/remove")
def remove_student(student_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404)

    from app.services.organization_service import remove_student_from_organization
    remove_student_from_organization(db, org.id, student_id)

    return _redirect_org_students()


# ── Обработка заявок от студентов ──────────────────────────────────────────

@router.post("/organization/student/{link_id:int}/accept")
def accept_student(link_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    
    from app.services.organization_service import accept_student_in_organization
    accept_student_in_organization(db, org.id, link_id)

    return _redirect_org_students()


@router.post("/organization/student/{link_id:int}/reject")
def reject_student(link_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    
    from app.services.organization_service import reject_student_in_organization
    reject_student_in_organization(db, org.id, link_id)

    return _redirect_org_students()


# ── Студент вступает в организацию ───────────────────────────────────────────

@router.post("/organization/{org_id:int}/student/join")
def student_join_organization(org_id: int, request: Request, force: bool = False, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    if not user or not user.is_student:
        raise HTTPException(status_code=403, detail="Только студенты могут вступать в учебные центры")

    from app.services.organization_service import student_join_organization_service
    try:
        status, old_org_name, is_open = student_join_organization_service(db, org_id, user, force)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if status == "already_in_this_org":
        return JSONResponse({"success": True, "already": True})
    elif status == "in_other_org":
        return JSONResponse({
            "already_in_org": True,
            "org_name": old_org_name
        })

    return JSONResponse({"success": True, "auto_accepted": is_open})


# ── Студент покидает организацию ─────────────────────────────────────────────

@router.post("/organization/student/leave")
def student_leave_organization(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    from app.services.organization_service import student_leave_organization_service
    student_leave_organization_service(db, user_id)

    return RedirectResponse("/dashboard/student", status_code=302)


# ── Курсы преподавателя (для кабинета организации) ────────────────────────────

@router.get("/organization/teacher/{teacher_id:int}/courses", response_class=HTMLResponse)
def org_teacher_courses(teacher_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    # Проверяем, что преподаватель является членом этой организации
    from app.services.organization_service import get_organization_teacher_courses
    try:
        teacher, courses = get_organization_teacher_courses(db, org.id, teacher_id)
    except ValueError as e:
        if "не является членом" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))

    return templates.TemplateResponse(
        "organization/teacher_courses.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "teacher": teacher,
            "courses": courses,
        }
    )


# ── Профиль организации ────────────────────────────────────────────────────

@router.get("/organization/profile", response_class=HTMLResponse)
def organization_profile(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()

    return templates.TemplateResponse(
        "organization/profile.html",
        {"request": request, "user": user, "org": org}
    )


@router.post("/organization/profile/update")
def organization_profile_update(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    phone: str = Form(""),
    website: Optional[str] = Form(None),
    is_open: str = Form("true"),
    db: Session = Depends(get_db)
):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    
    from app.services.organization_service import update_organization_profile_service
    try:
        update_organization_profile_service(db, org.id, name, description, phone, website, is_open)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return RedirectResponse("/organization/profile?success=1", status_code=302)


# ── Принять/отклонить приглашение (для преподавателя) ──────────────────────

@router.post("/organization/invite/{invite_id:int}/accept")
def accept_invite(invite_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    from app.services.organization_service import teacher_accepts_invite
    teacher_accepts_invite(db, user_id, invite_id)

    return RedirectResponse("/dashboard/teacher", status_code=302)


@router.post("/organization/invite/{invite_id:int}/reject")
def reject_invite(invite_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    from app.services.organization_service import teacher_rejects_invite
    teacher_rejects_invite(db, user_id, invite_id)

    return RedirectResponse("/dashboard/teacher", status_code=302)


# ── Публичная страница организации ────────────────────────────────────────

@router.get("/organization/{org_id:int}", response_class=HTMLResponse)
def public_organization_profile(org_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user(request, db)

    from app.services.organization_service import get_public_organization_profile_data
    try:
        data = get_public_organization_profile_data(db, org_id, user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return templates.TemplateResponse(
        "organization/public_profile.html",
        {
            "request": request,
            "user": user,
            **data
        }
    )


# ── Преподаватель сам вступает в организацию ──────────────────────────────────

@router.post("/organization/{org_id:int}/join")
async def join_organization(
    org_id: int,
    request: Request,
    cover_letter: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    from app.models.user import UserRole
    if not user or user.role not in [UserRole.teacher, UserRole.teacher_pending]:
        raise HTTPException(status_code=403, detail="Только преподаватели могут отправлять заявку")

    from app.services.organization_service import teacher_apply_organization_service
    try:
        status, existing_status = teacher_apply_organization_service(db, org_id, user, cover_letter, attachment)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if status == "in_other_org":
        raise HTTPException(status_code=400, detail="Вы уже состоите в другом учебном центре")
    elif status == "already_exists":
        return JSONResponse({"success": True, "status": existing_status, "already": True})

    return JSONResponse({"success": True})

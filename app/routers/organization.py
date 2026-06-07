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

    from app.models.user import UserRole

    # Найти преподавателя по ID или email
    if teacher_id:
        teacher = db.query(User).filter(
            User.id == teacher_id,
            User.role == UserRole.teacher,
            User.is_active == True,
        ).first()
    else:
        email = email.strip().lower()
        teacher = db.query(User).filter(
            User.email == email,
            User.role == UserRole.teacher,
        ).first()

    if not teacher:
        if teacher_id:
            return JSONResponse({"error": "teacher_not_found"}, status_code=404)
        return RedirectResponse("/organization/teachers?error=teacher_not_found", status_code=302)

    # Защита: нельзя приглашать если уже в другой организации
    in_other_org = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.teacher_id == teacher.id,
        OrganizationTeacher.status == "accepted",
        OrganizationTeacher.organization_id != org.id,
    ).first()
    if in_other_org:
        if teacher_id:
            return JSONResponse({"error": "in_other_org"}, status_code=400)
        return RedirectResponse("/organization/teachers?error=in_other_org", status_code=302)

    existing = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.teacher_id == teacher.id
    ).first()

    if existing:
        if teacher_id:
            return JSONResponse({"error": "already_invited"}, status_code=409)
        return RedirectResponse("/organization/teachers?error=already_invited", status_code=302)

    org_teacher = OrganizationTeacher(
        organization_id=org.id,
        teacher_id=teacher.id,
        status="pending"
    )
    db.add(org_teacher)
    db.commit()

    return RedirectResponse("/organization/teachers?success=invited", status_code=302)


# ── Принять входящую заявку от преподавателя ──────────────────────────────

@router.post("/organization/teacher/{link_id:int}/accept-incoming")
def accept_incoming_teacher(link_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    
    org_teacher = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.id == link_id,
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.status == "pending"
    ).first()
    
    if not org_teacher:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    teacher = db.query(User).filter(User.id == org_teacher.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Преподаватель не найден")

    from app.models.user import UserRole
    try:
        org_teacher.status = "accepted"
        org_teacher.was_accepted_notification = True
        teacher.is_active = True
        teacher.role = UserRole.teacher
        db.commit()
        db.refresh(teacher)
        db.refresh(org_teacher)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера при принятии заявки: {str(e)}")

    return _redirect_org_teachers()


# ── Отклонить входящую заявку ─────────────────────────────────────────────

@router.post("/organization/teacher/{link_id:int}/reject-incoming")
def reject_incoming_teacher(link_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    link = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.id == link_id,
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.status == "pending"
    ).first()

    if not link:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    try:
        link.status = "rejected"
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при отклонении заявки: {str(e)}")

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

    link = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.teacher_id == teacher_id
    ).first()

    if link:
        db.delete(link)
        db.commit()

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

    link = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.student_id == student_id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).first()

    if link:
        link.status = "removed"
        link.was_removed_notification = True
        db.commit()

    return _redirect_org_students()


# ── Обработка заявок от студентов ──────────────────────────────────────────

@router.post("/organization/student/{link_id:int}/accept")
def accept_student(link_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    link = db.query(OrganizationStudent).filter(
        OrganizationStudent.id == link_id,
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.status == "pending"
    ).first()

    if link:
        link.status = "accepted"
        db.commit()

    return _redirect_org_students()


@router.post("/organization/student/{link_id:int}/reject")
def reject_student(link_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    link = db.query(OrganizationStudent).filter(
        OrganizationStudent.id == link_id,
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.status == "pending"
    ).first()

    if link:
        link.status = "rejected"
        link.was_removed_notification = False
        db.commit()

    return _redirect_org_students()


# ── Студент вступает в организацию ───────────────────────────────────────────

@router.post("/organization/{org_id:int}/student/join")
def student_join_organization(org_id: int, request: Request, force: bool = False, db: Session = Depends(get_db)):
    user = get_user(request, db)
    if "user_id" not in request.session or not request.session["user_id"]:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    if not user or not user.is_student:
        raise HTTPException(status_code=403, detail="Только студенты могут вступать в учебные центры")

    org = db.query(Organization).filter(
        Organization.id == org_id,
        Organization.status == "approved"
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    # ── Upsert: ищем ЛЮБУЮ запись для этой пары (student, org) ──────────────
    # Это предотвращает создание дублей при повторном вступлении (после removed).
    existing_this_org = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.student_id == user.id,
    ).first()

    # Если уже состоит (активная запись) — ничего не делаем
    if existing_this_org and existing_this_org.status in ("accepted", "pending"):
        return JSONResponse({"success": True, "already": True})

    # Если состоит в ДРУГОЙ организации — проверяем force
    other_org_link = db.query(OrganizationStudent).filter(
        OrganizationStudent.student_id == user.id,
        OrganizationStudent.organization_id != org.id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).first()
    if other_org_link:
        if not force:
            old_org = db.query(Organization).filter(Organization.id == other_org_link.organization_id).first()
            return JSONResponse({
                "already_in_org": True,
                "org_name": old_org.name if old_org else "Неизвестно"
            })
        else:
            # Мягко удаляем старую связь с другой организацией через статус
            other_org_link.status = "removed"
            other_org_link.was_removed_notification = False

    new_status = "accepted" if org.is_open else "pending"

    if existing_this_org:
        # Запись уже существует (статус removed) — обновляем её, дублей не создаём
        existing_this_org.status = new_status
        existing_this_org.was_removed_notification = False
    else:
        # Записи нет совсем — создаём новую
        existing_this_org = OrganizationStudent(
            organization_id=org.id,
            student_id=user.id,
            status=new_status,
            was_removed_notification=False,
        )
        db.add(existing_this_org)

    db.commit()
    return JSONResponse({"success": True, "auto_accepted": org.is_open})


# ── Студент покидает организацию ─────────────────────────────────────────────

@router.post("/organization/student/leave")
def student_leave_organization(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    link = db.query(OrganizationStudent).filter(
        OrganizationStudent.student_id == user_id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).first()

    if link:
        link.status = "left"
        link.was_removed_notification = False
        db.commit()

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
    org.name = name
    org.description = description
    org.phone = phone
    org.website = website
    org.is_open = is_open.lower() == "true"
    db.commit()

    return RedirectResponse("/organization/profile?success=1", status_code=302)


# ── Принять/отклонить приглашение (для преподавателя) ──────────────────────

@router.post("/organization/invite/{invite_id:int}/accept")
def accept_invite(invite_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    invite = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.id == invite_id,
        OrganizationTeacher.teacher_id == user_id
    ).first()

    if invite:
        invite.status = "accepted"
        invite.was_accepted_notification = True
        db.commit()

    return RedirectResponse("/dashboard/teacher", status_code=302)


@router.post("/organization/invite/{invite_id:int}/reject")
def reject_invite(invite_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    invite = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.id == invite_id,
        OrganizationTeacher.teacher_id == user_id
    ).first()

    if invite:
        invite.status = "rejected"
        db.commit()

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

    org = db.query(Organization).filter(Organization.id == org_id, Organization.status == "approved").first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    # Проверка, что преподаватель не в другой организации
    in_other_org = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.teacher_id == user.id,
        OrganizationTeacher.status == "accepted",
        OrganizationTeacher.organization_id != org.id
    ).first()
    if in_other_org:
        raise HTTPException(status_code=400, detail="Вы уже состоите в другом учебном центре")

    # Проверка на уже существующую заявку
    existing = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.teacher_id == user.id
    ).first()
    if existing:
        return JSONResponse({"success": True, "status": existing.status, "already": True})

    # Загрузка файла-вложения
    attachment_path = None
    if attachment and attachment.filename:
        import os, uuid, shutil
        upload = validate_upload_file(
            attachment,
            allowed_extensions=APPLICATION_ATTACHMENT_EXTENSIONS,
            max_bytes=APPLICATION_ATTACHMENT_MAX_BYTES,
            invalid_type_message="Недопустимый тип файла вложения",
        )
        upload_dir = "static/uploads/applications"
        os.makedirs(upload_dir, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}_{upload.safe_filename}"
        dest = os.path.join(upload_dir, safe_name)
        with open(dest, "wb") as f:
            shutil.copyfileobj(attachment.file, f)
        attachment_path = f"/{dest}"

    try:
        org_teacher = OrganizationTeacher(
            organization_id=org.id,
            teacher_id=user.id,
            status="pending",
            cover_letter=cover_letter.strip() if cover_letter else None,
            attachment=attachment_path,
        )
        db.add(org_teacher)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка при создании заявки")

    return JSONResponse({"success": True})

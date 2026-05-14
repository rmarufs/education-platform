from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.models.course import Course
from app.models.group import Group, GroupMember

router = APIRouter()
from app.ui import templates


def require_org(request: Request, db: Session):
    """Проверяет что пользователь — активная одобренная организация."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None, RedirectResponse("/login", status_code=302)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_org:
        return None, RedirectResponse("/", status_code=302)
    # Если не одобрена — на страницу ожидания
    if not user.is_active:
        return None, RedirectResponse("/register/pending-org", status_code=302)
    return user, None


# ── API: список одобренных организаций для регистрации преподавателя ──────────

@router.get("/api/organizations/list")
def list_organizations_api(db: Session = Depends(get_db)):
    orgs = (
        db.query(Organization)
        .options(joinedload(Organization.user))
        .filter(Organization.status == "approved")
        .order_by(Organization.name)
        .all()
    )
    return JSONResponse({
        "organizations": [
            {"id": o.id, "name": o.name, "logo_url": o.logo_url or (o.user.avatar_url if o.user else None)}
            for o in orgs
        ]
    })


# ── API: поиск преподавателей (для кабинета организации и глобального поиска) ─

@router.get("/api/teachers/search")
def search_teachers_api(
    q: str = "",
    request: Request = None,
    db: Session = Depends(get_db)
):
    from app.models.user import UserRole

    query = db.query(User).filter(
        User.role == UserRole.teacher,
        User.is_active == True,
    )
    if q.strip():
        query = query.filter(User.name.ilike(f"%{q.strip()}%"))

    teachers = query.order_by(User.name).limit(20).all()

    # Получаем карту teacher_id → org_link
    teacher_ids = [t.id for t in teachers]
    org_map = {}
    if teacher_ids:
        links = (
            db.query(OrganizationTeacher)
            .options(joinedload(OrganizationTeacher.organization))
            .filter(
                OrganizationTeacher.teacher_id.in_(teacher_ids),
                OrganizationTeacher.status == "accepted",
            )
            .all()
        )
        for link in links:
            org_map[link.teacher_id] = link

    # Определяем приглашённых текущей организацией (если запрос от орг)
    already_invited = set()
    user_id = request.session.get("user_id") if request else None
    if user_id:
        caller = db.query(User).filter(User.id == user_id).first()
        if caller and caller.is_org and caller.is_active:
            org = db.query(Organization).filter(Organization.user_id == caller.id).first()
            if org:
                inv_links = db.query(OrganizationTeacher).filter(
                    OrganizationTeacher.organization_id == org.id,
                    OrganizationTeacher.teacher_id.in_(teacher_ids),
                ).all()
                already_invited = {l.teacher_id for l in inv_links}

    result = []
    for t in teachers:
        org_link = org_map.get(t.id)
        result.append({
            "id": t.id,
            "name": t.name,
            "bio": (t.bio[:120] if t.bio else None),
            "avatar": getattr(t, "avatar_url", None),
            "org_name": org_link.organization.name if org_link else None,
            "org_id": org_link.organization_id if org_link else None,
            "already_invited": t.id in already_invited,
        })

    return JSONResponse({"teachers": result})


# ── Кабинет организации ──────────────────────────────────────────────────────

@router.get("/dashboard/organization", response_class=HTMLResponse)
def organization_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()

    accepted_count = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.status == "accepted"
    ).count() if org else 0

    teacher_ids = [t.teacher_id for t in db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.status == "accepted"
    ).all()] if org else []

    courses_count = db.query(Course).filter(Course.teacher_id.in_(teacher_ids)).count() if teacher_ids else 0

    # Входящие заявки преподавателей (pending — учителя выбрали эту организацию при регистрации)
    incoming_count = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.status == "pending"
    ).count() if org else 0

    # Входящие заявки студентов (pending — студенты ждут одобрения закрытого центра)
    student_requests_count = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.status == "pending"
    ).count() if org else 0

    # Количество студентов
    students_count = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.status == "accepted"
    ).count() if org else 0

    # Количество групп
    from app.models.group import Group
    groups_count = db.query(Group).filter(Group.organization_id == org.id).count() if org else 0

    return templates.TemplateResponse(
        "organization/dashboard.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "teachers_count": accepted_count,
            "courses_count": courses_count,
            "students_count": students_count,
            "incoming_count": incoming_count,
            "student_requests_count": student_requests_count,
            "groups_count": groups_count,
        }
    )


# ── Список преподавателей + входящие заявки ────────────────────────────────

@router.get("/organization/teachers", response_class=HTMLResponse)
def organization_teachers(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()

    all_links = db.query(OrganizationTeacher).options(joinedload(OrganizationTeacher.teacher)).filter(
        OrganizationTeacher.organization_id == org.id
    ).all() if org else []

    accepted = [l for l in all_links if l.status == "accepted"]
    pending  = [l for l in all_links if l.status == "pending"]
    rejected = [l for l in all_links if l.status == "rejected"]

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

    org_students = db.query(OrganizationStudent).options(
        joinedload(OrganizationStudent.student)
    ).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).order_by(OrganizationStudent.created_at.desc()).all() if org else []

    accepted_students = [s for s in org_students if s.status == "accepted"]
    pending_students = [s for s in org_students if s.status == "pending"]

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

@router.post("/organization/teacher/{link_id}/accept-incoming")
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
        teacher.is_active = True
        teacher.role = UserRole.teacher
        db.commit()
        db.refresh(teacher)
        db.refresh(org_teacher)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сервера при принятии заявки: {str(e)}")

    return RedirectResponse("/organization/teachers", status_code=302)


# ── Отклонить входящую заявку ─────────────────────────────────────────────

@router.post("/organization/teacher/{link_id}/reject-incoming")
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

    return RedirectResponse("/organization/teachers", status_code=302)


# ── Удалить преподавателя из организации ─────────────────────────────────

@router.post("/organization/teacher/{teacher_id}/remove")
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

    return RedirectResponse("/organization/teachers", status_code=302)


# ── Удалить студента из организации ──────────────────────────────────────

@router.post("/organization/student/{student_id}/remove")
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

    return RedirectResponse("/organization/students", status_code=302)


# ── Обработка заявок от студентов ──────────────────────────────────────────

@router.post("/organization/student/{link_id}/accept")
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

    return RedirectResponse("/organization/students", status_code=302)


@router.post("/organization/student/{link_id}/reject")
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

    return RedirectResponse("/organization/students", status_code=302)


# ── Студент вступает в организацию ───────────────────────────────────────────

@router.post("/organization/{org_id}/student/join")
def student_join_organization(org_id: int, request: Request, force: bool = False, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    user = db.query(User).filter(User.id == user_id).first()
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

@router.get("/organization/teacher/{teacher_id}/courses", response_class=HTMLResponse)
def org_teacher_courses(teacher_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_org(request, db)
    if redirect:
        return redirect

    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    # Проверяем, что преподаватель является членом этой организации
    membership = db.query(OrganizationTeacher).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.teacher_id == teacher_id,
        OrganizationTeacher.status == "accepted"
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Этот преподаватель не является членом вашего учебного центра")

    teacher = db.query(User).filter(User.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Преподаватель не найден")

    from app.models.course import Course
    from sqlalchemy.orm import joinedload
    courses = db.query(Course).options(
        joinedload(Course.category)
    ).filter(Course.teacher_id == teacher_id).order_by(Course.created_at.desc()).all()

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

@router.post("/organization/invite/{invite_id}/accept")
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
        db.commit()

    return RedirectResponse("/dashboard/teacher", status_code=302)


@router.post("/organization/invite/{invite_id}/reject")
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

@router.get("/organization/{org_id}", response_class=HTMLResponse)
def public_organization_profile(org_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first() if user_id else None

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")

    org_teachers = db.query(OrganizationTeacher).options(joinedload(OrganizationTeacher.teacher)).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.status == "accepted"
    ).all()

    teacher_ids = [ot.teacher_id for ot in org_teachers]

    courses = []
    if teacher_ids:
        courses = db.query(Course).options(
            joinedload(Course.teacher),
            joinedload(Course.category)
        ).filter(Course.teacher_id.in_(teacher_ids)).all()

    direct_student_ids = {
        student_id
        for (student_id,) in db.query(OrganizationStudent.student_id)
        .join(User, User.id == OrganizationStudent.student_id)
        .filter(
            OrganizationStudent.organization_id == org.id,
            OrganizationStudent.status == "accepted",
            User.role == UserRole.student,
        )
        .all()
    }
    group_student_ids = {
        student_id
        for (student_id,) in db.query(GroupMember.student_id)
        .join(Group, Group.id == GroupMember.group_id)
        .join(User, User.id == GroupMember.student_id)
        .filter(
            Group.organization_id == org.id,
            User.role == UserRole.student,
        )
        .all()
    }
    students_count = len(direct_student_ids | group_student_ids)

    from app.models.review import Review
    from sqlalchemy.sql import func
    avg_rating = 0.0
    if teacher_ids:
        avg = db.query(func.avg(Review.rating)).filter(Review.teacher_id.in_(teacher_ids)).scalar()
        avg_rating = round(avg or 0.0, 1)

    # Заявка текущего пользователя-преподавателя в эту организацию
    user_application = None
    user_in_any_org = False
    # Членство текущего студента в этой организации
    user_student_membership = None
    current_student_org = None

    if user and user.is_teacher:
        user_application = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == user.id
        ).first()
        user_in_any_org = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.teacher_id == user.id,
            OrganizationTeacher.status == "accepted"
        ).first() is not None

    if user and user.is_student:
        user_student_membership = db.query(OrganizationStudent).filter(
            OrganizationStudent.organization_id == org.id,
            OrganizationStudent.student_id == user.id,
            OrganizationStudent.status.in_(["accepted", "pending", "rejected"])
        ).first()
        
        if not user_student_membership:
            other_membership = db.query(OrganizationStudent).filter(
                OrganizationStudent.student_id == user.id,
                OrganizationStudent.status.in_(["accepted", "pending"])
            ).first()
            if other_membership:
                current_student_org = db.query(Organization).filter(
                    Organization.id == other_membership.organization_id
                ).first()

    return templates.TemplateResponse(
        "organization/public_profile.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "org_teachers": [ot.teacher for ot in org_teachers],
            "courses": courses,
            "students_count": students_count,
            "avg_rating": avg_rating,
            "user_application": user_application,
            "user_in_any_org": user_in_any_org,
            "user_student_membership": user_student_membership,
            "current_student_org": current_student_org,
        }
    )


# ── Преподаватель сам вступает в организацию ──────────────────────────────────

@router.post("/organization/{org_id}/join")
async def join_organization(
    org_id: int,
    request: Request,
    cover_letter: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    user = db.query(User).filter(User.id == user_id).first()

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
        upload_dir = "static/uploads/applications"
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(attachment.filename)[-1].lower()
        safe_name = f"{uuid.uuid4().hex}{ext}"
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

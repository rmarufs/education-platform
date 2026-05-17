import os
import shutil
import uuid
from datetime import date, datetime
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional, List
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.models.group import Group, GroupMember, GroupModule, GroupLesson, GroupMaterial, GroupJournalEntry, GroupPaymentEntry
from app.ui import templates
from app.utils.image import compress_and_upload_avatar
from app.utils.group_analytics import build_group_analytics

router = APIRouter(prefix="/groups", tags=["groups"])

GROUP_MATERIAL_DIR = os.path.join("static", "uploads", "group_materials")


class BulkAddStudentsPayload(BaseModel):
    student_ids: List[int]
    grade: Optional[int] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_user(request: Request, db: Session) -> Optional[User]:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(User).filter(User.id == uid).first()


def _require_org(request: Request, db: Session):
    user = _get_user(request, db)
    if not user or not user.is_org:
        return None, RedirectResponse("/login", status_code=302)
    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        return None, RedirectResponse("/", status_code=302)
    return (user, org), None


def _require_teacher(request: Request, db: Session):
    user = _get_user(request, db)
    if not user or not user.is_teacher:
        return None, RedirectResponse("/login", status_code=302)
    return user, None


def _require_login(request: Request, db: Session):
    user = _get_user(request, db)
    if not user:
        return None, RedirectResponse("/login", status_code=302)
    return user, None


def _get_org_for_group(group_id: int, user: User, db: Session):
    """Verify that the group belongs to this org-user's organization."""
    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    group = db.query(Group).filter(
        Group.id == group_id,
        Group.organization_id == org.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return org, group


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


def _validate_quiz_url(quiz_url: str) -> str:
    clean_url = quiz_url.strip()
    if not clean_url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    parsed = urlparse(clean_url)
    if not all([parsed.scheme, parsed.netloc]):
        raise HTTPException(status_code=400, detail="Invalid URL format")
    return clean_url


def _ordered_group_lessons(group: Group) -> list[GroupLesson]:
    ordered_lessons = []
    seen_lesson_ids = set()
    for module in sorted(group.modules, key=lambda item: (item.order_index or 0, item.id)):
        for item in sorted(module.lessons, key=lambda lesson_item: (lesson_item.order or 0, lesson_item.id)):
            if item.group_id == group.id and item.id not in seen_lesson_ids:
                ordered_lessons.append(item)
                seen_lesson_ids.add(item.id)

    unassigned_lessons = sorted(
        [item for item in group.lessons if item.group_module_id is None and item.id not in seen_lesson_ids],
        key=lambda item: (item.order or 0, item.id),
    )
    ordered_lessons.extend(unassigned_lessons)
    return ordered_lessons


def _journal_redirect(group_id: int, **params) -> RedirectResponse:
    from urllib.parse import urlencode

    query = urlencode({key: value for key, value in params.items() if value})
    location = f"/groups/{group_id}/journal"
    if query:
        location = f"{location}?{query}"
    return RedirectResponse(location, status_code=302)


def _month_start(value: date | None = None) -> date:
    value = value or date.today()
    return date(value.year, value.month, 1)


def _parse_month(value: str | None) -> date:
    if not value:
        return _month_start()
    try:
        if len(value) == 7:
            parsed = datetime.strptime(value, "%Y-%m").date()
        else:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month")
    return _month_start(parsed)


def _payment_redirect(group_id: int, month: date, **params) -> RedirectResponse:
    from urllib.parse import urlencode

    payload = {"month": month.strftime("%Y-%m"), **{key: value for key, value in params.items() if value}}
    return RedirectResponse(f"/groups/{group_id}/payments?{urlencode(payload)}", status_code=302)


def _student_payment_overdue(db: Session, group_id: int, student_id: int, today: date | None = None) -> bool:
    today = today or date.today()
    if today.day <= 7:
        return False
    entry = _student_month_payment_entry(db, group_id, student_id, _month_start(today))
    return not (entry and entry.is_paid)


def _student_month_payment_entry(db: Session, group_id: int, student_id: int, month: date) -> GroupPaymentEntry | None:
    return db.query(GroupPaymentEntry).filter(
        GroupPaymentEntry.group_id == group_id,
        GroupPaymentEntry.student_id == student_id,
        GroupPaymentEntry.month == month,
    ).first()


# ═══════════════════════════════════════════════════════════
# ORG ENDPOINTS
# ═══════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse)
def groups_list(request: Request, db: Session = Depends(get_db)):
    """Список групп учебного центра."""
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result

    groups = (
        db.query(Group)
        .options(
            joinedload(Group.teacher),
            joinedload(Group.members),
            joinedload(Group.modules),
            joinedload(Group.lessons),
        )
        .filter(Group.organization_id == org.id)
        .order_by(Group.created_at.desc())
        .all()
    )

    # Список преподавателей организации для dropdown
    teacher_links = db.query(OrganizationTeacher).options(
        joinedload(OrganizationTeacher.teacher)
    ).filter(
        OrganizationTeacher.organization_id == org.id,
        OrganizationTeacher.status == "accepted"
    ).all()
    teachers = [link.teacher for link in teacher_links]

    return templates.TemplateResponse("groups/list.html", {
        "request": request,
        "user": user,
        "org": org,
        "groups": groups,
        "teachers": teachers,
    })


@router.get("/my", response_class=HTMLResponse)
def my_groups(request: Request, db: Session = Depends(get_db)):
    """Список групп текущего преподавателя."""
    user, redirect = _require_teacher(request, db)
    if redirect:
        return redirect

    groups = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.members),
        joinedload(Group.modules),
        joinedload(Group.lessons),
    ).filter(
        Group.teacher_id == user.id,
        Group.is_active == True,
    ).order_by(Group.created_at.desc()).all()

    return templates.TemplateResponse("groups/my_groups.html", {
        "request": request,
        "user": user,
        "groups": groups,
    })


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
        key=lambda item: (item["group"].name.lower(), item["average_grade"], (item["student"].name or "").lower())
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


@router.post("/create")
def group_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    teacher_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result

    # Validate teacher belongs to org if given
    if teacher_id:
        link = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == teacher_id,
            OrganizationTeacher.status == "accepted",
        ).first()
        if not link:
            teacher_id = None

    group = Group(
        name=name.strip(),
        description=description.strip() or None,
        organization_id=org.id,
        teacher_id=teacher_id,
    )
    db.add(group)
    db.commit()
    return RedirectResponse(f"/groups/{group.id}/manage", status_code=302)


@router.get("/{group_id}", response_class=HTMLResponse)
def group_detail(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Детали группы (org-only redirect to manage)."""
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _get_org_for_group(group_id, user, db)
    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


@router.post("/{group_id}/edit")
def group_edit(
    group_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    is_active: str = Form("true"),
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _, group = _get_org_for_group(group_id, user, db)

    group.name = name.strip()
    group.description = description.strip() or None
    group.is_active = is_active.lower() == "true"
    db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=saved", status_code=302)


@router.post("/{group_id}/avatar")
def group_avatar(group_id: int, request: Request, avatar: UploadFile = File(...), db: Session = Depends(get_db)):
    _, group = _get_manageable_group(group_id, request, db)

    if not avatar or not avatar.filename:
        return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)

    ext = os.path.splitext(avatar.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return RedirectResponse(f"/groups/{group_id}/manage?error=invalid_image", status_code=302)

    avatar_url = compress_and_upload_avatar(
        avatar.file,
        public_id=f"groups/group_{group.id}"
    )
    if avatar_url:
        group.avatar_url = avatar_url
        db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=avatar", status_code=302)


@router.post("/{group_id}/delete")
def group_delete(group_id: int, request: Request, db: Session = Depends(get_db)):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _, group = _get_org_for_group(group_id, user, db)

    db.delete(group)
    db.commit()
    return RedirectResponse("/groups/", status_code=302)


@router.post("/{group_id}/assign-teacher")
def group_assign_teacher(
    group_id: int,
    request: Request,
    teacher_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _, group = _get_org_for_group(group_id, user, db)

    if teacher_id:
        link = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == teacher_id,
            OrganizationTeacher.status == "accepted",
        ).first()
        group.teacher_id = teacher_id if link else None
    else:
        group.teacher_id = None
    db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=teacher", status_code=302)


@router.post("/{group_id}/add-student")
def group_add_student(
    group_id: int,
    request: Request,
    student_id: int = Form(...),
    grade: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _, group = _get_org_for_group(group_id, user, db)

    # Student must be a member of the organization
    org_membership = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.student_id == student_id,
        OrganizationStudent.status == "accepted",
    ).first()
    if not org_membership:
        return RedirectResponse(
            f"/groups/{group_id}/manage?error=not_org_member", status_code=302
        )

    # Avoid duplicates
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == student_id,
    ).first()
    if not existing:
        member = GroupMember(
            group_id=group_id,
            student_id=student_id,
            grade=grade,
        )
        db.add(member)
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage?success=student_added", status_code=302)


@router.post("/{group_id}/students/bulk-add")
def group_bulk_add_students(
    group_id: int,
    payload: BulkAddStudentsPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user, org = result
    _get_org_for_group(group_id, user, db)

    selected_ids = []
    seen_ids = set()
    for sid in payload.student_ids:
        if sid not in seen_ids:
            seen_ids.add(sid)
            selected_ids.append(sid)

    if not selected_ids:
        raise HTTPException(status_code=400, detail="Не выбраны ученики")

    org_members = db.query(OrganizationStudent.student_id).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.status == "accepted",
        OrganizationStudent.student_id.in_(selected_ids),
    ).all()
    org_member_ids = {row[0] for row in org_members}

    existing_members = db.query(GroupMember.student_id).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id.in_(selected_ids),
    ).all()
    existing_ids = {row[0] for row in existing_members}

    added_count = 0
    skipped_count = 0
    for sid in selected_ids:
        if sid not in org_member_ids:
            continue
        if sid in existing_ids:
            skipped_count += 1
            continue

        db.add(GroupMember(
            group_id=group_id,
            student_id=sid,
            grade=payload.grade,
        ))
        added_count += 1

    if added_count:
        db.commit()

    return {
        "success": True,
        "added_count": added_count,
        "skipped_count": skipped_count,
    }


@router.post("/{group_id}/remove-student/{student_id}")
def group_remove_student(
    group_id: int,
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _get_org_for_group(group_id, user, db)

    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == student_id,
    ).first()
    if member:
        db.query(GroupJournalEntry).filter(
            GroupJournalEntry.group_id == group_id,
            GroupJournalEntry.student_id == student_id,
        ).delete(synchronize_session=False)
        db.query(GroupPaymentEntry).filter(
            GroupPaymentEntry.group_id == group_id,
            GroupPaymentEntry.student_id == student_id,
        ).delete(synchronize_session=False)
        db.delete(member)
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


# ═══════════════════════════════════════════════════════════
# MANAGE — ORG & TEACHER SHARED VIEW
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id}/manage", response_class=HTMLResponse)
def group_manage(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Управление группой: организация видит всё, преподаватель — уроки и учеников."""
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    success = request.query_params.get("success")
    error = request.query_params.get("error")

    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        group = db.query(Group).options(
            joinedload(Group.organization),
            joinedload(Group.teacher),
            joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.members).joinedload(GroupMember.student),
            joinedload(Group.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.lessons).joinedload(GroupLesson.group_module),
        ).filter(
            Group.id == group_id,
            Group.organization_id == org.id,
        ).first()
        if not group:
            raise HTTPException(status_code=404, detail="Группа не найдена")

        # Teachers in this org for dropdown
        teacher_links = db.query(OrganizationTeacher).options(
            joinedload(OrganizationTeacher.teacher)
        ).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.status == "accepted",
        ).all()
        org_teachers = [link.teacher for link in teacher_links]

        # Accepted students in this org (not yet in group)
        org_student_links = db.query(OrganizationStudent).options(
            joinedload(OrganizationStudent.student)
        ).filter(
            OrganizationStudent.organization_id == org.id,
            OrganizationStudent.status == "accepted",
        ).all()
        member_ids = {m.student_id for m in group.members}
        available_students = [
            s.student for s in org_student_links if s.student_id not in member_ids
        ]

        return templates.TemplateResponse("groups/manage.html", {
            "request": request,
            "user": user,
            "org": org,
            "group": group,
            "group_modules": group.modules,
            "org_teachers": org_teachers,
            "available_students": available_students,
            "success": success,
            "error": error,
        })

    elif user.is_teacher:
        group = db.query(Group).options(
            joinedload(Group.organization),
            joinedload(Group.teacher),
            joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.members).joinedload(GroupMember.student),
            joinedload(Group.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.lessons).joinedload(GroupLesson.group_module),
        ).filter(
            Group.id == group_id,
            Group.teacher_id == user.id,
        ).first()
        if not group:
            raise HTTPException(status_code=403, detail="Доступ запрещён")

        return templates.TemplateResponse("groups/teacher_view.html", {
            "request": request,
            "user": user,
            "group": group,
            "group_modules": group.modules,
            "success": success,
            "error": error,
        })

    else:
        raise HTTPException(status_code=403, detail="Доступ запрещён")


# ═══════════════════════════════════════════════════════════
# GROUP JOURNAL — ORG & TEACHER
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id}/journal", response_class=HTMLResponse)
def group_journal(group_id: int, request: Request, db: Session = Depends(get_db)):
    user, group = _get_manageable_group(group_id, request, db)

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.teacher),
        joinedload(Group.modules).joinedload(GroupModule.lessons),
        joinedload(Group.lessons),
        joinedload(Group.members).joinedload(GroupMember.student),
    ).filter(Group.id == group.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    lessons = _ordered_group_lessons(group)
    members = sorted(group.members, key=lambda member: ((member.student.name or "").lower(), member.student_id))
    lesson_ids = [lesson.id for lesson in lessons]
    student_ids = [member.student_id for member in members]

    entries = []
    if lesson_ids and student_ids:
        entries = db.query(GroupJournalEntry).filter(
            GroupJournalEntry.group_id == group.id,
            GroupJournalEntry.lesson_id.in_(lesson_ids),
            GroupJournalEntry.student_id.in_(student_ids),
        ).all()

    entries_map = {
        (entry.student_id, entry.lesson_id): entry
        for entry in entries
    }
    averages = {
        student_id: avg
        for student_id, avg in db.query(
            GroupJournalEntry.student_id,
            func.avg(GroupJournalEntry.grade),
        ).filter(
            GroupJournalEntry.group_id == group.id,
            GroupJournalEntry.student_id.in_(student_ids or [0]),
            GroupJournalEntry.present.is_(True),
            GroupJournalEntry.grade.isnot(None),
        ).group_by(GroupJournalEntry.student_id).all()
    }

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


@router.post("/{group_id}/journal")
async def group_journal_save(group_id: int, request: Request, db: Session = Depends(get_db)):
    _, group = _get_manageable_group(group_id, request, db)

    group = db.query(Group).options(
        joinedload(Group.modules).joinedload(GroupModule.lessons),
        joinedload(Group.lessons),
        joinedload(Group.members),
    ).filter(Group.id == group.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    lessons = _ordered_group_lessons(group)
    lesson_ids = [lesson.id for lesson in lessons]
    student_ids = [member.student_id for member in group.members]
    form_data = await request.form()

    existing_entries = db.query(GroupJournalEntry).filter(
        GroupJournalEntry.group_id == group.id,
        GroupJournalEntry.lesson_id.in_(lesson_ids or [0]),
        GroupJournalEntry.student_id.in_(student_ids or [0]),
    ).all()
    entries_map = {
        (entry.student_id, entry.lesson_id): entry
        for entry in existing_entries
    }

    try:
        for student_id in student_ids:
            for lesson_id in lesson_ids:
                present = f"present_{student_id}_{lesson_id}" in form_data
                raw_grade = (form_data.get(f"grade_{student_id}_{lesson_id}") or "").strip()
                grade = int(raw_grade) if raw_grade else None

                if grade is not None and grade not in {1, 2, 3, 4, 5}:
                    return _journal_redirect(group.id, error="invalid_grade")
                if not present:
                    grade = None

                entry = entries_map.get((student_id, lesson_id))
                if entry:
                    entry.present = present
                    entry.grade = grade
                else:
                    db.add(GroupJournalEntry(
                        group_id=group.id,
                        lesson_id=lesson_id,
                        student_id=student_id,
                        present=present,
                        grade=grade,
                    ))

        db.commit()
    except ValueError:
        db.rollback()
        return _journal_redirect(group.id, error="invalid_grade")

    return _journal_redirect(group.id, success="journal_saved")


# ═══════════════════════════════════════════════════════════
# PAYMENT JOURNAL — ORG EDITS, TEACHER READS
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id}/payments", response_class=HTMLResponse)
def group_payments(group_id: int, request: Request, month: Optional[str] = None, db: Session = Depends(get_db)):
    user, group = _get_manageable_group(group_id, request, db)
    selected_month = _parse_month(month)

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.teacher),
        joinedload(Group.members).joinedload(GroupMember.student),
    ).filter(Group.id == group.id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    members = sorted(group.members, key=lambda member: ((member.student.name or "").lower(), member.student_id))
    student_ids = [member.student_id for member in members]
    entries = []
    if student_ids:
        entries = db.query(GroupPaymentEntry).options(
            joinedload(GroupPaymentEntry.marked_by)
        ).filter(
            GroupPaymentEntry.group_id == group.id,
            GroupPaymentEntry.month == selected_month,
            GroupPaymentEntry.student_id.in_(student_ids),
        ).all()

    entries_map = {entry.student_id: entry for entry in entries}
    can_edit_payments = user.is_org and _can_manage_group_content(user, group, db)

    return templates.TemplateResponse("groups/payments.html", {
        "request": request,
        "user": user,
        "group": group,
        "members": members,
        "entries_map": entries_map,
        "selected_month": selected_month,
        "month_value": selected_month.strftime("%Y-%m"),
        "can_edit_payments": can_edit_payments,
        "success": request.query_params.get("success"),
        "error": request.query_params.get("error"),
    })


@router.post("/{group_id}/payments")
async def group_payments_save(group_id: int, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not user or not user.is_org:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    form_data = await request.form()
    selected_month = _parse_month(form_data.get("month"))

    group = db.query(Group).options(joinedload(Group.members)).filter(
        Group.id == group.id,
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    student_ids = [member.student_id for member in group.members]
    existing_entries = db.query(GroupPaymentEntry).filter(
        GroupPaymentEntry.group_id == group.id,
        GroupPaymentEntry.month == selected_month,
        GroupPaymentEntry.student_id.in_(student_ids or [0]),
    ).all()
    entries_map = {entry.student_id: entry for entry in existing_entries}
    now = datetime.utcnow()

    for student_id in student_ids:
        is_paid = f"paid_{student_id}" in form_data
        entry = entries_map.get(student_id)
        if not entry:
            entry = GroupPaymentEntry(
                group_id=group.id,
                student_id=student_id,
                month=selected_month,
            )
            db.add(entry)

        if is_paid:
            if not entry.is_paid or not entry.paid_at:
                entry.paid_at = now
            entry.is_paid = True
        else:
            entry.is_paid = False
            entry.paid_at = None
        entry.marked_by_id = user.id

    db.commit()
    return _payment_redirect(group.id, selected_month, success="payments_saved")



# ═══════════════════════════════════════════════════════════
# LESSON ENDPOINTS (org & teacher)
# ═══════════════════════════════════════════════════════════

def _can_manage_lessons(user: User, group: Group, db: Session) -> bool:
    """Check if user can manage lessons in this group."""
    return _can_manage_group_content(user, group, db)


@router.post("/{group_id}/modules/create")
def group_module_create(
    group_id: int,
    request: Request,
    title: str = Form(...),
    order_index: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    _, group = _get_manageable_group(group_id, request, db)

    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Введите название модуля")

    module_order = order_index
    if module_order is None:
        module_order = db.query(GroupModule).filter(GroupModule.group_id == group_id).count()

    module = GroupModule(
        group_id=group_id,
        title=clean_title,
        order_index=module_order,
    )
    db.add(module)
    db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=module_created", status_code=302)


@router.post("/{group_id}/modules/{module_id}/edit")
def group_module_edit(
    group_id: int,
    module_id: int,
    request: Request,
    title: str = Form(...),
    order_index: int = Form(0),
    db: Session = Depends(get_db),
):
    _, group = _get_manageable_group(group_id, request, db)

    module = db.query(GroupModule).filter(
        GroupModule.id == module_id,
        GroupModule.group_id == group.id,
    ).first()
    if not module:
        raise HTTPException(status_code=404, detail="Модуль не найден")

    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Введите название модуля")

    module.title = clean_title
    module.order_index = order_index
    db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=module_saved", status_code=302)


@router.post("/{group_id}/modules/{module_id}/delete")
def group_module_delete(
    group_id: int,
    module_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _, group = _get_manageable_group(group_id, request, db)

    module = db.query(GroupModule).filter(
        GroupModule.id == module_id,
        GroupModule.group_id == group.id,
    ).first()
    if not module:
        raise HTTPException(status_code=404, detail="Модуль не найден")

    db.query(GroupLesson).filter(
        GroupLesson.group_id == group.id,
        GroupLesson.group_module_id == module.id,
    ).update({GroupLesson.group_module_id: None}, synchronize_session=False)
    db.delete(module)
    db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=module_deleted", status_code=302)


@router.post("/api/quiz-url")
async def save_group_quiz_url(
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    form_data = await request.form()
    scope_name = form_data.get("scope_name", "").strip()
    try:
        scope_id = int(form_data.get("scope_id", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid scope_id")

    quiz_url = _validate_quiz_url(form_data.get("quiz_url", ""))

    if scope_name == "group":
        group = db.query(Group).filter(Group.id == scope_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if not _can_manage_group_content(user, group, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        group.quiz_url = quiz_url
    elif scope_name == "module":
        module = db.query(GroupModule).filter(GroupModule.id == scope_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if not _can_manage_group_content(user, module.group, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        module.quiz_url = quiz_url
    elif scope_name == "lesson":
        lesson = db.query(GroupLesson).options(joinedload(GroupLesson.group)).filter(GroupLesson.id == scope_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")
        if not _can_manage_group_content(user, lesson.group, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        lesson.quiz_url = quiz_url
    else:
        raise HTTPException(status_code=400, detail="Invalid scope")

    db.commit()
    return JSONResponse({"success": True})


@router.delete("/api/quiz-url")
async def delete_group_quiz_url(
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    form_data = await request.form()
    scope_name = form_data.get("scope_name", "").strip()
    try:
        scope_id = int(form_data.get("scope_id", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid scope_id")

    if scope_name == "group":
        group = db.query(Group).filter(Group.id == scope_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        if not _can_manage_group_content(user, group, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        group.quiz_url = None
    elif scope_name == "module":
        module = db.query(GroupModule).filter(GroupModule.id == scope_id).first()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if not _can_manage_group_content(user, module.group, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        module.quiz_url = None
    elif scope_name == "lesson":
        lesson = db.query(GroupLesson).options(joinedload(GroupLesson.group)).filter(GroupLesson.id == scope_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")
        if not _can_manage_group_content(user, lesson.group, db):
            raise HTTPException(status_code=403, detail="Unauthorized")
        lesson.quiz_url = None
    else:
        raise HTTPException(status_code=400, detail="Invalid scope")

    db.commit()
    return JSONResponse({"success": True})


@router.post("/{group_id}/lessons/create")
async def lesson_create(
    group_id: int,
    request: Request,
    group_module_id: Optional[int] = Form(None),
    title: str = Form(...),
    description: str = Form(""),
    video_url: Optional[str] = Form(None),
    order: int = Form(0),
    cover: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_lessons(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    module = None
    if group_module_id:
        module = db.query(GroupModule).filter(
            GroupModule.id == group_module_id,
            GroupModule.group_id == group.id,
        ).first()
        if not module:
            raise HTTPException(status_code=404, detail="Модуль не найден")

    lesson = GroupLesson(
        group_id=group_id,
        group_module_id=module.id if module else None,
        title=title.strip(),
        description=description.strip() if description else None,
        video_url=video_url.strip() if video_url else None,
        order=order,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    if cover and cover.filename:
        cover_url = compress_and_upload_avatar(
            cover.file,
            public_id=f"group_lessons/lesson_{lesson.id}"
        )
        if cover_url:
            lesson.cover_url = cover_url
            db.commit()

    # Process files if any
    form_data = await request.form()
    files = form_data.getlist("files")
    if files:
        os.makedirs(GROUP_MATERIAL_DIR, exist_ok=True)
        for f in files:
            if isinstance(f, UploadFile) and f.filename:
                original_name = os.path.basename(f.filename)
                filename = f"{uuid.uuid4().hex}_{original_name}"
                save_path = os.path.join(GROUP_MATERIAL_DIR, filename)
                with open(save_path, "wb") as buffer:
                    shutil.copyfileobj(f.file, buffer)
                db.add(GroupMaterial(
                    lesson_id=lesson.id,
                    title=original_name,
                    file_url="/" + save_path,
                ))
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage?success=lesson_created", status_code=302)


@router.get("/{group_id}/lessons/{lesson_id}/edit", response_class=HTMLResponse)
def lesson_edit_page(
    group_id: int,
    lesson_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_lessons(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    return RedirectResponse(f"/groups/{group_id}/manage?edit_lesson={lesson_id}", status_code=302)


@router.post("/{group_id}/lessons/{lesson_id}/edit")
async def lesson_edit(
    group_id: int,
    lesson_id: int,
    request: Request,
    group_module_id: Optional[int] = Form(None),
    title: str = Form(...),
    description: str = Form(""),
    video_url: Optional[str] = Form(None),
    order: int = Form(0),
    cover: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_lessons(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    module = None
    if group_module_id:
        module = db.query(GroupModule).filter(
            GroupModule.id == group_module_id,
            GroupModule.group_id == group.id,
        ).first()
        if not module:
            raise HTTPException(status_code=404, detail="Модуль не найден")

    lesson.title = title.strip()
    lesson.group_module_id = module.id if module else None
    lesson.description = description.strip() if description else None
    lesson.video_url = video_url.strip() if video_url else None
    lesson.order = order

    if cover and cover.filename:
        cover_url = compress_and_upload_avatar(
            cover.file,
            public_id=f"group_lessons/lesson_{lesson.id}"
        )
        if cover_url:
            lesson.cover_url = cover_url

    # Process files if any
    form_data = await request.form()
    files = form_data.getlist("files")
    if files:
        os.makedirs(GROUP_MATERIAL_DIR, exist_ok=True)
        for f in files:
            if isinstance(f, UploadFile) and f.filename:
                original_name = os.path.basename(f.filename)
                filename = f"{uuid.uuid4().hex}_{original_name}"
                save_path = os.path.join(GROUP_MATERIAL_DIR, filename)
                with open(save_path, "wb") as buffer:
                    shutil.copyfileobj(f.file, buffer)
                db.add(GroupMaterial(
                    lesson_id=lesson.id,
                    title=original_name,
                    file_url="/" + save_path,
                ))

    db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=lesson_saved", status_code=302)


@router.post("/{group_id}/lessons/{lesson_id}/delete")
def lesson_delete(
    group_id: int,
    lesson_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_lessons(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if lesson:
        db.delete(lesson)
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


@router.post("/{group_id}/lessons/{lesson_id}/materials/add")
async def lesson_material_add(
    group_id: int,
    lesson_id: int,
    request: Request,
    title: str = Form(""),
    file_url: Optional[str] = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_lessons(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    material_title = title.strip()
    if file and file.filename:
        os.makedirs(GROUP_MATERIAL_DIR, exist_ok=True)
        original_name = os.path.basename(file.filename)
        filename = f"{uuid.uuid4().hex}_{original_name}"
        save_path = os.path.join(GROUP_MATERIAL_DIR, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        db.add(GroupMaterial(
            lesson_id=lesson.id,
            title=material_title or original_name,
            file_url="/" + save_path,
        ))
    elif file_url and file_url.strip():
        clean_file_url = file_url.strip()
        db.add(GroupMaterial(
            lesson_id=lesson.id,
            title=material_title or clean_file_url.split("/")[-1] or "Материал",
            file_url=clean_file_url,
        ))
    else:
        raise HTTPException(status_code=400, detail="Добавьте файл или ссылку на материал")

    db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=material_added", status_code=302)


@router.post("/{group_id}/lessons/{lesson_id}/materials/{material_id}/delete")
def lesson_material_delete(
    group_id: int,
    lesson_id: int,
    material_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_lessons(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    material = db.query(GroupMaterial).filter(
        GroupMaterial.id == material_id,
        GroupMaterial.lesson_id == lesson_id
    ).first()
    
    if material:
        db.delete(material)
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


# ═══════════════════════════════════════════════════════════
# STUDENT VIEW
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id}/view", response_class=HTMLResponse)
def group_student_view(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Просмотр группы для участника-студента."""
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.materials),
        joinedload(Group.lessons).joinedload(GroupLesson.materials),
        joinedload(Group.teacher),
    ).filter(Group.id == group_id, Group.is_active == True).first()

    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    # Check membership
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()

    if not membership:
        return RedirectResponse("/dashboard/student?error=access_denied", status_code=302)

    ordered_lessons = _ordered_group_lessons(group)
    ordered_lesson_ids = [lesson.id for lesson in ordered_lessons]
    group_has_progress = False
    if ordered_lesson_ids:
        journal_progress = (
            db.query(GroupJournalEntry.id)
            .filter(
                GroupJournalEntry.group_id == group_id,
                GroupJournalEntry.student_id == user.id,
                GroupJournalEntry.lesson_id.in_(ordered_lesson_ids),
                (GroupJournalEntry.present == True) | (GroupJournalEntry.grade.isnot(None)),  # noqa: E712
            )
            .first()
        )
        vocab_progress = (
            db.query(VocabularyAttempt.id)
            .join(VocabularySet, VocabularyAttempt.vocab_set_id == VocabularySet.id)
            .filter(
                VocabularyAttempt.student_id == user.id,
                VocabularySet.lesson_id.in_(ordered_lesson_ids),
            )
            .first()
        )
        group_has_progress = bool(journal_progress or vocab_progress)
    return templates.TemplateResponse("groups/student_view.html", {
        "request": request,
        "user": user,
        "group": group,
        "group_modules": group.modules,
        "ordered_lessons": ordered_lessons,
        "group_has_progress": group_has_progress,
        "membership": membership,
    })


@router.get("/{group_id}/lessons/{lesson_id}", response_class=HTMLResponse)
def group_lesson_view(group_id: int, lesson_id: int, request: Request, db: Session = Depends(get_db)):
    """Просмотр конкретного урока группы для участника-студента."""
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.modules).joinedload(GroupModule.lessons),
        joinedload(Group.lessons),
        joinedload(Group.teacher),
    ).filter(Group.id == group_id).first()

    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    can_preview_as_owner = _can_manage_lessons(user, group, db)
    if not group.is_active and not can_preview_as_owner:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()

    if not membership and not can_preview_as_owner:
        raise HTTPException(status_code=403, detail="Вы не являетесь членом этой группы")

    lesson = db.query(GroupLesson).options(
        joinedload(GroupLesson.materials),
        joinedload(GroupLesson.group_module),
        joinedload(GroupLesson.vocabularies).joinedload(VocabularySet.items),
    ).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id
    ).first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    ordered_lessons = _ordered_group_lessons(group)
    current_index = next(
        (index for index, item in enumerate(ordered_lessons) if item.id == lesson.id),
        None,
    )
    previous_lesson = ordered_lessons[current_index - 1] if current_index and current_index > 0 else None
    next_lesson = (
        ordered_lessons[current_index + 1]
        if current_index is not None and current_index + 1 < len(ordered_lessons)
        else None
    )
    journal_entry = None
    if membership and user.is_student:
        journal_entry = db.query(GroupJournalEntry).filter(
            GroupJournalEntry.group_id == group_id,
            GroupJournalEntry.lesson_id == lesson_id,
            GroupJournalEntry.student_id == user.id,
        ).first()

    return templates.TemplateResponse("groups/lesson_view.html", {
        "request": request,
        "user": user,
        "group": group,
        "group_modules": group.modules,
        "lesson": lesson,
        "membership": membership,
        "ordered_lessons": ordered_lessons,
        "previous_lesson": previous_lesson,
        "next_lesson": next_lesson,
        "journal_entry": journal_entry,
        "can_preview_as_owner": can_preview_as_owner,
    })


# ═══════════════════════════════════════════════════════════
# VOCABULARY — СОЗДАНИЕ / РЕДАКТИРОВАНИЕ (teacher / org)
# ═══════════════════════════════════════════════════════════

import json as _json
import re as _re
from app.models.vocabulary import VocabularySet, VocabularyItem, VocabularyAttempt, VocabularyAttemptAnswer


def _parse_words_bulk(text: str) -> list[dict]:
    """
    Парсит текстовый блок в список слов.
    Формат каждой строки: слово = ответ1; ответ2; ответ3
    Возвращает список словарей с ключами prompt_word и accepted_answers (через |).
    """
    items = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line or "=" not in line:
            continue
        parts = line.split("=", 1)
        prompt = parts[0].strip()
        answers_raw = parts[1].strip()
        # Разделитель ответов — точка с запятой или запятая, нормализуем в |
        answers = [a.strip() for a in _re.split(r"[;,]", answers_raw) if a.strip()]
        if not prompt or not answers:
            continue
        items.append({
            "prompt_word": prompt,
            "accepted_answers": "|".join(answers),
            "position": i,
        })
    return items


@router.get("/{group_id}/lessons/{lesson_id}/vocabulary/create", response_class=HTMLResponse)
def vocab_create_page(
    group_id: int,
    lesson_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    return templates.TemplateResponse("groups/vocabulary_edit.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": None,
        "words_bulk": "",
        "can_preview_as_owner": True,
    })


@router.post("/{group_id}/lessons/{lesson_id}/vocabulary/create")
async def vocab_create(
    group_id: int,
    lesson_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    words_bulk: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = VocabularySet(
        lesson_id=lesson_id,
        title=title.strip(),
        description=description.strip() or None,
    )
    db.add(vocab)
    db.flush()  # получаем vocab.id

    for word_data in _parse_words_bulk(words_bulk):
        db.add(VocabularyItem(
            vocab_set_id=vocab.id,
            prompt_word=word_data["prompt_word"],
            accepted_answers=word_data["accepted_answers"],
            position=word_data["position"],
        ))

    db.commit()
    return RedirectResponse(
        f"/groups/{group_id}/manage?success=vocab_created",
        status_code=302,
    )


@router.get("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/edit", response_class=HTMLResponse)
def vocab_edit_page(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = db.query(VocabularySet).options(
        joinedload(VocabularySet.items)
    ).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    # Строим bulk-текст из существующих слов
    lines = []
    for item in sorted(vocab.items, key=lambda x: x.position):
        answers = item.accepted_answers or ""
        answers_display = answers.replace("|", "; ")
        lines.append(f"{item.prompt_word} = {answers_display}")
    words_bulk = "\n".join(lines)

    return templates.TemplateResponse("groups/vocabulary_edit.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": vocab,
        "words_bulk": words_bulk,
        "can_preview_as_owner": True,
    })


@router.post("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/edit")
async def vocab_edit(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    words_bulk: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    vocab = db.query(VocabularySet).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    vocab.title = title.strip()
    vocab.description = description.strip() or None

    # Удаляем старые слова и создаём новые
    db.query(VocabularyItem).filter(VocabularyItem.vocab_set_id == vocab_id).delete()

    for word_data in _parse_words_bulk(words_bulk):
        db.add(VocabularyItem(
            vocab_set_id=vocab.id,
            prompt_word=word_data["prompt_word"],
            accepted_answers=word_data["accepted_answers"],
            position=word_data["position"],
        ))

    db.commit()
    return RedirectResponse(
        f"/groups/{group_id}/manage?success=vocab_saved",
        status_code=302,
    )


@router.post("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/delete")
def vocab_delete(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    vocab = db.query(VocabularySet).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if vocab:
        db.delete(vocab)
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


# ═══════════════════════════════════════════════════════════
# VOCABULARY — ПРОСМОТР И ПРОХОЖДЕНИЕ (student)
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}", response_class=HTMLResponse)
def vocab_start_page(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    can_preview_as_owner = _can_manage_group_content(user, group, db)
    if not group.is_active and not can_preview_as_owner:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()

    if not membership and not can_preview_as_owner:
        raise HTTPException(status_code=403, detail="Нет доступа к этой группе")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = db.query(VocabularySet).options(
        joinedload(VocabularySet.items)
    ).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    # Последняя попытка студента
    last_attempt = None
    if membership:
        last_attempt = (
            db.query(VocabularyAttempt)
            .filter(
                VocabularyAttempt.vocab_set_id == vocab_id,
                VocabularyAttempt.student_id == user.id,
            )
            .order_by(VocabularyAttempt.completed_at.desc())
            .first()
        )

    # Может ли студент начать/повторить:
    # - ещё не проходил (last_attempt is None), ИЛИ
    # - попытка не завершена (in_progress), ИЛИ
    # - преподаватель разрешил повтор именно для этой попытки (retake_allowed), ИЛИ
    # - админ/org смотрит предпросмотр (can_preview_as_owner)
    can_retake = can_preview_as_owner or (last_attempt is None) or (not last_attempt.is_completed) or last_attempt.retake_allowed

    return templates.TemplateResponse("groups/vocabulary_start.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": vocab,
        "last_attempt": last_attempt,
        "membership": membership,
        "can_preview_as_owner": can_preview_as_owner,
        "can_retake": can_retake,
    })


@router.get("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/quiz", response_class=HTMLResponse)
def vocab_quiz_page(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    can_preview_as_owner = _can_manage_group_content(user, group, db)
    if not group.is_active and not can_preview_as_owner:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()

    if not membership and not can_preview_as_owner:
        raise HTTPException(status_code=403, detail="Нет доступа к этой группе")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = db.query(VocabularySet).options(
        joinedload(VocabularySet.items)
    ).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    existing_answers_data = []
    attempt_id = None

    if membership and not can_preview_as_owner:
        latest_attempt = (
            db.query(VocabularyAttempt)
            .filter(
                VocabularyAttempt.vocab_set_id == vocab_id,
                VocabularyAttempt.student_id == user.id,
            )
            .order_by(VocabularyAttempt.completed_at.desc())
            .first()
        )

        if latest_attempt:
            if latest_attempt.is_completed:
                if not latest_attempt.retake_allowed:
                    # Редирект на стартовую страницу — там студент увидит результат
                    return RedirectResponse(
                        f"/groups/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}",
                        status_code=302,
                    )
                else:
                    # Разрешен повтор: создаем новую попытку
                    new_attempt = VocabularyAttempt(
                        vocab_set_id=vocab_id,
                        student_id=user.id,
                        is_completed=False,
                    )
                    db.add(new_attempt)
                    # Сбрасываем разрешение на предыдущей попытке, чтобы не было бесконечных повторов
                    latest_attempt.retake_allowed = False
                    db.commit()
                    db.refresh(new_attempt)
                    attempt_id = new_attempt.id
            else:
                # Есть незавершенная попытка, продолжаем её
                attempt_id = latest_attempt.id
                existing_answers = (
                    db.query(VocabularyAttemptAnswer)
                    .filter(VocabularyAttemptAnswer.attempt_id == attempt_id)
                    .all()
                )
                existing_answers_data = [
                    {
                        "item_id": a.item_id,
                        "student_answer": a.student_answer,
                        "is_correct": a.is_correct
                    }
                    for a in existing_answers
                ]
        else:
            # Нет ни одной попытки, создаем первую
            new_attempt = VocabularyAttempt(
                vocab_set_id=vocab_id,
                student_id=user.id,
                is_completed=False,
            )
            db.add(new_attempt)
            db.commit()
            db.refresh(new_attempt)
            attempt_id = new_attempt.id

    items_data = [
        {
            "id": item.id,
            "prompt_word": item.prompt_word,
            "accepted_answers": item.accepted_answers or "",
            "accepted_answers_ru": item.accepted_answers_ru or "",
            "accepted_answers_tj": item.accepted_answers_tj or "",
        }
        for item in sorted(vocab.items, key=lambda x: x.position)
    ]

    return templates.TemplateResponse("groups/vocabulary_quiz.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": vocab,
        "items_json": _json.dumps(items_data, ensure_ascii=False),
        "existing_answers_json": _json.dumps(existing_answers_data, ensure_ascii=False),
        "attempt_id": attempt_id,
        "membership": membership,
    })


@router.post("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/attempts/{attempt_id}/answer")
async def vocab_submit_answer(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    attempt_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        raise HTTPException(status_code=401, detail="Not authenticated")

    attempt = db.query(VocabularyAttempt).filter(
        VocabularyAttempt.id == attempt_id,
        VocabularyAttempt.vocab_set_id == vocab_id,
        VocabularyAttempt.student_id == user.id,
    ).first()

    if not attempt or attempt.is_completed:
        from fastapi.responses import JSONResponse as _JSONResponse
        return _JSONResponse({"success": False, "detail": "Invalid or completed attempt"}, status_code=400)

    body = await request.json()
    item_id = body.get("item_id")
    student_answer = body.get("student_answer", "")
    is_correct = bool(body.get("is_correct"))
    lang = body.get("lang", "ru")
    
    attempt.lang_used = lang

    # Check if answer already exists
    existing_answer = db.query(VocabularyAttemptAnswer).filter(
        VocabularyAttemptAnswer.attempt_id == attempt.id,
        VocabularyAttemptAnswer.item_id == item_id
    ).first()

    if existing_answer:
        existing_answer.student_answer = student_answer
        existing_answer.is_correct = is_correct
    else:
        db.add(VocabularyAttemptAnswer(
            attempt_id=attempt.id,
            item_id=item_id,
            student_answer=student_answer,
            is_correct=is_correct,
        ))

    db.commit()
    from fastapi.responses import JSONResponse as _JSONResponse
    return _JSONResponse({"success": True})


@router.post("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/attempts/{attempt_id}/complete")
async def vocab_complete(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    attempt_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        raise HTTPException(status_code=401, detail="Not authenticated")

    attempt = db.query(VocabularyAttempt).filter(
        VocabularyAttempt.id == attempt_id,
        VocabularyAttempt.vocab_set_id == vocab_id,
        VocabularyAttempt.student_id == user.id,
    ).first()

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.is_completed:
        from fastapi.responses import JSONResponse as _JSONResponse
        return _JSONResponse({"success": True, "score": attempt.score, "total": attempt.total})

    # Recalculate score and total just to be safe
    answers = db.query(VocabularyAttemptAnswer).filter(
        VocabularyAttemptAnswer.attempt_id == attempt.id
    ).all()

    correct_count = sum(1 for a in answers if a.is_correct)
    total = len(answers)

    attempt.score = correct_count
    attempt.total = total
    attempt.is_completed = True
    attempt.completed_at = datetime.utcnow()

    db.commit()
    
    from fastapi.responses import JSONResponse as _JSONResponse
    return _JSONResponse({"success": True, "score": attempt.score, "total": attempt.total})


@router.get("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/results", response_class=HTMLResponse)
def vocab_results_page(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    lesson = db.query(GroupLesson).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    vocab = db.query(VocabularySet).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    attempts = (
        db.query(VocabularyAttempt)
        .options(joinedload(VocabularyAttempt.student))
        .filter(VocabularyAttempt.vocab_set_id == vocab_id)
        .order_by(VocabularyAttempt.completed_at.desc())
        .all()
    )

    return templates.TemplateResponse("groups/vocabulary_results.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "vocab": vocab,
        "attempts": attempts,
        "can_manage": True,
    })


# ═══════════════════════════════════════════════════════════
# VOCABULARY — Разрешить/запретить повторные попытки (teacher / org)
# ═══════════════════════════════════════════════════════════

@router.post("/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/toggle-retake")
async def vocab_toggle_retake(
    group_id: int,
    lesson_id: int,
    vocab_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Toggle retake_allowed on a specific student's latest vocabulary attempt. Only teacher/org can call this."""
    user = _get_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    vocab = db.query(VocabularySet).filter(
        VocabularySet.id == vocab_id,
        VocabularySet.lesson_id == lesson_id,
    ).first()
    if not vocab:
        raise HTTPException(status_code=404, detail="Словарь не найден")

    form_data = await request.form()
    student_id = form_data.get("student_id")
    if not student_id:
        raise HTTPException(status_code=400, detail="Missing student_id")

    latest_attempt = (
        db.query(VocabularyAttempt)
        .filter(
            VocabularyAttempt.vocab_set_id == vocab_id,
            VocabularyAttempt.student_id == student_id,
        )
        .order_by(VocabularyAttempt.completed_at.desc())
        .first()
    )

    if latest_attempt:
        latest_attempt.retake_allowed = not latest_attempt.retake_allowed
        db.commit()

    return RedirectResponse(
        f"/groups/{group_id}/lessons/{lesson_id}/vocabulary/{vocab_id}/results",
        status_code=302,
    )

import os
import shutil
import uuid
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.models.group import Group, GroupMember, GroupLesson, GroupMaterial
from app.ui import templates
from app.utils.image import compress_and_upload_avatar

router = APIRouter(prefix="/groups", tags=["groups"])

GROUP_AVATAR_DIR = os.path.join("static", "uploads", "group_avatars")
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
        .options(joinedload(Group.teacher), joinedload(Group.members))
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
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _, group = _get_org_for_group(group_id, user, db)

    if not avatar or not avatar.filename:
        return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)

    ext = os.path.splitext(avatar.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Invalid extension")

    os.makedirs(GROUP_AVATAR_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(GROUP_AVATAR_DIR, filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(avatar.file, buffer)

    group.avatar_url = f"/{save_path}"
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
        db.delete(member)
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


@router.post("/{group_id}/member/{member_id}/toggle-paid")
def group_toggle_paid(
    group_id: int,
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _get_org_for_group(group_id, user, db)

    member = db.query(GroupMember).filter(
        GroupMember.id == member_id,
        GroupMember.group_id == group_id,
    ).first()
    if member:
        member.is_paid = not member.is_paid
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
            joinedload(Group.teacher),
            joinedload(Group.members).joinedload(GroupMember.student),
            joinedload(Group.lessons).joinedload(GroupLesson.materials),
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
            "org_teachers": org_teachers,
            "available_students": available_students,
            "success": success,
            "error": error,
        })

    elif user.is_teacher:
        group = db.query(Group).options(
            joinedload(Group.teacher),
            joinedload(Group.members).joinedload(GroupMember.student),
            joinedload(Group.lessons).joinedload(GroupLesson.materials),
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
            "success": success,
            "error": error,
        })

    else:
        raise HTTPException(status_code=403, detail="Доступ запрещён")



# ═══════════════════════════════════════════════════════════
# LESSON ENDPOINTS (org & teacher)
# ═══════════════════════════════════════════════════════════

def _can_manage_lessons(user: User, group: Group, db: Session) -> bool:
    """Check if user can manage lessons in this group."""
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        return org and group.organization_id == org.id
    if user.is_teacher:
        return group.teacher_id == user.id
    return False


@router.post("/{group_id}/lessons/create")
async def lesson_create(
    group_id: int,
    request: Request,
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

    lesson = GroupLesson(
        group_id=group_id,
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


@router.post("/{group_id}/lessons/{lesson_id}/edit")
async def lesson_edit(
    group_id: int,
    lesson_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    video_url: Optional[str] = Form(None),
    order: int = Form(0),
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

    lesson.title = title.strip()
    lesson.description = description.strip() if description else None
    lesson.video_url = video_url.strip() if video_url else None
    lesson.order = order

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

    return templates.TemplateResponse("groups/student_view.html", {
        "request": request,
        "user": user,
        "group": group,
        "membership": membership,
    })


@router.get("/{group_id}/lessons/{lesson_id}", response_class=HTMLResponse)
def group_lesson_view(group_id: int, lesson_id: int, request: Request, db: Session = Depends(get_db)):
    """Просмотр конкретного урока группы для участника-студента."""
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).options(
        joinedload(Group.lessons),
        joinedload(Group.teacher),
    ).filter(Group.id == group_id, Group.is_active == True).first()

    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()
    can_preview_as_owner = bool(user.is_teacher and group.teacher_id == user.id)

    if not membership and not can_preview_as_owner:
        raise HTTPException(status_code=403, detail="Вы не являетесь членом этой группы")

    lesson = db.query(GroupLesson).options(
        joinedload(GroupLesson.materials)
    ).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id
    ).first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    return templates.TemplateResponse("groups/lesson_view.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "membership": membership,
    })

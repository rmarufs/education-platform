import os
import shutil
import uuid
import mimetypes
import calendar
from datetime import date, datetime
from urllib.parse import quote, urlparse
from urllib.request import urlopen
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session, joinedload, load_only, selectinload
from sqlalchemy import func, text
from typing import Optional, List
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.models.group import Group, GroupMember, GroupModule, GroupLesson, GroupMaterial, GroupJournalEntry, GroupLessonProgress, GroupHomework, GroupHomeworkSubmission, GroupHomeworkNotification, GroupPaymentEntry
from app.ui import templates
from app.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from app.utils.announcements import get_visible_announcements
from app.utils.image import upload_group_cover_image, upload_lesson_image
from app.utils.group_analytics import build_group_analytics
from app.utils.upload_constants import BASIC_DOCUMENT_EXTENSIONS, COVER_IMAGE_MAX_BYTES, IMAGE_EXTENSIONS, MATERIAL_MAX_BYTES
from app.utils.uploads import validate_upload_file

try:
    import cloudinary
    import cloudinary.uploader
except ModuleNotFoundError:
    cloudinary = None

router = APIRouter(prefix="/groups", tags=["groups"])

GROUP_MATERIAL_DIR = os.path.join("static", "uploads", "group_materials")
GROUP_MATERIAL_MAX_BYTES = MATERIAL_MAX_BYTES
GROUP_MATERIAL_EXTENSIONS = BASIC_DOCUMENT_EXTENSIONS
GROUP_LESSON_COVER_MAX_BYTES = COVER_IMAGE_MAX_BYTES
GROUP_LESSON_COVER_EXTENSIONS = IMAGE_EXTENSIONS
# Homework uploads use Cloudinary because Render's local filesystem is ephemeral.
# TODO(Render): group materials still use local static storage and have the same persistence risk.
GROUP_HOMEWORK_CLOUDINARY_FOLDER = "group_homework"
GROUP_HOMEWORK_MAX_BYTES = 50 * 1024 * 1024
GROUP_HOMEWORK_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt",
    ".jpg", ".jpeg", ".png", ".webp",
}
GROUP_HOMEWORK_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
GROUP_HOMEWORK_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v"}

if cloudinary:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )


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


def _validate_group_material_upload(file: UploadFile):
    if not file or not file.filename:
        return
    return validate_upload_file(
        file,
        allowed_extensions=GROUP_MATERIAL_EXTENSIONS,
        max_bytes=GROUP_MATERIAL_MAX_BYTES,
    )


def _validate_group_lesson_cover_upload(file: UploadFile) -> None:
    if not file or not file.filename:
        return
    validate_upload_file(
        file,
        allowed_extensions=GROUP_LESSON_COVER_EXTENSIONS,
        max_bytes=GROUP_LESSON_COVER_MAX_BYTES,
        invalid_type_message="Разрешены только JPG, JPEG, PNG и WEBP",
        too_large_message="Изображение должно быть не больше 5MB",
    )


def _validate_group_homework_upload(file: UploadFile):
    if not file or not file.filename:
        return
    ext = os.path.splitext(file.filename or "")[1].lower()
    content_type = (file.content_type or "").split(";", 1)[0].lower().strip()
    if ext in GROUP_HOMEWORK_VIDEO_EXTENSIONS or content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="homework.video_upload_not_allowed")
    return validate_upload_file(
        file,
        allowed_extensions=GROUP_HOMEWORK_EXTENSIONS,
        max_bytes=GROUP_HOMEWORK_MAX_BYTES,
    )


def _homework_file_type(filename: str | None, content_type: str | None = None) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in GROUP_HOMEWORK_IMAGE_EXTENSIONS or (content_type or "").startswith("image/"):
        return "image"
    if ext in GROUP_HOMEWORK_VIDEO_EXTENSIONS or (content_type or "").startswith("video/"):
        return "video"
    return "file"


def _homework_url_type(url: str) -> str:
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext in GROUP_HOMEWORK_IMAGE_EXTENSIONS:
        return "image"
    if ext in GROUP_HOMEWORK_VIDEO_EXTENSIONS or "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        return "video"
    return "link"


def _save_group_homework_upload(file: UploadFile, folder: str) -> tuple[str, str, str]:
    upload = _validate_group_homework_upload(file)
    original_name = upload.original_filename
    public_name = f"{uuid.uuid4().hex}_{upload.safe_filename}"
    if not cloudinary:
        raise HTTPException(status_code=500, detail="Cloudinary недоступен для загрузки файла")
    if hasattr(file.file, "seek"):
        file.file.seek(0)

    try:
        upload_result = cloudinary.uploader.upload(
            file.file,
            public_id=f"{GROUP_HOMEWORK_CLOUDINARY_FOLDER}/{folder}/{public_name}",
            resource_type="auto",
            use_filename=False,
            unique_filename=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Не удалось загрузить файл домашнего задания") from exc

    file_url = upload_result.get("secure_url")
    if not file_url:
        raise HTTPException(status_code=500, detail="Cloudinary не вернул ссылку на файл")
    return file_url, _homework_file_type(original_name, file.content_type), original_name


def _is_uploaded_file(value) -> bool:
    return bool(getattr(value, "filename", None) and getattr(value, "file", None))


def _download_remote_file(file_url: str, filename: str):
    parsed = urlparse(file_url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Некорректная ссылка на файл")

    content_type = mimetypes.guess_type(filename or "")[0] or "application/octet-stream"
    quoted_filename = quote(filename or "file")

    def iter_file():
        with urlopen(file_url, timeout=20) as response:
            while True:
                chunk = response.read(1024 * 64)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}",
        },
    )


def _parse_homework_deadline(value: str | None) -> datetime | None:
    clean_value = (value or "").strip()
    if not clean_value:
        return None
    try:
        return datetime.fromisoformat(clean_value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный дедлайн")


def _get_group_lesson(group_id: int, lesson_id: int, db: Session) -> GroupLesson:
    lesson = db.query(GroupLesson).options(
        joinedload(GroupLesson.group),
        joinedload(GroupLesson.homework),
    ).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    return lesson


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


def get_next_group_lesson_for_student(db: Session, group: Group, student_id: int) -> GroupLesson | None:
    ordered_lessons = _ordered_group_lessons(group)
    if not ordered_lessons:
        return None

    lesson_ids = [lesson.id for lesson in ordered_lessons]
    completed_lesson_ids = {
        lesson_id
        for (lesson_id,) in db.query(GroupLessonProgress.lesson_id).filter(
            GroupLessonProgress.group_id == group.id,
            GroupLessonProgress.student_id == student_id,
            GroupLessonProgress.lesson_id.in_(lesson_ids),
        ).all()
    }

    for lesson in ordered_lessons:
        if lesson.id not in completed_lesson_ids:
            return lesson

    return ordered_lessons[-1]


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


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _normalize_payment_day(payment_day: int, year: int, month: int) -> int:
    if payment_day < 1 or payment_day > 31:
        raise ValueError("payment_day must be between 1 and 31")
    return min(payment_day, _last_day_of_month(year, month))


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _calculate_paid_until(payment_day: int, payment_date: date) -> date:
    next_year, next_month = _next_month(payment_date.year, payment_date.month)
    next_normalized_day = _normalize_payment_day(payment_day, next_year, next_month)
    return date(next_year, next_month, next_normalized_day)


def _payment_status(paid_until: date | None, today: date | None = None) -> str:
    if not paid_until:
        return "unpaid"
    today = today or date.today()
    if today > paid_until:
        return "overdue"
    return "paid"


def _resolve_payment_day(value, fallback: int | None = None) -> int:
    raw_value = str(value if value is not None else fallback or 1).strip()
    try:
        payment_day = int(raw_value)
    except (TypeError, ValueError):
        return 1
    if payment_day < 1 or payment_day > 31:
        return 1
    return payment_day


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
        "visible_announcements": get_visible_announcements(db, user, limit=3),
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


@router.get("/{group_id:int}", response_class=HTMLResponse)
def group_detail(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Детали группы (org-only redirect to manage)."""
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _get_org_for_group(group_id, user, db)
    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


@router.post("/{group_id:int}/edit")
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


@router.post("/{group_id:int}/avatar")
def group_avatar(group_id: int, request: Request, avatar: UploadFile = File(...), db: Session = Depends(get_db)):
    _, group = _get_manageable_group(group_id, request, db)

    if not avatar or not avatar.filename:
        return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)

    try:
        validate_upload_file(
            avatar,
            allowed_extensions=GROUP_LESSON_COVER_EXTENSIONS,
            max_bytes=GROUP_LESSON_COVER_MAX_BYTES,
            invalid_type_message="Разрешены только JPG, JPEG, PNG и WEBP",
            too_large_message="Изображение должно быть не больше 5MB",
        )
    except HTTPException:
        return RedirectResponse(f"/groups/{group_id}/manage?error=invalid_image", status_code=302)

    avatar_url = upload_group_cover_image(
        avatar.file,
        public_id=f"groups/group_{group.id}"
    )
    if avatar_url:
        group.avatar_url = avatar_url
        db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=avatar", status_code=302)


@router.post("/{group_id:int}/delete")
def group_delete(group_id: int, request: Request, db: Session = Depends(get_db)):
    result, redirect = _require_org(request, db)
    if redirect:
        return redirect
    user, org = result
    _, group = _get_org_for_group(group_id, user, db)

    db.delete(group)
    db.commit()
    return RedirectResponse("/groups/", status_code=302)


@router.post("/{group_id:int}/assign-teacher")
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


@router.post("/{group_id:int}/add-student")
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


@router.post("/{group_id:int}/students/bulk-add")
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


@router.post("/{group_id:int}/remove-student/{student_id:int}")
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

@router.get("/{group_id:int}/manage", response_class=HTMLResponse)
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
            joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.homework),
            joinedload(Group.members).joinedload(GroupMember.student),
            joinedload(Group.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.lessons).joinedload(GroupLesson.group_module),
            joinedload(Group.lessons).joinedload(GroupLesson.homework),
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
            joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.homework),
            joinedload(Group.members).joinedload(GroupMember.student),
            joinedload(Group.lessons).joinedload(GroupLesson.materials),
            joinedload(Group.lessons).joinedload(GroupLesson.group_module),
            joinedload(Group.lessons).joinedload(GroupLesson.homework),
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


@router.get("/{group_id:int}/teach", response_class=HTMLResponse)
def group_teach(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Lesson selection for the assigned teacher's in-class mode."""
    user, redirect = _require_teacher(request, db)
    if redirect:
        return redirect

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.teacher),
        joinedload(Group.modules).joinedload(GroupModule.lessons).joinedload(GroupLesson.homework),
        joinedload(Group.lessons).joinedload(GroupLesson.group_module),
        joinedload(Group.lessons).joinedload(GroupLesson.homework),
    ).filter(
        Group.id == group_id,
        Group.teacher_id == user.id,
        Group.is_active == True,  # noqa: E712
    ).first()
    if not group:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return templates.TemplateResponse("groups/teach.html", {
        "request": request,
        "user": user,
        "group": group,
        "group_modules": group.modules,
        "ordered_lessons": _ordered_group_lessons(group),
    })


# ═══════════════════════════════════════════════════════════
# GROUP JOURNAL — ORG & TEACHER
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id:int}/journal", response_class=HTMLResponse)
def group_journal(group_id: int, request: Request, db: Session = Depends(get_db)):
    user, group = _get_manageable_group(group_id, request, db)

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.teacher),
        selectinload(Group.modules).selectinload(GroupModule.lessons),
        selectinload(Group.lessons),
        selectinload(Group.members).joinedload(GroupMember.student),
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


@router.post("/{group_id:int}/journal")
async def group_journal_save(group_id: int, request: Request, db: Session = Depends(get_db)):
    _, group = _get_manageable_group(group_id, request, db)

    group = db.query(Group).options(
        selectinload(Group.modules).selectinload(GroupModule.lessons),
        selectinload(Group.lessons),
        selectinload(Group.members),
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

@router.get("/{group_id:int}/payments", response_class=HTMLResponse)
def group_payments(group_id: int, request: Request, month: Optional[str] = None, db: Session = Depends(get_db)):
    user, group = _get_manageable_group(group_id, request, db)
    selected_month = _parse_month(month)

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.teacher),
        selectinload(Group.members).joinedload(GroupMember.student),
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
    payment_status_map = {
        member.student_id: _payment_status(member.paid_until)
        for member in members
    }
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

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    form_data = await request.form()
    selected_month = _parse_month(form_data.get("month"))

    group = db.query(Group).options(selectinload(Group.members)).filter(
        Group.id == group.id,
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    student_ids = [member.student_id for member in group.members]
    now = datetime.utcnow()
    payment_month = _month_start(now.date())
    entry_months = list({selected_month, payment_month})
    existing_entries = db.query(GroupPaymentEntry).filter(
        GroupPaymentEntry.group_id == group.id,
        GroupPaymentEntry.month.in_(entry_months),
        GroupPaymentEntry.student_id.in_(student_ids or [0]),
    ).all()
    entries_map = {
        (entry.student_id, entry.month): entry
        for entry in existing_entries
    }

    for member in group.members:
        student_id = member.student_id
        payment_day = _resolve_payment_day(
            form_data.get(f"payment_day_{student_id}"),
            member.payment_day,
        )
        member.payment_day = payment_day
        is_paid = f"paid_{student_id}" in form_data
        entry_month = payment_month if is_paid else selected_month
        entry = entries_map.get((student_id, entry_month))
        if not entry:
            entry = GroupPaymentEntry(
                group_id=group.id,
                student_id=student_id,
                month=entry_month,
            )
            db.add(entry)

        if is_paid:
            paid_until = _calculate_paid_until(payment_day, now.date())
            member.paid_until = paid_until
            member.last_paid_at = now

            entry.is_paid = True
            entry.paid_at = now
            entry.paid_until = paid_until
            entry.action = "paid"
        else:
            entry.is_paid = False
            entry.paid_at = None
            entry.paid_until = None
            entry.action = "cancelled"
        entry.marked_by_id = user.id
        entry.payment_day = payment_day

    db.commit()
    return _payment_redirect(group.id, selected_month, success="payments_saved")



# ═══════════════════════════════════════════════════════════
# LESSON ENDPOINTS (org & teacher)
# ═══════════════════════════════════════════════════════════

def _can_manage_lessons(user: User, group: Group, db: Session) -> bool:
    """Check if user can manage lessons in this group."""
    return _can_manage_group_content(user, group, db)


@router.post("/{group_id:int}/modules/create")
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


@router.post("/{group_id:int}/modules/{module_id:int}/edit")
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


@router.post("/{group_id:int}/modules/{module_id:int}/delete")
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


@router.post("/{group_id:int}/lessons/create")
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
    video_url_value = video_url.strip() if video_url and video_url.strip() else None
    has_cover_upload = bool(cover and cover.filename)
    if video_url_value and has_cover_upload:
        raise HTTPException(status_code=400, detail="Можно добавить либо видео, либо картинку")
    if has_cover_upload:
        _validate_group_lesson_cover_upload(cover)

    lesson = GroupLesson(
        group_id=group_id,
        group_module_id=module.id if module else None,
        title=title.strip(),
        description=description.strip() if description else None,
        video_url=video_url_value,
        order=order,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    if has_cover_upload:
        cover_url = upload_lesson_image(
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
            if _is_uploaded_file(f):
                upload = _validate_group_material_upload(f)
                original_name = upload.original_filename
                filename = f"{uuid.uuid4().hex}_{upload.safe_filename}"
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


@router.get("/{group_id:int}/lessons/create")
async def group_lesson_create_get(group_id: int):
    return RedirectResponse(
        url=f"/groups/{group_id}/manage",
        status_code=303,
    )


@router.get("/{group_id:int}/lessons/{lesson_id:int}/edit", response_class=HTMLResponse)
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


@router.post("/{group_id:int}/lessons/{lesson_id:int}/edit")
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
    remove_cover: str = Form("0"),
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
    video_url_value = video_url.strip() if video_url and video_url.strip() else None
    has_cover_upload = bool(cover and cover.filename)
    if video_url_value and has_cover_upload:
        raise HTTPException(status_code=400, detail="Можно добавить либо видео, либо картинку")
    if has_cover_upload:
        _validate_group_lesson_cover_upload(cover)
    lesson.video_url = video_url_value
    lesson.order = order
    if video_url_value or remove_cover == "1":
        lesson.cover_url = None

    if has_cover_upload:
        cover_url = upload_lesson_image(
            cover.file,
            public_id=f"group_lessons/lesson_{lesson.id}"
        )
        if cover_url:
            lesson.cover_url = cover_url
            lesson.video_url = None

    # Process files if any
    form_data = await request.form()
    files = form_data.getlist("files")
    if files:
        os.makedirs(GROUP_MATERIAL_DIR, exist_ok=True)
        for f in files:
            if _is_uploaded_file(f):
                upload = _validate_group_material_upload(f)
                original_name = upload.original_filename
                filename = f"{uuid.uuid4().hex}_{upload.safe_filename}"
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


@router.post("/{group_id:int}/lessons/{lesson_id:int}/delete")
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
        homework_ids = [lesson.homework.id] if lesson.homework else []
        if homework_ids:
            try:
                db.query(GroupHomeworkNotification).filter(
                    GroupHomeworkNotification.homework_id.in_(homework_ids)
                ).delete(synchronize_session=False)
                db.commit()
            except DatabaseError:
                db.rollback()
        db.delete(lesson)
        db.commit()

    return RedirectResponse(f"/groups/{group_id}/manage", status_code=302)


@router.post("/{group_id:int}/lessons/{lesson_id:int}/materials/add")
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
        upload = _validate_group_material_upload(file)
        os.makedirs(GROUP_MATERIAL_DIR, exist_ok=True)
        original_name = upload.original_filename
        filename = f"{uuid.uuid4().hex}_{upload.safe_filename}"
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


@router.post("/{group_id:int}/lessons/{lesson_id:int}/materials/{material_id:int}/delete")
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
# GROUP HOMEWORK — ORG / TEACHER / STUDENT
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id:int}/lessons/{lesson_id:int}/homework", response_class=HTMLResponse)
def group_homework_view(group_id: int, lesson_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    lesson = _get_group_lesson(group_id, lesson_id, db)
    group = lesson.group
    homework = lesson.homework
    mode = request.query_params.get("mode", "").strip()
    is_teach_mode = mode == "teach" and user.is_teacher and group.teacher_id == user.id
    can_manage = _can_manage_group_content(user, group, db)
    if not group.is_active and not can_manage:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = None
    if user.is_student:
        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.student_id == user.id,
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Вы не являетесь членом этой группы")
    elif not can_manage and not is_teach_mode:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    submission = None
    if homework and user.is_student:
        submission = db.query(GroupHomeworkSubmission).filter(
            GroupHomeworkSubmission.homework_id == homework.id,
            GroupHomeworkSubmission.student_id == user.id,
        ).first()

    deadline_passed = bool(homework and homework.deadline and homework.deadline < datetime.utcnow())
    success = request.query_params.get("success")
    error = request.query_params.get("error")

    return templates.TemplateResponse("groups/homework.html", {
        "request": request,
        "user": user,
        "group": group,
        "lesson": lesson,
        "homework": homework,
        "submission": submission,
        "deadline_passed": deadline_passed,
        "can_manage": can_manage,
        "is_teach_mode": is_teach_mode,
        "can_submit": bool(homework and user.is_student and membership),
        "success": success,
        "error": error,
    })


@router.post("/{group_id:int}/lessons/{lesson_id:int}/homework/save")
async def group_homework_save(
    group_id: int,
    lesson_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    material_url: Optional[str] = Form(None),
    deadline_enabled: Optional[str] = Form(None),
    deadline: Optional[str] = Form(None),
    material_file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user, group = _get_manageable_group(group_id, request, db)
    lesson = _get_group_lesson(group.id, lesson_id, db)

    clean_description = description.strip()
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Добавьте название домашнего задания")
    if not clean_description:
        raise HTTPException(status_code=400, detail="Добавьте описание домашнего задания")

    homework = lesson.homework
    is_new_homework = homework is None
    if not homework:
        homework = GroupHomework(
            group_id=group.id,
            lesson_id=lesson.id,
            created_by_id=user.id,
            description=clean_description,
        )
        db.add(homework)

    homework.title = clean_title
    homework.description = clean_description
    deadline_is_enabled = deadline_enabled == "1"
    if deadline_is_enabled and not (deadline or "").strip():
        raise HTTPException(status_code=400, detail="homework.deadline_required")
    homework.deadline = _parse_homework_deadline(deadline) if deadline_is_enabled else None

    if material_file and material_file.filename:
        try:
            file_url, file_type, filename = _save_group_homework_upload(material_file, "materials")
        except HTTPException as exc:
            if exc.detail == "homework.video_upload_not_allowed":
                db.rollback()
                return RedirectResponse(f"/groups/{group_id}/manage?error=homework_video_upload", status_code=302)
            raise
        homework.material_url = file_url
        homework.material_type = file_type
        homework.material_filename = filename
    elif material_url and material_url.strip():
        clean_url = material_url.strip()
        parsed = urlparse(clean_url)
        if not all([parsed.scheme, parsed.netloc]):
            raise HTTPException(status_code=400, detail="Некорректная ссылка на материал")
        homework.material_url = clean_url
        homework.material_type = _homework_url_type(clean_url)
        homework.material_filename = clean_url.split("/")[-1] or clean_url

    db.commit()
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"### DEBUG HW PUSH: group_id={group.id}, homework_id={homework.id}, is_new_homework={is_new_homework}")
    if is_new_homework:
        try:
            student_ids = [
                student_id for (student_id,) in db.query(GroupMember.student_id)
                .filter(GroupMember.group_id == group.id)
                .all()
            ]
            logger.info(f"### DEBUG HW PUSH: Found {len(student_ids)} students in group: {student_ids}")
            notifications_created = []
            for student_id in student_ids:
                notif = GroupHomeworkNotification(
                    homework_id=homework.id,
                    student_id=student_id,
                    notification_type="new_homework",
                )
                db.add(notif)
                notifications_created.append(notif)
            db.commit()

            try:
                from app.utils.push import send_push_to_user
                for notif in notifications_created:
                    send_push_to_user(
                        db=db,
                        user_id=notif.student_id,
                        title="Новое домашнее задание",
                        body=homework.title,
                        target_url=f"/dashboard/student/homework-notifications/{notif.id}/open",
                        notification_type="new_homework",
                        entity_id=notif.id
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"### DEBUG HW PUSH: Error inside inner push loop: {e}")

        except Exception as outer_e:
            import logging
            logging.getLogger(__name__).error(f"### DEBUG HW PUSH: db.commit() failed for notifications or outer exception: {outer_e}")
            db.rollback()
    return RedirectResponse(f"/groups/{group_id}/manage?success=homework_saved", status_code=302)


@router.post("/{group_id:int}/lessons/{lesson_id:int}/homework/delete")
def group_homework_delete(group_id: int, lesson_id: int, request: Request, db: Session = Depends(get_db)):
    _, group = _get_manageable_group(group_id, request, db)
    lesson = _get_group_lesson(group.id, lesson_id, db)
    if lesson.homework:
        try:
            db.query(GroupHomeworkNotification).filter(
                GroupHomeworkNotification.homework_id == lesson.homework.id
            ).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.delete(lesson.homework)
        db.commit()
    return RedirectResponse(f"/groups/{group_id}/manage?success=homework_deleted", status_code=302)


@router.post("/{group_id:int}/lessons/{lesson_id:int}/homework/submit")
async def group_homework_submit(
    group_id: int,
    lesson_id: int,
    request: Request,
    answer_file: Optional[UploadFile] = File(None),
    comment: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect
    if not user.is_student:
        raise HTTPException(status_code=403, detail="Только ученики могут отправлять ответы")

    lesson = _get_group_lesson(group_id, lesson_id, db)
    homework = lesson.homework
    if not homework:
        raise HTTPException(status_code=404, detail="Домашнее задание не найдено")
    if not lesson.group.is_active:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember.id).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Вы не являетесь членом этой группы")

    if homework.deadline and homework.deadline < datetime.utcnow():
        return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}/homework?error=deadline_passed", status_code=302)

    clean_comment = comment.strip() if comment and comment.strip() else None
    has_file = bool(answer_file and answer_file.filename)
    if not has_file and not clean_comment:
        return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}/homework?error=answer_required", status_code=302)

    file_url = None
    file_type = None
    filename = None
    if has_file:
        try:
            file_url, file_type, filename = _save_group_homework_upload(answer_file, "submissions")
        except HTTPException as exc:
            if exc.detail == "homework.video_upload_not_allowed":
                db.rollback()
                return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}/homework?error=video_upload_not_allowed", status_code=302)
            raise

    submission = db.query(GroupHomeworkSubmission).filter(
        GroupHomeworkSubmission.homework_id == homework.id,
        GroupHomeworkSubmission.student_id == user.id,
    ).first()
    now = datetime.utcnow()
    if submission:
        if has_file:
            submission.file_url = file_url
            submission.file_type = file_type
            submission.filename = filename
        submission.comment = clean_comment
        submission.updated_at = now
    else:
        submission = GroupHomeworkSubmission(
            homework_id=homework.id,
            student_id=user.id,
            file_url=file_url,
            file_type=file_type,
            filename=filename,
            comment=clean_comment,
            submitted_at=now,
            updated_at=now,
        )
        db.add(submission)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}/homework?error=submit_error", status_code=302)

    return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}/homework?success=submit_success", status_code=302)


@router.get("/{group_id:int}/lessons/{lesson_id:int}/homework/material/download")
def group_homework_material_download(
    group_id: int,
    lesson_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    lesson = _get_group_lesson(group_id, lesson_id, db)
    homework = lesson.homework
    if not homework or not homework.material_url:
        raise HTTPException(status_code=404, detail="Файл не найден")

    is_member = db.query(GroupMember.id).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first() is not None
    if not (_can_manage_group_content(user, lesson.group, db) or is_member):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return _download_remote_file(homework.material_url, homework.material_filename or "homework-file")


@router.get("/{group_id:int}/lessons/{lesson_id:int}/homework/submissions/{submission_id:int}/download")
def group_homework_submission_download(
    group_id: int,
    lesson_id: int,
    submission_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    lesson = _get_group_lesson(group_id, lesson_id, db)
    submission = db.query(GroupHomeworkSubmission).join(GroupHomework).filter(
        GroupHomeworkSubmission.id == submission_id,
        GroupHomework.lesson_id == lesson.id,
        GroupHomework.group_id == group_id,
    ).first()
    if not submission or not submission.file_url:
        raise HTTPException(status_code=404, detail="Файл не найден")

    if not (_can_manage_group_content(user, lesson.group, db) or submission.student_id == user.id):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return _download_remote_file(submission.file_url, submission.filename or "homework-submission")


@router.get("/{group_id:int}/homework/review", response_class=HTMLResponse)
def group_homework_review(group_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.members).joinedload(GroupMember.student),
        joinedload(Group.modules)
            .joinedload(GroupModule.lessons)
            .joinedload(GroupLesson.homework)
            .joinedload(GroupHomework.submissions)
            .joinedload(GroupHomeworkSubmission.student),
        joinedload(Group.lessons)
            .joinedload(GroupLesson.homework)
            .joinedload(GroupHomework.submissions)
            .joinedload(GroupHomeworkSubmission.student),
    ).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if not _can_manage_group_content(user, group, db):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    members = sorted(
        [member for member in group.members if member.student],
        key=lambda member: (member.student.name or "").lower(),
    )
    ordered_lessons = _ordered_group_lessons(group)
    now = datetime.utcnow()
    selected_lesson_id = request.query_params.get("lesson_id")
    try:
        selected_lesson_id_int = int(selected_lesson_id) if selected_lesson_id else None
    except ValueError:
        selected_lesson_id_int = None

    homework_items = []
    selected_item = None
    for lesson in ordered_lessons:
        homework = lesson.homework
        if not homework:
            continue

        submissions = homework.submissions or []
        submitted_student_ids = {submission.student_id for submission in submissions}
        checked_student_ids = {submission.student_id for submission in submissions if submission.reviewed_at}
        item = {
            "lesson": lesson,
            "homework": homework,
            "deadline_passed": bool(homework.deadline and homework.deadline < now),
            "submitted_count": len(submitted_student_ids),
            "unsubmitted_count": max(len(members) - len(submitted_student_ids), 0),
            "checked_count": len(checked_student_ids),
            "pending_count": max(len(submitted_student_ids) - len(checked_student_ids), 0),
        }
        homework_items.append(item)
        if selected_lesson_id_int == lesson.id:
            selected_item = item

    review_rows = []
    if selected_item:
        submissions_by_student = {
            submission.student_id: submission
            for submission in selected_item["homework"].submissions or []
        }
        deadline_passed = selected_item["deadline_passed"]
        for member in members:
            submission = submissions_by_student.get(member.student_id)
            if submission and submission.reviewed_at:
                status = "checked"
            elif submission:
                status = "pending_review"
            elif deadline_passed:
                status = "overdue"
            else:
                status = "not_submitted"
            review_rows.append({
                "member": member,
                "student": member.student,
                "submission": submission,
                "status": status,
            })

    success = request.query_params.get("success")

    return templates.TemplateResponse("groups/homework_review.html", {
        "request": request,
        "user": user,
        "group": group,
        "homework_items": homework_items,
        "selected_item": selected_item,
        "review_rows": review_rows,
        "success": success,
    })


@router.post("/{group_id:int}/homework/review/{submission_id:int}")
def group_homework_review_save(
    group_id: int,
    submission_id: int,
    request: Request,
    teacher_comment: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user, group = _get_manageable_group(group_id, request, db)
    submission = db.query(GroupHomeworkSubmission).join(GroupHomework).filter(
        GroupHomeworkSubmission.id == submission_id,
        GroupHomework.group_id == group.id,
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Ответ не найден")

    previous_comment = (submission.teacher_comment or "").strip()
    clean_teacher_comment = teacher_comment.strip() if teacher_comment and teacher_comment.strip() else None
    submission.teacher_comment = clean_teacher_comment
    if clean_teacher_comment and clean_teacher_comment != previous_comment:
        submission.homework_reply_read_at = None
    elif not clean_teacher_comment:
        submission.homework_reply_read_at = None
    submission.reviewed_at = datetime.utcnow()
    submission.reviewed_by_id = user.id
    db.commit()

    try:
        from app.utils.push import send_push_to_user
        send_push_to_user(
            db=db,
            user_id=submission.student_id,
            title="Домашнее задание проверено",
            body="Преподаватель оставил ответ/оценку",
            target_url=f"/dashboard/student/homework-replies/{submission.id}/open",
            notification_type="homework_reviewed",
            entity_id=submission.id
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error sending push for homework review: {e}")

    lesson_id = submission.homework.lesson_id
    return RedirectResponse(f"/groups/{group_id}/homework/review?lesson_id={lesson_id}&success=review_saved", status_code=302)


# ═══════════════════════════════════════════════════════════
# STUDENT VIEW
# ═══════════════════════════════════════════════════════════

@router.get("/{group_id:int}/continue")
def group_continue(group_id: int, request: Request, db: Session = Depends(get_db)):
    """Redirect a student to the first available group lesson, or fallback to group view."""
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect

    group = db.query(Group).options(
        joinedload(Group.modules).joinedload(GroupModule.lessons),
        joinedload(Group.lessons),
    ).filter(Group.id == group_id, Group.is_active == True).first()

    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember.id).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()

    if not membership:
        return RedirectResponse("/dashboard/student?error=access_denied", status_code=302)

    next_lesson = get_next_group_lesson_for_student(db, group, user.id)
    if next_lesson:
        return RedirectResponse(
            f"/groups/{group.id}/lessons/{next_lesson.id}",
            status_code=303,
        )

    return RedirectResponse(f"/groups/{group.id}/view", status_code=303)


@router.get("/{group_id:int}/view", response_class=HTMLResponse)
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
        completed_lesson = (
            db.query(GroupLessonProgress.id)
            .filter(
                GroupLessonProgress.group_id == group_id,
                GroupLessonProgress.student_id == user.id,
                GroupLessonProgress.lesson_id.in_(ordered_lesson_ids),
            )
            .first()
        )
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
        group_has_progress = bool(completed_lesson or journal_progress or vocab_progress)
    return templates.TemplateResponse("groups/student_view.html", {
        "request": request,
        "user": user,
        "group": group,
        "group_modules": group.modules,
        "ordered_lessons": ordered_lessons,
        "group_has_progress": group_has_progress,
        "membership": membership,
    })


@router.get("/{group_id:int}/lessons/{lesson_id:int}", response_class=HTMLResponse)
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
    is_teach_mode = request.query_params.get("mode", "").strip() == "teach" and user.is_teacher and group.teacher_id == user.id
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
        joinedload(GroupLesson.homework),
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
    group_progress = None
    group_progress_data = {}
    if membership and user.is_student:
        journal_entry = db.query(GroupJournalEntry).filter(
            GroupJournalEntry.group_id == group_id,
            GroupJournalEntry.lesson_id == lesson_id,
            GroupJournalEntry.student_id == user.id,
        ).first()
        lesson_ids = [item.id for item in ordered_lessons]
        progress_rows = (
            db.query(GroupLessonProgress)
            .filter(
                GroupLessonProgress.group_id == group_id,
                GroupLessonProgress.student_id == user.id,
                GroupLessonProgress.lesson_id.in_(lesson_ids),
            )
            .all()
        ) if lesson_ids else []
        group_progress_data = {progress.lesson_id: True for progress in progress_rows}
        group_progress = next(
            (progress for progress in progress_rows if progress.lesson_id == lesson_id),
            None,
        )

    vocabulary_anticheat_warnings = []
    if is_teach_mode:
        vocab_ids = [vocab.id for vocab in lesson.vocabularies]
        if vocab_ids:
            try:
                warning_attempts = (
                    db.query(VocabularyAttempt)
                    .options(
                        joinedload(VocabularyAttempt.student),
                        joinedload(VocabularyAttempt.vocab_set),
                    )
                    .filter(
                        VocabularyAttempt.vocab_set_id.in_(vocab_ids),
                        VocabularyAttempt.anti_cheat_teacher_visible.is_(True),
                    )
                    .order_by(
                        VocabularyAttempt.anti_cheat_last_flag_at.desc(),
                        VocabularyAttempt.id.desc(),
                    )
                    .limit(50)
                    .all()
                )
            except DatabaseError as exc:
                db.rollback()
                if not _is_vocabulary_anticheat_schema_mismatch(exc):
                    raise
                warning_attempts = []
            seen_warning_keys = set()
            for attempt in warning_attempts:
                warning_key = (attempt.student_id, attempt.vocab_set_id)
                if warning_key in seen_warning_keys:
                    continue
                seen_warning_keys.add(warning_key)
                vocabulary_anticheat_warnings.append({
                    "attempt_id": attempt.id,
                    "student_name": attempt.student.name if attempt.student else "",
                    "vocab_title": attempt.vocab_set.title if attempt.vocab_set else "",
                    "flagged_at": attempt.anti_cheat_last_flag_at,
                })

    template_context = {
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
        "group_progress": group_progress,
        "group_progress_data": group_progress_data,
        "can_preview_as_owner": can_preview_as_owner,
        "is_teach_mode": is_teach_mode,
        "lesson_mode_suffix": "?mode=teach" if is_teach_mode else "",
    }
    if is_teach_mode:
        template_context["vocabulary_anticheat_warnings"] = vocabulary_anticheat_warnings

    return templates.TemplateResponse("groups/lesson_view.html", template_context)


@router.post("/{group_id:int}/lessons/{lesson_id:int}/complete")
def group_lesson_complete(group_id: int, lesson_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = _require_login(request, db)
    if redirect:
        return redirect
    if not user.is_student:
        raise HTTPException(status_code=403, detail="Только ученики могут отмечать урок как пройденный")

    group = db.query(Group).filter(
        Group.id == group_id,
        Group.is_active == True,  # noqa: E712
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember.id).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Вы не являетесь членом этой группы")

    lesson = db.query(GroupLesson.id).filter(
        GroupLesson.id == lesson_id,
        GroupLesson.group_id == group_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")

    progress = db.query(GroupLessonProgress).filter(
        GroupLessonProgress.group_id == group_id,
        GroupLessonProgress.lesson_id == lesson_id,
        GroupLessonProgress.student_id == user.id,
    ).first()
    if not progress:
        db.add(GroupLessonProgress(
            group_id=group_id,
            lesson_id=lesson_id,
            student_id=user.id,
            completed_at=datetime.utcnow(),
        ))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

    next_url = request.query_params.get("next")
    allowed_prefixes = (
        f"/groups/{group_id}/lessons/",
        f"/groups/{group_id}/view",
    )
    if next_url and next_url.startswith(allowed_prefixes):
        return RedirectResponse(next_url, status_code=302)

    return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}", status_code=302)


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


def _is_vocabulary_anticheat_schema_mismatch(exc: DatabaseError) -> bool:
    anti_cheat_columns = (
        "anti_cheat_flags_count",
        "anti_cheat_teacher_visible",
        "anti_cheat_last_flag_at",
    )
    orig = getattr(exc, "orig", None)
    parts = [str(exc), exc.__class__.__name__]
    if orig:
        parts.extend([
            str(orig),
            orig.__class__.__name__,
            str(getattr(orig, "pgcode", "")),
            str(getattr(orig, "sqlstate", "")),
        ])
    message = " ".join(part for part in parts if part).lower()
    if not any(column in message for column in anti_cheat_columns):
        return False

    undefined_column_codes = {"42703"}
    if getattr(orig, "pgcode", None) in undefined_column_codes or getattr(orig, "sqlstate", None) in undefined_column_codes:
        return True

    missing_column_markers = (
        "undefinedcolumn",
        "undefined column",
        "no such column",
        "has no column",
        "no column named",
        "does not exist",
        "unknown column",
        "column not found",
    )
    return any(marker in message for marker in missing_column_markers)


def _create_vocabulary_attempt_record(db: Session, vocab_id: int, student_id: int) -> int:
    new_attempt = VocabularyAttempt(
        vocab_set_id=vocab_id,
        student_id=student_id,
        is_completed=False,
    )
    db.add(new_attempt)
    try:
        db.commit()
        db.refresh(new_attempt)
        return new_attempt.id
    except DatabaseError as exc:
        db.rollback()
        if not _is_vocabulary_anticheat_schema_mismatch(exc):
            raise

    attempt_id = db.execute(
        text(
            """
            INSERT INTO vocabulary_attempts
                (vocab_set_id, student_id, score, total, lang_used, is_completed, retake_allowed, completed_at)
            VALUES
                (:vocab_set_id, :student_id, 0, 0, 'ru', :is_completed, :retake_allowed, :completed_at)
            RETURNING id
            """
        ),
        {
            "vocab_set_id": vocab_id,
            "student_id": student_id,
            "is_completed": False,
            "retake_allowed": False,
            "completed_at": datetime.utcnow(),
        },
    ).scalar_one()
    db.commit()
    return attempt_id


@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/create", response_class=HTMLResponse)
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


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/create")
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


@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/edit", response_class=HTMLResponse)
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


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/edit")
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


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/delete")
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

@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}", response_class=HTMLResponse)
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
            .options(load_only(
                VocabularyAttempt.id,
                VocabularyAttempt.completed_at,
                VocabularyAttempt.is_completed,
                VocabularyAttempt.retake_allowed,
                VocabularyAttempt.score,
                VocabularyAttempt.total,
            ))
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


@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/quiz", response_class=HTMLResponse)
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
            .options(load_only(
                VocabularyAttempt.id,
                VocabularyAttempt.completed_at,
                VocabularyAttempt.is_completed,
                VocabularyAttempt.retake_allowed,
            ))
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
                    previous_attempt_id = latest_attempt.id
                    should_clear_retake = latest_attempt.retake_allowed
                    attempt_id = _create_vocabulary_attempt_record(db, vocab_id, user.id)
                    if should_clear_retake:
                        # Сбрасываем разрешение на предыдущей попытке, чтобы не было бесконечных повторов
                        db.query(VocabularyAttempt).filter(
                            VocabularyAttempt.id == previous_attempt_id,
                        ).update(
                            {VocabularyAttempt.retake_allowed: False},
                            synchronize_session=False,
                        )
                        db.commit()
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
            attempt_id = _create_vocabulary_attempt_record(db, vocab_id, user.id)

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


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/attempts/{attempt_id:int}/answer")
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
    ).options(load_only(
        VocabularyAttempt.id,
        VocabularyAttempt.is_completed,
        VocabularyAttempt.lang_used,
    )).first()

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


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/attempts/{attempt_id:int}/anti-cheat/second-warning")
async def vocab_report_second_anticheat_warning(
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
    if not user.is_student:
        raise HTTPException(status_code=403, detail="Only students can report vocabulary anti-cheat warnings")

    try:
        attempt = db.query(VocabularyAttempt).filter(
            VocabularyAttempt.id == attempt_id,
            VocabularyAttempt.vocab_set_id == vocab_id,
            VocabularyAttempt.student_id == user.id,
        ).options(load_only(
            VocabularyAttempt.id,
            VocabularyAttempt.is_completed,
            VocabularyAttempt.anti_cheat_flags_count,
            VocabularyAttempt.anti_cheat_teacher_visible,
            VocabularyAttempt.anti_cheat_last_flag_at,
        )).first()
    except DatabaseError as exc:
        db.rollback()
        if not _is_vocabulary_anticheat_schema_mismatch(exc):
            raise
        return JSONResponse({"success": False, "detail": "Anti-cheat migration required"}, status_code=503)

    if not attempt:
        return JSONResponse({"success": False, "detail": "Attempt not found"}, status_code=404)
    if attempt.is_completed:
        return JSONResponse({"success": False, "detail": "Attempt is completed"}, status_code=400)
    if attempt.anti_cheat_teacher_visible:
        return JSONResponse({"success": True})

    try:
        updated_rows = (
            db.query(VocabularyAttempt)
            .filter(
                VocabularyAttempt.id == attempt.id,
                VocabularyAttempt.anti_cheat_teacher_visible.is_(False),
            )
            .update(
                {
                    VocabularyAttempt.anti_cheat_flags_count: max(attempt.anti_cheat_flags_count or 0, 2),
                    VocabularyAttempt.anti_cheat_teacher_visible: True,
                    VocabularyAttempt.anti_cheat_last_flag_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        if updated_rows:
            db.commit()
        else:
            db.rollback()
    except DatabaseError as exc:
        db.rollback()
        if not _is_vocabulary_anticheat_schema_mismatch(exc):
            raise
        return JSONResponse({"success": False, "detail": "Anti-cheat migration required"}, status_code=503)

    return JSONResponse({"success": True})


@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/attempts/{attempt_id:int}/complete")
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
    ).options(load_only(
        VocabularyAttempt.id,
        VocabularyAttempt.completed_at,
        VocabularyAttempt.is_completed,
        VocabularyAttempt.score,
        VocabularyAttempt.total,
    )).first()

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
    response_score = attempt.score
    response_total = attempt.total

    db.commit()
    
    from fastapi.responses import JSONResponse as _JSONResponse
    return _JSONResponse({"success": True, "score": response_score, "total": response_total})


@router.get("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/results", response_class=HTMLResponse)
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
        .options(
            load_only(
                VocabularyAttempt.id,
                VocabularyAttempt.student_id,
                VocabularyAttempt.score,
                VocabularyAttempt.total,
                VocabularyAttempt.is_completed,
                VocabularyAttempt.retake_allowed,
                VocabularyAttempt.completed_at,
            ),
            joinedload(VocabularyAttempt.student),
        )
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

@router.post("/{group_id:int}/lessons/{lesson_id:int}/vocabulary/{vocab_id:int}/toggle-retake")
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
        .options(load_only(
            VocabularyAttempt.id,
            VocabularyAttempt.completed_at,
            VocabularyAttempt.retake_allowed,
        ))
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

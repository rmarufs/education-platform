import os
import shutil
import uuid
import mimetypes
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
from app.services.group_lesson_service import ordered_group_lessons as _ordered_group_lessons
from app.deps.auth import get_user as _get_user
from app.models.user import User
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.models.group import Group, GroupMember, GroupModule, GroupLesson, GroupMaterial, GroupJournalEntry, GroupLessonProgress, GroupHomework, GroupHomeworkSubmission, GroupHomeworkNotification, GroupPaymentEntry
from app.ui import templates
from app.utils.announcements import get_visible_announcements
from app.utils.image import upload_group_cover_image, upload_lesson_image
from app.utils.group_analytics import build_group_analytics
from app.utils.datetime_helpers import (
    calculate_paid_until as _calculate_paid_until,
    month_start as _month_start,
    parse_homework_deadline as _parse_homework_deadline,
    parse_month as _parse_month,
    payment_status as _payment_status,
    resolve_payment_day as _resolve_payment_day,
)
from app.utils.upload_constants import BASIC_DOCUMENT_EXTENSIONS, COVER_IMAGE_MAX_BYTES, IMAGE_EXTENSIONS, MATERIAL_MAX_BYTES
from app.utils.uploads import validate_upload_file

from app.deps.cloudinary import cloudinary

router = APIRouter(prefix="/groups", tags=["groups"])

from app.routers import group_crud
router.include_router(group_crud.router)

from app.routers import group_modules
router.include_router(group_modules.router)

from app.routers import group_lessons
router.include_router(group_lessons.router)

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


class BulkAddStudentsPayload(BaseModel):
    student_ids: List[int]
    grade: Optional[int] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

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


    next_url = request.query_params.get("next")
    allowed_prefixes = (
        f"/groups/{group_id}/lessons/",
    )
    if next_url and next_url.startswith(allowed_prefixes):
        return RedirectResponse(next_url, status_code=302)

    return RedirectResponse("/dashboard/student", status_code=302)


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

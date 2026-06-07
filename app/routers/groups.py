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

from app.routers import group_journal
router.include_router(group_journal.router)

from app.routers import group_payments
router.include_router(group_payments.router)

from app.routers import group_homework
router.include_router(group_homework.router)

from app.routers import group_vocabulary
router.include_router(group_vocabulary.router)

GROUP_MATERIAL_DIR = os.path.join("static", "uploads", "group_materials")
GROUP_MATERIAL_MAX_BYTES = MATERIAL_MAX_BYTES
GROUP_MATERIAL_EXTENSIONS = BASIC_DOCUMENT_EXTENSIONS
GROUP_LESSON_COVER_MAX_BYTES = COVER_IMAGE_MAX_BYTES
GROUP_LESSON_COVER_EXTENSIONS = IMAGE_EXTENSIONS
# Homework uploads use Cloudinary because Render's local filesystem is ephemeral.
# TODO(Render): group materials still use local static storage and have the same persistence risk.
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

# ═══════════════════════════════════════════════════════════
# PAYMENT JOURNAL — ORG EDITS, TEACHER READS
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# LESSON ENDPOINTS (org & teacher)
# ═══════════════════════════════════════════════════════════

def _can_manage_lessons(user: User, group: Group, db: Session) -> bool:
    """Check if user can manage lessons in this group."""
    return _can_manage_group_content(user, group, db)







# ═══════════════════════════════════════════════════════════
# GROUP HOMEWORK — ORG / TEACHER / STUDENT
# ═══════════════════════════════════════════════════════════


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





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

from app.routers import group_analytics
router.include_router(group_analytics.router)

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

from app.routers import group_views
router.include_router(group_views.router)

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

# ═══════════════════════════════════════════════════════════
# VOCABULARY — СОЗДАНИЕ / РЕДАКТИРОВАНИЕ (teacher / org)
# ═══════════════════════════════════════════════════════════

import json as _json
import re as _re
from app.models.vocabulary import VocabularySet, VocabularyItem, VocabularyAttempt, VocabularyAttemptAnswer




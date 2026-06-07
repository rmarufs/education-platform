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

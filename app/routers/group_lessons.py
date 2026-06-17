import os
import shutil
import uuid
import mimetypes
from typing import Optional
from urllib.parse import urlparse, quote
from urllib.request import urlopen

from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import DatabaseError, IntegrityError
from datetime import datetime

from app.database import get_db
from app.ui import templates
from app.models.group import (
    Group, GroupModule, GroupLesson, GroupMaterial, GroupMember,
    GroupLessonProgress, GroupJournalEntry, GroupHomeworkNotification
)
from app.models.vocabulary import VocabularyAttempt, VocabularySet
from app.models.user import User
from app.models.organization import Organization
from app.utils.image import upload_lesson_image
from app.utils.upload_constants import (
    IMAGE_EXTENSIONS as GROUP_LESSON_COVER_EXTENSIONS,
    COVER_IMAGE_MAX_BYTES as GROUP_LESSON_COVER_MAX_BYTES,
    BASIC_DOCUMENT_EXTENSIONS as GROUP_MATERIAL_EXTENSIONS,
    MATERIAL_MAX_BYTES as GROUP_MATERIAL_MAX_BYTES
)
from app.utils.uploads import validate_upload_file
from app.deps.auth import get_user as _get_user
from app.utils.group_membership import ACTIVE_GROUP_MEMBER_STATUS

from app.services.group_lesson_service import (
    ordered_group_lessons,
    get_next_group_lesson_for_student,
    validate_quiz_url,
)

router = APIRouter()
GROUP_MATERIAL_DIR = os.path.join("static", "uploads", "group_materials")

def _require_login(request: Request, db: Session):
    user = _get_user(request, db)
    if not user:
        return None, RedirectResponse("/login", status_code=302)
    return user, None

def _can_manage_group_content(user: User, group: Group, db: Session) -> bool:
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        return bool(org and group.organization_id == org.id)
    if user.is_teacher:
        return group.teacher_id == user.id
    return False

def _can_manage_lessons(user: User, group: Group, db: Session) -> bool:
    return _can_manage_group_content(user, group, db)

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

def _is_uploaded_file(value) -> bool:
    return isinstance(value, UploadFile) and bool(value.filename)

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


def _is_vocabulary_anticheat_schema_mismatch(exc: DatabaseError) -> bool:
    # A dummy or exact copy from groups.py to satisfy imports
    err_str = str(exc).lower()
    return "no such column: vocabularyattempt.anti_cheat" in err_str or "unknown column" in err_str
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

    try:
        quiz_url = validate_quiz_url(form_data.get("quiz_url", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
        GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
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
        GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
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

    ordered_lessons = ordered_group_lessons(group)
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

    group = db.query(Group).options(
        joinedload(Group.modules).joinedload(GroupModule.lessons),
        joinedload(Group.lessons),
    ).filter(
        Group.id == group_id,
        Group.is_active == True,  # noqa: E712
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = db.query(GroupMember.id).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == user.id,
        GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
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

    ordered_lessons = ordered_group_lessons(group)
    current_index = next(
        (index for index, item in enumerate(ordered_lessons) if item.id == lesson_id),
        None,
    )
    if current_index is not None:
        if current_index + 1 < len(ordered_lessons):
            next_lesson = ordered_lessons[current_index + 1]
            return RedirectResponse(f"/groups/{group_id}/lessons/{next_lesson.id}", status_code=302)
        return RedirectResponse("/dashboard/student", status_code=302)

    next_url = request.query_params.get("next")
    allowed_prefixes = (
        f"/groups/{group_id}/lessons/",
    )
    if next_url and next_url.startswith(allowed_prefixes):
        return RedirectResponse(next_url, status_code=302)

    return RedirectResponse("/dashboard/student", status_code=302)

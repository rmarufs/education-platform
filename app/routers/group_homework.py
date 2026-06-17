import os
import uuid
import mimetypes
from urllib.parse import urlparse, quote
from urllib.request import urlopen
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.ui import templates
from app.models.group import (
    Group, GroupMember, GroupModule, GroupLesson, GroupHomework, 
    GroupHomeworkSubmission, GroupHomeworkNotification, GroupJournalEntry
)
from app.models.user import User
from app.deps.auth import get_user as _get_user
from app.services.group_permissions import can_manage_group_content, is_active_group_member
from app.services.group_lesson_service import ordered_group_lessons as _ordered_group_lessons
from app.deps.cloudinary import cloudinary

from app.utils.datetime_helpers import parse_homework_deadline as _parse_homework_deadline

from app.utils.uploads import validate_upload_file
from app.utils.group_membership import ACTIVE_GROUP_MEMBER_STATUS, active_members
from app.services.group_homework_service import (
    save_homework_record, delete_homework_record, submit_homework_record, save_review_record
)

router = APIRouter()
GROUP_HOMEWORK_CLOUDINARY_FOLDER = "group_homework"

GROUP_HOMEWORK_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".jpg", ".jpeg", ".png", ".webp",
}
GROUP_HOMEWORK_VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
}
GROUP_HOMEWORK_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
}
GROUP_HOMEWORK_MAX_BYTES = 50 * 1024 * 1024  # 50 MB



def _require_login(request: Request, db: Session):
    user = _get_user(request, db)
    if not user:
        return None, RedirectResponse("/login?next=" + request.url.path, status_code=302)
    return user, None


def _get_manageable_group(group_id: int, request: Request, db: Session) -> tuple[User, Group]:
    user = _get_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Необходима авторизация")

    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if not can_manage_group_content(db, user, group):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user, group


def _get_group_lesson(group_id: int, lesson_id: int, db: Session) -> GroupLesson:
    lesson = db.query(GroupLesson).filter(
        GroupLesson.group_id == group_id,
        GroupLesson.id == lesson_id,
    ).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    return lesson

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
    can_manage = can_manage_group_content(db, user, group)
    if not group.is_active and not can_manage:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    membership = None
    if user.is_student:
        if not is_active_group_member(db, group_id, user.id):
            raise HTTPException(status_code=403, detail="Вы не являетесь членом этой группы")
        membership = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.student_id == user.id,
            GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
        ).first()
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

    deadline_is_enabled = deadline_enabled == "1"
    if deadline_is_enabled and not (deadline or "").strip():
        raise HTTPException(status_code=400, detail="homework.deadline_required")

    file_url, file_type, filename = None, None, None
    url_to_save, url_type, url_filename = None, None, None
    if material_file and material_file.filename:
        try:
            file_url, file_type, filename = _save_group_homework_upload(material_file, "materials")
        except HTTPException as exc:
            if exc.detail == "homework.video_upload_not_allowed":
                db.rollback()
                return RedirectResponse(f"/groups/{group_id}/manage?error=homework_video_upload", status_code=302)
            raise
    elif material_url and material_url.strip():
        clean_url = material_url.strip()
        parsed = urlparse(clean_url)
        if not all([parsed.scheme, parsed.netloc]):
            raise HTTPException(status_code=400, detail="Некорректная ссылка на материал")
        url_to_save = clean_url
        url_type = _homework_url_type(clean_url)
        url_filename = clean_url.split("/")[-1] or clean_url

    save_homework_record(
        db, group, lesson, user.id,
        clean_title, clean_description, deadline_is_enabled, deadline,
        file_url, file_type, filename,
        url_to_save, url_type, url_filename
    )
    return RedirectResponse(f"/groups/{group_id}/manage?success=homework_saved", status_code=302)


@router.post("/{group_id:int}/lessons/{lesson_id:int}/homework/delete")
def group_homework_delete(group_id: int, lesson_id: int, request: Request, db: Session = Depends(get_db)):
    _, group = _get_manageable_group(group_id, request, db)
    lesson = _get_group_lesson(group.id, lesson_id, db)
    if lesson.homework:
        delete_homework_record(db, group.id, lesson.id)
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

    if not is_active_group_member(db, group_id, user.id):
        raise HTTPException(status_code=403, detail="Вы не являетесь членом этой группы")

    if homework.deadline and homework.deadline < datetime.utcnow():
        return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}/homework?error=deadline_passed", status_code=302)

    clean_comment = comment.strip() if comment and comment.strip() else None
    has_file = bool(answer_file and answer_file.filename)
    if not has_file and not clean_comment:
        return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}/homework?error=answer_required", status_code=302)

    file_url, file_type, filename = None, None, None
    url_to_save, url_type, url_filename = None, None, None
    if has_file:
        try:
            file_url, file_type, filename = _save_group_homework_upload(answer_file, "submissions")
        except HTTPException as exc:
            if exc.detail == "homework.video_upload_not_allowed":
                db.rollback()
                return RedirectResponse(f"/groups/{group_id}/lessons/{lesson_id}/homework?error=video_upload_not_allowed", status_code=302)
            raise

    try:
        submit_homework_record(
            db, group_id, lesson_id, user.id, clean_comment,
            file_url, file_type, filename, None, None, None
        )
    except Exception:
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

    is_member = is_active_group_member(db, group_id, user.id)
    if not (can_manage_group_content(db, user, lesson.group) or is_member):
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

    is_submission_owner_with_access = (
        submission.student_id == user.id
        and is_active_group_member(db, group_id, user.id)
    )
    if not (can_manage_group_content(db, user, lesson.group) or is_submission_owner_with_access):
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
    if not can_manage_group_content(db, user, group):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    members = sorted(
        [member for member in active_members(group.members) if member.student],
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
    success, lesson_id = save_review_record(db, group.id, submission_id, user.id, teacher_comment)
    if not success:
        raise HTTPException(status_code=404, detail="Ответ не найден")
    return RedirectResponse(f"/groups/{group_id}/homework/review?lesson_id={lesson_id}&success=review_saved", status_code=302)

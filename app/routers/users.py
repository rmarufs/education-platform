from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import logging
import re
from datetime import datetime
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session, joinedload, selectinload
from collections import defaultdict

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.module import Module
from app.models.group import Group, GroupMember, GroupHomework, GroupHomeworkNotification, GroupHomeworkSubmission, GroupJournalEntry, GroupLesson, GroupLessonProgress
from app.models.vocabulary import VocabularyAttempt, VocabularySet
from app.course_flow import first_course_lesson_url
from app.utils.announcements import get_visible_announcements
from app.utils.group_analytics import build_student_analytics

router = APIRouter()
from app.ui import templates

logger = logging.getLogger(__name__)


def require_login(request: Request, db: Session):
    """Возвращает пользователя или редирект на логин."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None, RedirectResponse("/login", status_code=302)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        request.session.clear()
        return None, RedirectResponse("/login", status_code=302)
    return user, None


def _course_continue_url(course: Course, lesson_id: int | None) -> str | None:
    if not lesson_id:
        return first_course_lesson_url(course)

    modules = list(course.modules)
    for module_index, module in enumerate(modules):
        lessons = list(module.lessons)
        for lesson_index, lesson in enumerate(lessons):
            if lesson.id != lesson_id:
                continue
            if lesson_index < len(lessons) - 1:
                return f"/lessons/{lessons[lesson_index + 1].id}"
            for next_module in modules[module_index + 1:]:
                next_lessons = list(next_module.lessons)
                if next_lessons:
                    return f"/lessons/{next_lessons[0].id}"
            return f"/courses/{course.id}/completed"

    return f"/courses/{course.id}"


def _homework_comment_preview(comment: str | None, max_chars: int = 220, max_sentences: int = 4) -> str:
    text = " ".join((comment or "").split())
    if not text:
        return ""

    sentences = [part.strip() for part in re.findall(r"[^.!?…]+[.!?…]?", text) if part.strip()]
    preview = " ".join(sentences[:max_sentences]) if sentences else text
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip()

    if len(preview) < len(text):
        preview = preview.rstrip(" .,!?:;…") + "…"

    return preview


def _homework_target_url(group_id: int, lesson_id: int, anchor: str | None = None) -> str:
    url = f"/groups/{group_id}/lessons/{lesson_id}/homework"
    return f"{url}#{anchor}" if anchor else url


def _load_student_notifications(db: Session, student_id: int) -> list[dict]:
    try:
        homework_reply_submissions = (
            db.query(GroupHomeworkSubmission)
            .options(
                joinedload(GroupHomeworkSubmission.reviewed_by),
                joinedload(GroupHomeworkSubmission.homework)
                .joinedload(GroupHomework.lesson)
                .joinedload(GroupLesson.group)
                .joinedload(Group.teacher),
            )
            .filter(
                GroupHomeworkSubmission.student_id == student_id,
                GroupHomeworkSubmission.teacher_comment.isnot(None),
                GroupHomeworkSubmission.teacher_comment != "",
                GroupHomeworkSubmission.reviewed_at.isnot(None),
                GroupHomeworkSubmission.homework_reply_read_at.is_(None),
            )
            .order_by(GroupHomeworkSubmission.reviewed_at.desc(), GroupHomeworkSubmission.id.desc())
            .limit(5)
            .all()
        )
        new_homework_notifications = (
            db.query(GroupHomeworkNotification)
            .options(
                joinedload(GroupHomeworkNotification.homework)
                .joinedload(GroupHomework.created_by),
                joinedload(GroupHomeworkNotification.homework)
                .joinedload(GroupHomework.lesson)
                .joinedload(GroupLesson.group)
                .joinedload(Group.teacher),
            )
            .filter(
                GroupHomeworkNotification.student_id == student_id,
                GroupHomeworkNotification.notification_type == "new_homework",
                GroupHomeworkNotification.read_at.is_(None),
            )
            .order_by(GroupHomeworkNotification.created_at.desc(), GroupHomeworkNotification.id.desc())
            .limit(5)
            .all()
        )
    except DatabaseError as exc:
        db.rollback()
        logger.warning(
            "Student homework notifications were skipped. "
            "If this happens after deploy, run alembic upgrade head. Error: %s",
            exc,
        )
        return []

    student_notifications = []
    for submission in homework_reply_submissions:
        homework = submission.homework
        lesson = homework.lesson if homework else None
        group = lesson.group if lesson else None
        if not homework or not lesson or not group:
            continue
        teacher = submission.reviewed_by or group.teacher
        student_notifications.append({
            "id": f"homework-reply-{submission.id}",
            "kind": "homework_reply",
            "icon": "↩",
            "badge_key": "notification.type_teacher_reply",
            "badge": "Ответ преподавателя",
            "title_key": "notification.teacher_homework_reply_title",
            "title": "Преподаватель ответил на домашку",
            "preview": _homework_comment_preview(submission.teacher_comment),
            "teacher_name": teacher.name if teacher else "",
            "group": group,
            "lesson": lesson,
            "time_key": "notification.reply_time",
            "time_at": submission.reviewed_at,
            "deadline_at": homework.deadline,
            "open_url": f"/dashboard/student/homework-replies/{submission.id}/open",
            "dismiss_url": f"/dashboard/student/homework-replies/{submission.id}/dismiss",
            "action_key": "notification.open_homework",
            "action": "Открыть домашку",
        })
    for notification in new_homework_notifications:
        homework = notification.homework
        lesson = homework.lesson if homework else None
        group = lesson.group if lesson else None
        if not homework or not lesson or not group:
            continue
        teacher = homework.created_by or group.teacher
        student_notifications.append({
            "id": f"new-homework-{notification.id}",
            "kind": "new_homework",
            "icon": "✦",
            "badge_key": "notification.type_homework",
            "badge": "Домашка",
            "title_key": "notification.new_homework_title",
            "title": "Добавлена новая домашка",
            "preview": _homework_comment_preview(homework.description),
            "teacher_name": teacher.name if teacher else "",
            "group": group,
            "lesson": lesson,
            "time_key": "notification.created_time",
            "time_at": notification.created_at or homework.created_at,
            "deadline_at": homework.deadline,
            "open_url": f"/dashboard/student/homework-notifications/{notification.id}/open",
            "dismiss_url": f"/dashboard/student/homework-notifications/{notification.id}/dismiss",
            "action_key": "notification.open_homework",
            "action": "Открыть домашку",
        })
    student_notifications.sort(key=lambda item: item["time_at"] or datetime.min, reverse=True)
    return student_notifications[:8]


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """Перенаправляет на нужный дашборд в зависимости от роли."""
    user, redirect = require_login(request, db)
    if redirect:
        return redirect

    if user.is_teacher:
        return RedirectResponse("/dashboard/teacher", status_code=302)
    if user.role.value == "teacher_pending":
        return RedirectResponse("/register/pending", status_code=302)
    if user.is_admin:
        return RedirectResponse("/admin", status_code=302)
    if user.is_org:
        return RedirectResponse("/dashboard/organization", status_code=302)
    return RedirectResponse("/dashboard/student", status_code=302)


@router.get("/dashboard/student", response_class=HTMLResponse)
def student_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value != "student":
        return RedirectResponse("/dashboard/teacher", status_code=302)

    from app.models.progress import Progress
    from app.models.lesson import Lesson
    from app.models.organization import OrganizationStudent
    from datetime import datetime

    # Получаем активную организацию студента (если есть)
    student_org_link = db.query(OrganizationStudent).options(
        joinedload(OrganizationStudent.organization)
    ).filter(
        OrganizationStudent.student_id == user.id,
        OrganizationStudent.status.in_(["accepted", "pending"])
    ).first()

    # Проверяем, есть ли уведомления об удалении
    removed_links = db.query(OrganizationStudent).filter(
        OrganizationStudent.student_id == user.id,
        OrganizationStudent.status == "removed",
        OrganizationStudent.was_removed_notification == True
    ).all()

    show_removed_notification = False
    if removed_links:
        show_removed_notification = True
        for r_link in removed_links:
            r_link.was_removed_notification = False
        db.commit()

    user_progress = (
        db.query(Progress)
        .options(joinedload(Progress.lesson).joinedload(Lesson.module))
        .filter(Progress.student_id == user.id)
        .all()
    )

    course_progress_data = defaultdict(lambda: {
        "completed_lessons": set(),
        "last_accessed_lesson_id": None,
        "last_accessed_time": datetime.min,
        "last_completed_lesson_id": None,
        "last_completed_time": datetime.min,
        "last_completed_progress_id": 0,
    })
    course_ids = set()
    last_lesson_ids = set()

    for progress in user_progress:
        if not progress.lesson or not progress.lesson.module:
            continue
        course_id = progress.lesson.module.course_id
        course_ids.add(course_id)
        pt_time = progress.completed_at or datetime.min
        data = course_progress_data[course_id]
        if progress.completed:
            data["completed_lessons"].add(progress.lesson_id)
            completed_at = progress.completed_at or datetime.min
            if (completed_at, progress.id) >= (data["last_completed_time"], data["last_completed_progress_id"]):
                data["last_completed_time"] = completed_at
                data["last_completed_progress_id"] = progress.id
                data["last_completed_lesson_id"] = progress.lesson_id

        if pt_time >= data["last_accessed_time"]:
            data["last_accessed_time"] = pt_time
            data["last_accessed_lesson_id"] = progress.lesson_id
            last_lesson_ids.add(progress.lesson_id)

    all_courses = (
        db.query(Course)
        .options(joinedload(Course.teacher), selectinload(Course.modules).selectinload(Module.lessons))
        .filter(Course.id.in_(course_ids))
        .all()
    ) if course_ids else []

    last_lessons = {
        lesson.id: lesson
        for lesson in db.query(Lesson).filter(Lesson.id.in_(last_lesson_ids)).all()
    } if last_lesson_ids else {}

    my_courses = []
    for c in all_courses:
        if c.id in course_progress_data:
            data = course_progress_data[c.id]
            total_lessons = sum(len(m.lessons) for m in c.modules)
            pct = int((len(data["completed_lessons"]) / total_lessons) * 100) if total_lessons > 0 else 0

            my_courses.append({
                "course": c,
                "progress_pct": pct,
                "last_lesson": last_lessons.get(data["last_accessed_lesson_id"]),
                "continue_url": _course_continue_url(c, data["last_completed_lesson_id"]),
            })

    # Группы студента
    student_groups = (
        db.query(Group)
        .options(
            joinedload(Group.organization),
            joinedload(Group.teacher),
            selectinload(Group.lessons),
        )
        .join(GroupMember, GroupMember.group_id == Group.id)
        .filter(GroupMember.student_id == user.id)
        .all()
    )
    group_ids = [group.id for group in student_groups]
    group_progress_map = {group_id: False for group_id in group_ids}
    if group_ids:
        progress_group_ids = {
            group_id
            for (group_id,) in db.query(GroupLessonProgress.group_id)
            .filter(
                GroupLessonProgress.student_id == user.id,
                GroupLessonProgress.group_id.in_(group_ids),
            )
            .distinct()
            .all()
        }
        journal_group_ids = {
            group_id
            for (group_id,) in db.query(GroupJournalEntry.group_id)
            .filter(
                GroupJournalEntry.student_id == user.id,
                GroupJournalEntry.group_id.in_(group_ids),
                (GroupJournalEntry.present == True) | (GroupJournalEntry.grade.isnot(None)),  # noqa: E712
            )
            .distinct()
            .all()
        }
        vocabulary_group_ids = {
            group_id
            for (group_id,) in db.query(GroupLesson.group_id)
            .join(VocabularySet, VocabularySet.lesson_id == GroupLesson.id)
            .join(VocabularyAttempt, VocabularyAttempt.vocab_set_id == VocabularySet.id)
            .filter(
                VocabularyAttempt.student_id == user.id,
                GroupLesson.group_id.in_(group_ids),
            )
            .distinct()
            .all()
        }
        for group_id in progress_group_ids | journal_group_ids | vocabulary_group_ids:
            group_progress_map[group_id] = True
    student_analytics = build_student_analytics(db, user.id)
    visible_announcements = get_visible_announcements(db, user, limit=3)
    student_notifications = _load_student_notifications(db, user.id)

    return templates.TemplateResponse(
        "dashboard/student.html",
        {
            "request": request, 
            "user": user, 
            "my_courses": my_courses,
            "student_org_link": student_org_link,
            "show_removed_notification": show_removed_notification,
            "student_groups": student_groups,
            "group_progress_map": group_progress_map,
            "student_analytics": student_analytics,
            "visible_announcements": visible_announcements,
            "student_notifications": student_notifications,
        },
    )


@router.get("/dashboard/student/homework-replies/{submission_id:int}/open")
def open_homework_reply_notification(submission_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value != "student":
        return RedirectResponse("/dashboard", status_code=302)

    submission = (
        db.query(GroupHomeworkSubmission)
        .options(
            joinedload(GroupHomeworkSubmission.homework)
            .joinedload(GroupHomework.lesson)
            .joinedload(GroupLesson.group)
        )
        .filter(
            GroupHomeworkSubmission.id == submission_id,
            GroupHomeworkSubmission.student_id == user.id,
        )
        .first()
    )
    if not submission:
        return RedirectResponse("/dashboard/student", status_code=302)

    homework = submission.homework
    lesson = homework.lesson if homework else None
    group = lesson.group if lesson else None
    if not homework or not lesson or not group:
        return RedirectResponse("/dashboard/student", status_code=302)

    if submission.homework_reply_read_at is None:
        submission.homework_reply_read_at = datetime.utcnow()
        db.commit()

    return RedirectResponse(_homework_target_url(group.id, lesson.id, "homework-review"), status_code=302)


@router.post("/dashboard/student/homework-replies/{submission_id:int}/dismiss")
def dismiss_homework_reply_notification(submission_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value != "student":
        return RedirectResponse("/dashboard", status_code=302)

    submission = db.query(GroupHomeworkSubmission).filter(
        GroupHomeworkSubmission.id == submission_id,
        GroupHomeworkSubmission.student_id == user.id,
    ).first()
    if submission and submission.homework_reply_read_at is None:
        submission.homework_reply_read_at = datetime.utcnow()
        db.commit()

    return RedirectResponse("/dashboard/student", status_code=302)


@router.get("/dashboard/student/homework-notifications/{notification_id:int}/open")
def open_new_homework_notification(notification_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value != "student":
        return RedirectResponse("/dashboard", status_code=302)

    notification = (
        db.query(GroupHomeworkNotification)
        .options(
            joinedload(GroupHomeworkNotification.homework)
            .joinedload(GroupHomework.lesson)
            .joinedload(GroupLesson.group)
        )
        .filter(
            GroupHomeworkNotification.id == notification_id,
            GroupHomeworkNotification.student_id == user.id,
        )
        .first()
    )
    if not notification:
        return RedirectResponse("/dashboard/student", status_code=302)

    homework = notification.homework
    lesson = homework.lesson if homework else None
    group = lesson.group if lesson else None
    if not homework or not lesson or not group:
        return RedirectResponse("/dashboard/student", status_code=302)

    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()

    return RedirectResponse(_homework_target_url(group.id, lesson.id, "homework-task"), status_code=302)


@router.post("/dashboard/student/homework-notifications/{notification_id:int}/dismiss")
def dismiss_new_homework_notification(notification_id: int, request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value != "student":
        return RedirectResponse("/dashboard", status_code=302)

    notification = db.query(GroupHomeworkNotification).filter(
        GroupHomeworkNotification.id == notification_id,
        GroupHomeworkNotification.student_id == user.id,
    ).first()
    if notification and notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()

    return RedirectResponse("/dashboard/student", status_code=302)


@router.get("/dashboard/teacher", response_class=HTMLResponse)
def teacher_dashboard(request: Request, db: Session = Depends(get_db)):
    user, redirect = require_login(request, db)
    if redirect:
        return redirect
    if user.role.value not in ("teacher", "admin"):
        if user.role.value == "teacher_pending":
            return RedirectResponse("/register/pending", status_code=302)
        return RedirectResponse("/dashboard/student", status_code=302)

    from app.models.group import Group

    my_groups = []
    has_active_groups = db.query(Group.id).filter(
        Group.teacher_id == user.id,
        Group.is_active == True,  # noqa: E712
    ).first()

    if user.is_teacher and request.query_params.get("section") != "courses" and has_active_groups:
        return RedirectResponse("/groups/my", status_code=302)

    # Только курсы этого преподавателя (teacher уже загружен, eager load не нужен)
    courses = db.query(Course).filter(Course.teacher_id == user.id).all()
    
    # Загружаем категории для списка выбора
    from app.models.category import Category
    categories = db.query(Category).order_by(Category.name).all()
    
    # Заявки и приглашения от организаций
    from app.models.organization import OrganizationTeacher
    pending_invites = db.query(OrganizationTeacher).options(joinedload(OrganizationTeacher.organization)).filter(
        OrganizationTeacher.teacher_id == user.id,
        OrganizationTeacher.status == "pending"
    ).all()

    accepted_notice_links = db.query(OrganizationTeacher).options(
        joinedload(OrganizationTeacher.organization)
    ).filter(
        OrganizationTeacher.teacher_id == user.id,
        OrganizationTeacher.status == "accepted",
        OrganizationTeacher.was_accepted_notification == True,  # noqa: E712
    ).order_by(OrganizationTeacher.created_at.desc()).all()
    accepted_application_notice = accepted_notice_links[0] if accepted_notice_links else None
    if accepted_notice_links:
        for link in accepted_notice_links:
            link.was_accepted_notification = False
        db.commit()

    # Для секции оставляем только реально актуальные ожидающие заявки.
    teacher_applications = db.query(OrganizationTeacher).options(
        joinedload(OrganizationTeacher.organization)
    ).filter(
        OrganizationTeacher.teacher_id == user.id,
        OrganizationTeacher.status == "pending",
    ).order_by(OrganizationTeacher.created_at.desc()).all()
    visible_announcements = get_visible_announcements(db, user, limit=3)

    return templates.TemplateResponse(
        "dashboard/teacher.html",
        {
            "request": request,
            "user": user,
            "courses": courses,
            "categories": categories,
            "pending_invites": pending_invites,
            "accepted_application_notice": accepted_application_notice,
            "my_org_applications": teacher_applications,  # backward compat
            "teacher_applications": teacher_applications,
            "my_groups": my_groups,
            "visible_announcements": visible_announcements,
        },
    )

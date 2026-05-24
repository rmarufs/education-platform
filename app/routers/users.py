from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from collections import defaultdict

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.module import Module
from app.models.group import Group, GroupMember
from app.course_flow import course_learning_url
from app.utils.announcements import get_visible_announcements
from app.utils.group_analytics import build_student_analytics

router = APIRouter()
from app.ui import templates


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

        if pt_time >= data["last_accessed_time"]:
            data["last_accessed_time"] = pt_time
            data["last_accessed_lesson_id"] = progress.lesson_id
            last_lesson_ids.add(progress.lesson_id)

    all_courses = (
        db.query(Course)
        .options(joinedload(Course.teacher), joinedload(Course.modules).joinedload(Module.lessons))
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
                "continue_url": course_learning_url(db, user.id, c),
            })

    # Группы студента
    student_groups = (
        db.query(Group)
        .options(
            joinedload(Group.organization),
            joinedload(Group.teacher),
            joinedload(Group.lessons),
        )
        .join(GroupMember, GroupMember.group_id == Group.id)
        .filter(GroupMember.student_id == user.id)
        .all()
    )
    student_analytics = build_student_analytics(db, user.id)
    visible_announcements = get_visible_announcements(db, user, limit=3)

    return templates.TemplateResponse(
        "dashboard/student.html",
        {
            "request": request, 
            "user": user, 
            "my_courses": my_courses,
            "student_org_link": student_org_link,
            "show_removed_notification": show_removed_notification,
            "student_groups": student_groups,
            "student_analytics": student_analytics,
            "visible_announcements": visible_announcements,
        },
    )


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
    from sqlalchemy.orm import joinedload as jl

    # Группы, в которых преподаватель назначен
    my_groups = db.query(Group).options(
        jl(Group.members),
        jl(Group.lessons),
    ).filter(
        Group.teacher_id == user.id,
        Group.is_active == True,  # noqa: E712
    ).order_by(Group.created_at.desc()).all()

    if user.is_teacher and request.query_params.get("section") != "courses" and my_groups:
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

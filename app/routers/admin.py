# Роутер админ-панели
import os
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
import csv
import io
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app.database import get_db
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.progress import Progress
from app.models.module import Module
from app.models.lesson import Lesson
from app.models.assessment import AssessmentResponse
from app.models.comment import Comment
from app.models.group import (
    Group,
    GroupHomework,
    GroupHomeworkSubmission,
    GroupJournalEntry,
    GroupLesson,
    GroupMaterial,
    GroupMember,
    GroupModule,
    GroupPaymentEntry,
)
from app.models.organization import Organization, OrganizationStudent, OrganizationTeacher
from app.models.quiz import QuizAttempt, QuizResult
from app.models.review import Review

router = APIRouter(prefix="/admin")
from app.ui import templates


def get_admin(request: Request, db: Session) -> User:
    """Проверяет, что текущий пользователь — админ."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return user


def _admin_users_redirect(**params) -> RedirectResponse:
    query = urlencode({key: value for key, value in params.items() if value})
    location = f"/admin/users?{query}" if query else "/admin/users"
    return RedirectResponse(location, status_code=302)


def _admin_organizations_redirect(**params) -> RedirectResponse:
    query = urlencode({key: value for key, value in params.items() if value})
    location = f"/admin/organizations?{query}" if query else "/admin/organizations"
    return RedirectResponse(location, status_code=302)


def _is_last_admin(db: Session, user: User) -> bool:
    if user.role != UserRole.admin:
        return False
    return db.query(func.count(User.id)).filter(User.role == UserRole.admin).scalar() <= 1


def _delete_user_document(user: User) -> None:
    if not user.documents:
        return
    file_path = user.documents.lstrip("/")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass


def _delete_user_courses(db: Session, user: User) -> None:
    for course in db.query(Course).filter(Course.teacher_id == user.id).all():
        db.delete(course)


def _delete_owned_organization(db: Session, user: User) -> None:
    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        return

    _delete_organization_dependencies(db, org)
    db.delete(org)


def _delete_organization_dependencies(db: Session, org: Organization) -> None:
    """Delete organization-owned data while keeping linked user accounts intact."""
    group_ids = [
        row[0]
        for row in db.query(Group.id)
        .filter(Group.organization_id == org.id)
        .all()
    ]

    if group_ids:
        lesson_ids = [
            row[0]
            for row in db.query(GroupLesson.id)
            .filter(GroupLesson.group_id.in_(group_ids))
            .all()
        ]

        db.query(GroupJournalEntry).filter(GroupJournalEntry.group_id.in_(group_ids)).delete(synchronize_session=False)
        db.query(GroupPaymentEntry).filter(GroupPaymentEntry.group_id.in_(group_ids)).delete(synchronize_session=False)
        db.query(GroupMember).filter(GroupMember.group_id.in_(group_ids)).delete(synchronize_session=False)

        if lesson_ids:
            homework_ids = [
                row[0]
                for row in db.query(GroupHomework.id)
                .filter(GroupHomework.lesson_id.in_(lesson_ids))
                .all()
            ]
            if homework_ids:
                db.query(GroupHomeworkSubmission).filter(GroupHomeworkSubmission.homework_id.in_(homework_ids)).delete(synchronize_session=False)
                db.query(GroupHomework).filter(GroupHomework.id.in_(homework_ids)).delete(synchronize_session=False)
            db.query(GroupMaterial).filter(GroupMaterial.lesson_id.in_(lesson_ids)).delete(synchronize_session=False)

        db.query(GroupLesson).filter(GroupLesson.group_id.in_(group_ids)).delete(synchronize_session=False)
        db.query(GroupModule).filter(GroupModule.group_id.in_(group_ids)).delete(synchronize_session=False)
        db.query(Group).filter(Group.id.in_(group_ids)).delete(synchronize_session=False)

    db.query(OrganizationTeacher).filter(OrganizationTeacher.organization_id == org.id).delete(synchronize_session=False)
    db.query(OrganizationStudent).filter(OrganizationStudent.organization_id == org.id).delete(synchronize_session=False)


def _delete_user_dependencies(db: Session, user: User, delete_owned_organization: bool = True) -> None:
    """Remove or detach records that can block deleting older test users."""
    db.query(QuizAttempt).filter(QuizAttempt.student_id == user.id).delete(synchronize_session=False)
    db.query(QuizResult).filter(QuizResult.student_id == user.id).delete(synchronize_session=False)
    db.query(Progress).filter(Progress.student_id == user.id).delete(synchronize_session=False)
    db.query(Comment).filter(Comment.user_id == user.id).delete(synchronize_session=False)
    db.query(AssessmentResponse).filter(AssessmentResponse.user_id == user.id).delete(synchronize_session=False)
    db.query(Review).filter(
        (Review.student_id == user.id) | (Review.teacher_id == user.id)
    ).delete(synchronize_session=False)
    db.query(GroupJournalEntry).filter(GroupJournalEntry.student_id == user.id).delete(synchronize_session=False)
    db.query(GroupHomeworkSubmission).filter(GroupHomeworkSubmission.student_id == user.id).delete(synchronize_session=False)
    db.query(GroupHomework).filter(GroupHomework.created_by_id == user.id).update(
        {GroupHomework.created_by_id: None},
        synchronize_session=False,
    )
    db.query(GroupPaymentEntry).filter(GroupPaymentEntry.student_id == user.id).delete(synchronize_session=False)
    db.query(GroupPaymentEntry).filter(GroupPaymentEntry.marked_by_id == user.id).update(
        {GroupPaymentEntry.marked_by_id: None},
        synchronize_session=False,
    )
    db.query(GroupMember).filter(GroupMember.student_id == user.id).delete(synchronize_session=False)
    db.query(OrganizationTeacher).filter(OrganizationTeacher.teacher_id == user.id).delete(synchronize_session=False)
    db.query(OrganizationStudent).filter(OrganizationStudent.student_id == user.id).delete(synchronize_session=False)
    db.query(Group).filter(Group.teacher_id == user.id).update(
        {Group.teacher_id: None},
        synchronize_session=False,
    )

    _delete_user_courses(db, user)
    if delete_owned_organization:
        _delete_owned_organization(db, user)


def _delete_organization_owner_user(db: Session, owner: User, admin: User) -> bool:
    """Delete the technical organization owner account to release its unique email."""
    if owner.id == admin.id or _is_last_admin(db, owner):
        return False
    if owner.role != UserRole.organization:
        return False

    _delete_user_document(owner)
    _delete_user_dependencies(db, owner, delete_owned_organization=False)
    db.delete(owner)
    return True


# ── Главная админ-панели ─────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def admin_index(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    # 1 запрос вместо 4: получаем счётчики по ролям через GROUP BY
    role_counts: dict[str, int] = {
        row.role.value: row.cnt
        for row in db.query(User.role, func.count(User.id).label("cnt")).group_by(User.role).all()
    }

    stats = {
        "total_users": sum(role_counts.values()),
        "students":    role_counts.get("student", 0),
        "teachers":    role_counts.get("teacher", 0),
        "pending":     role_counts.get("teacher_pending", 0),
        "courses":     db.query(func.count(Course.id)).scalar(),
    }

    return templates.TemplateResponse("admin/index.html", {
        "request": request,
        "user": admin,
        "stats": stats,
    })


# ── Заявки преподавателей ────────────────────────────────────────────────────

@router.get("/teachers", response_class=HTMLResponse)
def admin_teachers(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    from app.models.organization import Organization, OrganizationTeacher

    # Все заявки (teacher_pending)
    pending_teachers = (
        db.query(User)
        .filter(User.role == UserRole.teacher_pending)
        .order_by(User.created_at.desc())
        .all()
    )

    # Все активные преподаватели
    active_teachers = (
        db.query(User)
        .filter(User.role == UserRole.teacher)
        .order_by(User.created_at.desc())
        .all()
    )

    # Маппинг teacher_id → организация
    all_teacher_ids = [t.id for t in pending_teachers + active_teachers]
    org_map = {}
    if all_teacher_ids:
        links = (
            db.query(OrganizationTeacher)
            .options(joinedload(OrganizationTeacher.organization))
            .filter(OrganizationTeacher.teacher_id.in_(all_teacher_ids))
            .all()
        )
        for link in links:
            org_map[link.teacher_id] = link

    return templates.TemplateResponse("admin/teachers.html", {
        "request": request,
        "user": admin,
        "pending_teachers": pending_teachers,
        "active_teachers": active_teachers,
        "org_map": org_map,
    })


@router.post("/teachers/{user_id}/approve")
def approve_teacher(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    teacher = db.query(User).filter(User.id == user_id, User.role == UserRole.teacher_pending).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    teacher.role = UserRole.teacher
    teacher.is_active = True
    db.commit()

    return RedirectResponse("/admin/teachers", status_code=302)


@router.post("/teachers/{user_id}/reject")
def reject_teacher(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    teacher = db.query(User).filter(User.id == user_id, User.role == UserRole.teacher_pending).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    # Удаляем документ, если есть
    if teacher.documents:
        file_path = teacher.documents.lstrip("/")
        if os.path.exists(file_path):
            os.remove(file_path)
        teacher.documents = None

    teacher.role = UserRole.student
    db.commit()

    return RedirectResponse("/admin/teachers", status_code=302)


@router.post("/teachers/{user_id}/remove-from-org")
def admin_remove_from_org(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)
    from app.models.organization import OrganizationTeacher
    links = db.query(OrganizationTeacher).filter(OrganizationTeacher.teacher_id == user_id).all()
    for link in links:
        db.delete(link)
    db.commit()
    return RedirectResponse("/admin/teachers", status_code=302)


# ── Управление организациями ─────────────────────────────────────────────────

@router.get("/organizations", response_class=HTMLResponse)
def admin_organizations(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)
    from app.models.organization import Organization

    all_orgs = (
        db.query(Organization)
        .options(joinedload(Organization.user))
        .order_by(Organization.created_at.desc())
        .all()
    )

    return templates.TemplateResponse("admin/organizations.html", {
        "request": request,
        "user": admin,
        "orgs": all_orgs,
    })


@router.post("/organizations/{org_id}/approve")
def admin_approve_org(org_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)
    from app.models.organization import Organization

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404)

    org.status = "approved"
    # Активируем пользователя организации
    owner = db.query(User).filter(User.id == org.user_id).first()
    if owner:
        owner.is_active = True
        owner.role = UserRole.organization
    db.commit()

    return RedirectResponse("/admin/organizations", status_code=302)


@router.post("/organizations/{org_id}/reject")
def admin_reject_org(org_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)
    from app.models.organization import Organization

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404)

    org.status = "rejected"
    owner = db.query(User).filter(User.id == org.user_id).first()
    if owner:
        owner.is_active = False
    db.commit()

    return RedirectResponse("/admin/organizations", status_code=302)


@router.post("/organizations/{org_id}/delete")
def admin_delete_org(org_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)
    from app.models.organization import Organization

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return _admin_organizations_redirect(error="not_found")

    try:
        owner = db.query(User).filter(User.id == org.user_id).first()

        _delete_organization_dependencies(db, org)
        db.delete(org)
        db.flush()

        owner_deleted = False
        if owner:
            owner_deleted = _delete_organization_owner_user(db, owner, admin)
            if not owner_deleted:
                owner.is_active = False

        db.commit()
    except SQLAlchemyError:
        db.rollback()
        return _admin_organizations_redirect(error="delete_failed")

    return _admin_organizations_redirect(success="deleted_email_released" if owner_deleted else "deleted_owner_kept")




# ── Управление пользователями ────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
def admin_users(request: Request, q: str = "", db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    query = db.query(User).order_by(User.created_at.desc())
    if q:
        query = query.filter(
            (User.name.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )
    users = query.all()

    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "user": admin,
        "users_list": users,
        "q": q,
    })


@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return _admin_users_redirect(error="not_found")

    # Нельзя заблокировать самого себя
    if target.id == admin.id:
        return _admin_users_redirect(error="cannot_block_self")

    if target.is_active and _is_last_admin(db, target):
        return _admin_users_redirect(error="cannot_block_last_admin")

    target.is_active = not target.is_active
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        return _admin_users_redirect(error="action_failed")

    return _admin_users_redirect(success="unblocked" if target.is_active else "blocked")


@router.post("/users/{user_id}/delete")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return _admin_users_redirect(error="not_found")

    if target.id == admin.id:
        return _admin_users_redirect(error="cannot_delete_self")

    if _is_last_admin(db, target):
        return _admin_users_redirect(error="cannot_delete_last_admin")

    try:
        _delete_user_document(target)
        _delete_user_dependencies(db, target)
        db.delete(target)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        return _admin_users_redirect(error="delete_failed")

    return _admin_users_redirect(success="deleted")


# ── Управление курсами ──────────────────────────────────────────────────────

@router.get("/courses", response_class=HTMLResponse)
def admin_courses(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    courses = (
        db.query(Course)
        .options(joinedload(Course.teacher), joinedload(Course.modules).joinedload(Module.lessons))
        .order_by(Course.created_at.desc())
        .all()
    )

    course_ids = [course.id for course in courses]
    student_count_map = {
        course_id: count
        for course_id, count in (
            db.query(
                Module.course_id,
                func.count(func.distinct(Progress.student_id)),
            )
            .join(Lesson, Lesson.module_id == Module.id)
            .outerjoin(Progress, Progress.lesson_id == Lesson.id)
            .filter(Module.course_id.in_(course_ids))
            .group_by(Module.course_id)
            .all()
        )
    } if course_ids else {}

    course_data = [
        {
            "course": course,
            "student_count": student_count_map.get(course.id, 0),
        }
        for course in courses
    ]

    return templates.TemplateResponse("admin/courses.html", {
        "request": request,
        "user": admin,
        "course_data": course_data,
    })


@router.post("/courses/{course_id}/delete")
def admin_delete_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404)

    db.delete(course)
    db.commit()

    from main import invalidate_courses_cache
    invalidate_courses_cache()
    return RedirectResponse("/admin/courses", status_code=302)


# ── Экспорт данных ──────────────────────────────────────────────────────────

@router.get("/export-assessments")
def export_assessments(request: Request, db: Session = Depends(get_db)):
    admin = get_admin(request, db)
    
    from app.models.assessment import AssessmentResponse
    responses = db.query(AssessmentResponse).options(joinedload(AssessmentResponse.user)).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовки CSV
    writer.writerow([
        "ID пользователя", 
        "Имя", 
        "Email", 
        "Q1: Опыт онлайн-курсов (1-Да,много; 2-Да,1-2; 3-Нет)", 
        "Q2: Частота самообучения (1-Часто; 2-Иногда; 3-Редко)", 
        "Q3: Доводит до конца (1-Всегда; 2-Иногда; 3-Редко)", 
        "Q4: Комфорт без наставника (1-Комфортно; 2-Нормально; 3-Сложно)", 
        "Q5: Трудности (1-Мотивация; 2-Сложность; 3-Нет трудностей)",
        "Дата ответа"
    ])
    
    for r in responses:
        writer.writerow([
            r.user.id if r.user else "",
            r.user.name if r.user else "Удален",
            r.user.email if r.user else "",
            r.q1_answer,
            r.q2_answer,
            r.q3_answer,
            r.q4_answer,
            r.q5_answer,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
        ])
    
    # Возвращаем файл
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), 
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=assessments.csv"}
    )

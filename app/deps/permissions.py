"""Preparatory role and permission helpers.

This module mirrors permission behavior from `app/dependencies.py` but is not
wired into existing routers yet.
"""

from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.organization import Organization, OrganizationTeacher
from app.models.user import User


def is_admin(user: User | None) -> bool:
    return bool(user and user.role.value == "admin")


def is_teacher(user: User | None) -> bool:
    return bool(user and user.role.value == "teacher")


def is_student(user: User | None) -> bool:
    return bool(user and user.role.value == "student")


def is_org(user: User | None) -> bool:
    return bool(user and user.role.value == "organization")


def can_access_course_content(user: User | None, course: Course | None, db: Session) -> bool:
    """Returns whether a user may open regular course learning content."""
    if not course:
        return False
    if not user:
        return bool(course.is_guest_accessible)
    if is_admin(user):
        return True
    if is_teacher(user):
        return course.teacher_id == user.id
    if is_org(user):
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if not org:
            return False
        return db.query(OrganizationTeacher.id).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == course.teacher_id,
            OrganizationTeacher.status == "accepted",
        ).first() is not None
    if is_student(user):
        # Product rule: regular courses are currently public/free for all
        # authenticated students. When private/paid courses are introduced,
        # add CourseEnrollment/access_mode checks here.
        return True
    return False


def can(user: User | None, permission: str) -> bool:
    """Проверка наличия разрешения у пользователя на основе его роли."""
    permissions = {
        "edit_course": ["teacher", "admin", "organization"],
        "view_course": ["student", "teacher", "admin", "organization"],
        "manage_users": ["admin", "organization"],
        "submit_review": ["student"],
    }
    return bool(user and user.role.value in permissions.get(permission, []))

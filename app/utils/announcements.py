from datetime import datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.group import Group, GroupMember
from app.models.organization import (
    OrganizationAnnouncement,
    OrganizationAnnouncementDismissal,
    OrganizationStudent,
    OrganizationTeacher,
)
from app.models.user import User


TEACHER_AUDIENCES = ("teachers", "all")
STUDENT_AUDIENCES = ("students", "all")
VALID_AUDIENCES = ("teachers", "students", "all")


def get_teacher_organization_ids(db: Session, user_id: int) -> list[int]:
    return [
        row[0]
        for row in db.query(OrganizationTeacher.organization_id)
        .filter(
            OrganizationTeacher.teacher_id == user_id,
            OrganizationTeacher.status == "accepted",
        )
        .all()
    ]


def get_student_organization_ids(db: Session, user_id: int) -> list[int]:
    org_ids = {
        row[0]
        for row in db.query(OrganizationStudent.organization_id)
        .filter(
            OrganizationStudent.student_id == user_id,
            OrganizationStudent.status == "accepted",
        )
        .all()
    }
    group_org_ids = {
        row[0]
        for row in db.query(Group.organization_id)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .filter(
            GroupMember.student_id == user_id,
            Group.is_active == True,  # noqa: E712
        )
        .all()
    }
    return list(org_ids | group_org_ids)


def _role_visibility(user: User, db: Session) -> tuple[list[int], tuple[str, ...]]:
    if user.is_teacher:
        return get_teacher_organization_ids(db, user.id), TEACHER_AUDIENCES
    if user.is_student:
        return get_student_organization_ids(db, user.id), STUDENT_AUDIENCES
    return [], ()


def visible_announcements_query(db: Session, user: User):
    org_ids, audiences = _role_visibility(user, db)
    if not org_ids or not audiences:
        return None

    now = datetime.utcnow()
    return (
        db.query(OrganizationAnnouncement)
        .options(joinedload(OrganizationAnnouncement.organization))
        .outerjoin(
            OrganizationAnnouncementDismissal,
            and_(
                OrganizationAnnouncementDismissal.announcement_id == OrganizationAnnouncement.id,
                OrganizationAnnouncementDismissal.user_id == user.id,
            ),
        )
        .filter(
            OrganizationAnnouncement.organization_id.in_(org_ids),
            OrganizationAnnouncement.audience.in_(audiences),
            OrganizationAnnouncement.is_active == True,  # noqa: E712
            or_(
                OrganizationAnnouncement.expires_at.is_(None),
                OrganizationAnnouncement.expires_at > now,
            ),
            OrganizationAnnouncementDismissal.id.is_(None),
        )
    )


def get_visible_announcements(db: Session, user: User, limit: int = 3) -> list[OrganizationAnnouncement]:
    query = visible_announcements_query(db, user)
    if query is None:
        return []
    query = query.order_by(OrganizationAnnouncement.created_at.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def get_visible_announcement(db: Session, user: User, announcement_id: int) -> OrganizationAnnouncement | None:
    query = visible_announcements_query(db, user)
    if query is None:
        return None
    return query.filter(OrganizationAnnouncement.id == announcement_id).first()

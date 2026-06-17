from sqlalchemy.orm import Session

from app.models.group import Group, GroupMember
from app.models.organization import Organization
from app.models.user import User
from app.utils.group_membership import ACTIVE_GROUP_MEMBER_STATUS


def is_active_group_member(db: Session, group_id: int, student_id: int) -> bool:
    return (
        db.query(GroupMember.id)
        .filter(
            GroupMember.group_id == group_id,
            GroupMember.student_id == student_id,
            GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
        )
        .first()
        is not None
    )


def can_manage_group_content(db: Session, user: User | None, group: Group | None) -> bool:
    if not user or not group:
        return False
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        return bool(org and group.organization_id == org.id)
    if user.is_teacher:
        return group.teacher_id == user.id
    return False


def can_attempt_group_vocabulary(db: Session, user: User | None, group_id: int) -> bool:
    if not user:
        return False
    return is_active_group_member(db, group_id, user.id)

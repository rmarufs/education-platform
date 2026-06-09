from sqlalchemy.orm import Session

from app.models.group import GroupMember


ACTIVE_GROUP_MEMBER_STATUS = "active"


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


def active_members(members):
    return [
        member
        for member in members
        if member.status == ACTIVE_GROUP_MEMBER_STATUS
    ]

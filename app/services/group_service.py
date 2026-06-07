from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from app.models.user import User
from app.models.organization import Organization, OrganizationTeacher, OrganizationStudent
from app.models.group import Group, GroupMember, GroupJournalEntry, GroupPaymentEntry

def get_org_for_group(db: Session, group_id: int, user: User) -> tuple[Organization, Group]:
    org = db.query(Organization).filter(Organization.user_id == user.id).first()
    if not org:
        raise ValueError("Организация не найдена")
    group = db.query(Group).filter(
        Group.id == group_id,
        Group.organization_id == org.id
    ).first()
    if not group:
        raise ValueError("Группа не найдена")
    return org, group

def can_manage_group_content(db: Session, user: User, group: Group) -> bool:
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        return bool(org and group.organization_id == org.id)
    if user.is_teacher:
        return group.teacher_id == user.id
    return False

def get_manageable_group(db: Session, group_id: int, user: User) -> tuple[User, Group]:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise ValueError("Группа не найдена")
    if not can_manage_group_content(db, user, group):
        raise ValueError("Доступ запрещён")
    return user, group

def get_organization_groups(db: Session, org_id: int):
    groups = (
        db.query(Group)
        .options(
            joinedload(Group.teacher),
            joinedload(Group.members),
            joinedload(Group.modules),
            joinedload(Group.lessons),
        )
        .filter(Group.organization_id == org_id)
        .order_by(Group.created_at.desc())
        .all()
    )
    teacher_links = db.query(OrganizationTeacher).options(
        joinedload(OrganizationTeacher.teacher)
    ).filter(
        OrganizationTeacher.organization_id == org_id,
        OrganizationTeacher.status == "accepted"
    ).all()
    teachers = [link.teacher for link in teacher_links]
    return groups, teachers

def get_teacher_groups(db: Session, teacher_id: int):
    return db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.members),
        joinedload(Group.modules),
        joinedload(Group.lessons),
    ).filter(
        Group.teacher_id == teacher_id,
        Group.is_active == True,
    ).order_by(Group.created_at.desc()).all()

def create_group(db: Session, org: Organization, name: str, description: str, teacher_id: Optional[int]) -> Group:
    if teacher_id:
        link = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == teacher_id,
            OrganizationTeacher.status == "accepted",
        ).first()
        if not link:
            teacher_id = None

    group = Group(
        name=name.strip(),
        description=description.strip() or None,
        organization_id=org.id,
        teacher_id=teacher_id,
    )
    db.add(group)
    db.commit()
    return group

def update_group(db: Session, org: Organization, group_id: int, name: str, description: str, is_active: bool):
    group = db.query(Group).filter(Group.id == group_id, Group.organization_id == org.id).first()
    if not group:
        raise ValueError("Группа не найдена")
    group.name = name.strip()
    group.description = description.strip() or None
    group.is_active = is_active
    db.commit()

def delete_group(db: Session, org: Organization, group_id: int):
    group = db.query(Group).filter(Group.id == group_id, Group.organization_id == org.id).first()
    if not group:
        raise ValueError("Группа не найдена")
    db.delete(group)
    db.commit()

def assign_teacher(db: Session, org: Organization, group_id: int, teacher_id: Optional[int]):
    group = db.query(Group).filter(Group.id == group_id, Group.organization_id == org.id).first()
    if not group:
        raise ValueError("Группа не найдена")
    if teacher_id:
        link = db.query(OrganizationTeacher).filter(
            OrganizationTeacher.organization_id == org.id,
            OrganizationTeacher.teacher_id == teacher_id,
            OrganizationTeacher.status == "accepted",
        ).first()
        group.teacher_id = teacher_id if link else None
    else:
        group.teacher_id = None
    db.commit()

def add_student_to_group(db: Session, org: Organization, group_id: int, student_id: int, grade: Optional[int]) -> bool:
    group = db.query(Group).filter(Group.id == group_id, Group.organization_id == org.id).first()
    if not group:
        raise ValueError("Группа не найдена")
    
    org_membership = db.query(OrganizationStudent).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.student_id == student_id,
        OrganizationStudent.status == "accepted",
    ).first()
    if not org_membership:
        return False

    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == student_id,
    ).first()
    if not existing:
        member = GroupMember(
            group_id=group_id,
            student_id=student_id,
            grade=grade,
        )
        db.add(member)
        db.commit()
    return True

def bulk_add_students_to_group(db: Session, org: Organization, group_id: int, student_ids: List[int], grade: Optional[int]) -> tuple[int, int]:
    group = db.query(Group).filter(Group.id == group_id, Group.organization_id == org.id).first()
    if not group:
        raise ValueError("Группа не найдена")

    selected_ids = []
    seen_ids = set()
    for sid in student_ids:
        if sid not in seen_ids:
            seen_ids.add(sid)
            selected_ids.append(sid)

    if not selected_ids:
        raise ValueError("Не выбраны ученики")

    org_members = db.query(OrganizationStudent.student_id).filter(
        OrganizationStudent.organization_id == org.id,
        OrganizationStudent.status == "accepted",
        OrganizationStudent.student_id.in_(selected_ids),
    ).all()
    org_member_ids = {row[0] for row in org_members}

    existing_members = db.query(GroupMember.student_id).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id.in_(selected_ids),
    ).all()
    existing_ids = {row[0] for row in existing_members}

    added_count = 0
    skipped_count = 0
    for sid in selected_ids:
        if sid not in org_member_ids:
            continue
        if sid in existing_ids:
            skipped_count += 1
            continue

        db.add(GroupMember(
            group_id=group_id,
            student_id=sid,
            grade=grade,
        ))
        added_count += 1

    if added_count:
        db.commit()

    return added_count, skipped_count

def remove_student_from_group(db: Session, org: Organization, group_id: int, student_id: int):
    group = db.query(Group).filter(Group.id == group_id, Group.organization_id == org.id).first()
    if not group:
        raise ValueError("Группа не найдена")
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.student_id == student_id,
    ).first()
    if member:
        db.query(GroupJournalEntry).filter(
            GroupJournalEntry.group_id == group_id,
            GroupJournalEntry.student_id == student_id,
        ).delete(synchronize_session=False)
        db.query(GroupPaymentEntry).filter(
            GroupPaymentEntry.group_id == group_id,
            GroupPaymentEntry.student_id == student_id,
        ).delete(synchronize_session=False)
        db.delete(member)
        db.commit()

def update_group_avatar(db: Session, group: Group, avatar_url: str):
    group.avatar_url = avatar_url
    db.commit()

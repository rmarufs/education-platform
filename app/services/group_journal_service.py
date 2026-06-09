from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func
from app.models.group import Group, GroupModule, GroupJournalEntry, GroupMember
from app.services.group_lesson_service import ordered_group_lessons
from app.utils.group_membership import active_members

def get_group_for_journal(db: Session, group_id: int) -> Group | None:
    return db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.teacher),
        selectinload(Group.modules).selectinload(GroupModule.lessons),
        selectinload(Group.lessons),
        selectinload(Group.members).joinedload(GroupMember.student),
    ).filter(Group.id == group_id).first()

def get_journal_data(db: Session, group: Group):
    lessons = ordered_group_lessons(group)
    members = sorted(active_members(group.members), key=lambda member: ((member.student.name or "").lower(), member.student_id))
    lesson_ids = [lesson.id for lesson in lessons]
    student_ids = [member.student_id for member in members]

    entries = []
    if lesson_ids and student_ids:
        entries = db.query(GroupJournalEntry).filter(
            GroupJournalEntry.group_id == group.id,
            GroupJournalEntry.lesson_id.in_(lesson_ids),
            GroupJournalEntry.student_id.in_(student_ids),
        ).all()

    entries_map = {
        (entry.student_id, entry.lesson_id): entry
        for entry in entries
    }
    averages = {
        student_id: avg
        for student_id, avg in db.query(
            GroupJournalEntry.student_id,
            func.avg(GroupJournalEntry.grade),
        ).filter(
            GroupJournalEntry.group_id == group.id,
            GroupJournalEntry.student_id.in_(student_ids or [0]),
            GroupJournalEntry.present.is_(True),
            GroupJournalEntry.grade.isnot(None),
        ).group_by(GroupJournalEntry.student_id).all()
    }

    return lessons, members, entries_map, averages

def get_group_for_journal_save(db: Session, group_id: int) -> Group | None:
    return db.query(Group).options(
        selectinload(Group.modules).selectinload(GroupModule.lessons),
        selectinload(Group.lessons),
        selectinload(Group.members),
    ).filter(Group.id == group_id).first()

def save_journal_entries(db: Session, group: Group, form_data: dict) -> bool:
    lessons = ordered_group_lessons(group)
    lesson_ids = [lesson.id for lesson in lessons]
    student_ids = [member.student_id for member in active_members(group.members)]

    existing_entries = db.query(GroupJournalEntry).filter(
        GroupJournalEntry.group_id == group.id,
        GroupJournalEntry.lesson_id.in_(lesson_ids or [0]),
        GroupJournalEntry.student_id.in_(student_ids or [0]),
    ).all()
    entries_map = {
        (entry.student_id, entry.lesson_id): entry
        for entry in existing_entries
    }

    try:
        for student_id in student_ids:
            for lesson_id in lesson_ids:
                present = f"present_{student_id}_{lesson_id}" in form_data
                raw_grade = (form_data.get(f"grade_{student_id}_{lesson_id}") or "").strip()
                grade = int(raw_grade) if raw_grade else None

                if grade is not None and grade not in {1, 2, 3, 4, 5}:
                    return False
                if not present:
                    grade = None

                entry = entries_map.get((student_id, lesson_id))
                if entry:
                    entry.present = present
                    entry.grade = grade
                else:
                    db.add(GroupJournalEntry(
                        group_id=group.id,
                        lesson_id=lesson_id,
                        student_id=student_id,
                        present=present,
                        grade=grade,
                    ))

        db.commit()
        return True
    except ValueError:
        db.rollback()
        return False

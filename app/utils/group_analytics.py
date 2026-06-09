from collections import defaultdict
from typing import Iterable

from sqlalchemy.orm import Session, joinedload

from app.models.group import Group, GroupJournalEntry, GroupMember
from app.utils.group_membership import ACTIVE_GROUP_MEMBER_STATUS


def _round_metric(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


def build_group_analytics(db: Session, groups: Iterable[Group]) -> list[dict]:
    """Calculate journal analytics for the given groups without persisted aggregates."""
    groups = list(groups)
    if not groups:
        return []

    group_by_id = {group.id: group for group in groups}
    group_ids = list(group_by_id)

    members = (
        db.query(GroupMember)
        .options(joinedload(GroupMember.student))
        .filter(
            GroupMember.group_id.in_(group_ids),
            GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
        )
        .all()
    )
    member_ids_by_group: dict[int, set[int]] = defaultdict(set)
    member_by_group_student: dict[tuple[int, int], GroupMember] = {}
    for member in members:
        member_ids_by_group[member.group_id].add(member.student_id)
        member_by_group_student[(member.group_id, member.student_id)] = member

    active_student_ids = {member.student_id for member in members}
    entries = []
    if active_student_ids:
        entries = (
            db.query(GroupJournalEntry)
            .filter(
                GroupJournalEntry.group_id.in_(group_ids),
                GroupJournalEntry.student_id.in_(active_student_ids),
            )
            .all()
        )

    entries_by_group: dict[int, list[GroupJournalEntry]] = defaultdict(list)
    grades_by_group_student: dict[tuple[int, int], list[int]] = defaultdict(list)
    for entry in entries:
        if entry.student_id not in member_ids_by_group.get(entry.group_id, set()):
            continue
        entries_by_group[entry.group_id].append(entry)
        if entry.present and entry.grade is not None:
            grades_by_group_student[(entry.group_id, entry.student_id)].append(entry.grade)

    analytics = []
    for group in groups:
        group_entries = entries_by_group.get(group.id, [])
        marked_count = len(group_entries)
        present_count = sum(1 for entry in group_entries if entry.present)
        grades = [entry.grade for entry in group_entries if entry.present and entry.grade is not None]

        lagging_students = []
        for (entry_group_id, student_id), student_grades in grades_by_group_student.items():
            if entry_group_id != group.id or len(student_grades) < 2:
                continue
            average_grade = sum(student_grades) / len(student_grades)
            if average_grade < 3:
                member = member_by_group_student.get((group.id, student_id))
                if member and member.student:
                    lagging_students.append(
                        {
                            "student": member.student,
                            "group": group,
                            "average_grade": _round_metric(average_grade),
                            "grade_count": len(student_grades),
                        }
                    )

        lagging_students.sort(
            key=lambda item: ((item["student"].name or "").lower(), item["student"].id)
        )

        analytics.append(
            {
                "group": group,
                "marked_count": marked_count,
                "present_count": present_count,
                "attendance_percent": _round_metric((present_count / marked_count) * 100) if marked_count else None,
                "grade_count": len(grades),
                "average_grade": _round_metric(sum(grades) / len(grades)) if grades else None,
                "lagging_count": len(lagging_students),
                "lagging_students": lagging_students,
            }
        )

    return analytics


def build_student_analytics(db: Session, student_id: int) -> dict:
    """Calculate personal student stats across groups where the student is currently a member."""
    memberships = db.query(GroupMember.group_id).filter(
        GroupMember.student_id == student_id,
        GroupMember.status == ACTIVE_GROUP_MEMBER_STATUS,
    ).all()
    group_ids = [membership.group_id for membership in memberships]
    if not group_ids:
        return {
            "marked_count": 0,
            "present_count": 0,
            "attendance_percent": None,
            "grade_count": 0,
            "average_grade": None,
        }

    entries = (
        db.query(GroupJournalEntry)
        .filter(
            GroupJournalEntry.student_id == student_id,
            GroupJournalEntry.group_id.in_(group_ids),
        )
        .all()
    )

    marked_count = len(entries)
    present_count = sum(1 for entry in entries if entry.present)
    grades = [entry.grade for entry in entries if entry.present and entry.grade is not None]

    return {
        "marked_count": marked_count,
        "present_count": present_count,
        "attendance_percent": _round_metric((present_count / marked_count) * 100) if marked_count else None,
        "grade_count": len(grades),
        "average_grade": _round_metric(sum(grades) / len(grades)) if grades else None,
    }

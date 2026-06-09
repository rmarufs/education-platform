from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.group import Group, GroupMember, GroupPaymentEntry
from app.utils.datetime_helpers import (
    month_start as _month_start,
    parse_month as _parse_month,
    calculate_paid_until as _calculate_paid_until,
    payment_status as _payment_status,
    resolve_payment_day as _resolve_payment_day,
)
from app.utils.group_membership import active_members

def get_group_for_payments(db: Session, group_id: int) -> Group | None:
    return db.query(Group).options(
        joinedload(Group.organization),
        joinedload(Group.teacher),
        selectinload(Group.members).joinedload(GroupMember.student),
    ).filter(Group.id == group_id).first()

def get_payments_data(db: Session, group: Group, month: str | None):
    selected_month = _parse_month(month)
    members = sorted(active_members(group.members), key=lambda member: ((member.student.name or "").lower(), member.student_id))
    student_ids = [member.student_id for member in members]
    
    entries = []
    if student_ids:
        entries = db.query(GroupPaymentEntry).options(
            joinedload(GroupPaymentEntry.marked_by)
        ).filter(
            GroupPaymentEntry.group_id == group.id,
            GroupPaymentEntry.month == selected_month,
            GroupPaymentEntry.student_id.in_(student_ids),
        ).all()

    entries_map = {entry.student_id: entry for entry in entries}
    payment_status_map = {
        member.student_id: _payment_status(member.paid_until)
        for member in members
    }
    
    return members, entries_map, payment_status_map, selected_month

def get_group_for_payments_save(db: Session, group_id: int) -> Group | None:
    return db.query(Group).options(selectinload(Group.members)).filter(
        Group.id == group_id,
    ).first()

def save_payments(db: Session, group: Group, user_id: int, form_data: dict) -> date:
    selected_month = _parse_month(form_data.get("month"))
    members = active_members(group.members)
    student_ids = [member.student_id for member in members]
    now = datetime.utcnow()
    payment_month = _month_start(now.date())
    entry_months = list({selected_month, payment_month})
    
    existing_entries = db.query(GroupPaymentEntry).filter(
        GroupPaymentEntry.group_id == group.id,
        GroupPaymentEntry.month.in_(entry_months),
        GroupPaymentEntry.student_id.in_(student_ids or [0]),
    ).all()
    entries_map = {
        (entry.student_id, entry.month): entry
        for entry in existing_entries
    }

    for member in members:
        student_id = member.student_id
        payment_day = _resolve_payment_day(
            form_data.get(f"payment_day_{student_id}"),
            member.payment_day,
        )
        member.payment_day = payment_day
        is_paid = f"paid_{student_id}" in form_data
        entry_month = payment_month if is_paid else selected_month
        entry = entries_map.get((student_id, entry_month))
        
        if not entry:
            entry = GroupPaymentEntry(
                group_id=group.id,
                student_id=student_id,
                month=entry_month,
            )
            db.add(entry)

        if is_paid:
            paid_until = _calculate_paid_until(payment_day, now.date())
            member.paid_until = paid_until
            member.last_paid_at = now

            entry.is_paid = True
            entry.paid_at = now
            entry.paid_until = paid_until
            entry.action = "paid"
        else:
            entry.is_paid = False
            entry.paid_at = None
            entry.paid_until = None
            entry.action = "cancelled"
            
        entry.marked_by_id = user_id
        entry.payment_day = payment_day

    db.commit()
    return selected_month

def student_month_payment_entry(db: Session, group_id: int, student_id: int, month: date) -> GroupPaymentEntry | None:
    return db.query(GroupPaymentEntry).filter(
        GroupPaymentEntry.group_id == group_id,
        GroupPaymentEntry.student_id == student_id,
        GroupPaymentEntry.month == month,
    ).first()

def student_payment_overdue(db: Session, group_id: int, student_id: int, today: date | None = None) -> bool:
    today = today or date.today()
    if today.day <= 7:
        return False
    entry = student_month_payment_entry(db, group_id, student_id, _month_start(today))
    return not (entry and entry.is_paid)

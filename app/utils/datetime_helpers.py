"""Preparatory date and time helpers."""

import calendar
from datetime import date, datetime

from fastapi import HTTPException


def parse_homework_deadline(value: str | None) -> datetime | None:
    clean_value = (value or "").strip()
    if not clean_value:
        return None
    try:
        return datetime.fromisoformat(clean_value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный дедлайн")


def month_start(value: date | None = None) -> date:
    value = value or date.today()
    return date(value.year, value.month, 1)


def parse_month(value: str | None) -> date:
    if not value:
        return month_start()
    try:
        if len(value) == 7:
            parsed = datetime.strptime(value, "%Y-%m").date()
        else:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month")
    return month_start(parsed)


def last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def normalize_payment_day(payment_day: int, year: int, month: int) -> int:
    if payment_day < 1 or payment_day > 31:
        raise ValueError("payment_day must be between 1 and 31")
    return min(payment_day, last_day_of_month(year, month))


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def calculate_paid_until(payment_day: int, payment_date: date) -> date:
    next_year, next_month_value = next_month(payment_date.year, payment_date.month)
    next_normalized_day = normalize_payment_day(payment_day, next_year, next_month_value)
    return date(next_year, next_month_value, next_normalized_day)


def payment_status(paid_until: date | None, today: date | None = None) -> str:
    if not paid_until:
        return "unpaid"
    today = today or date.today()
    if today > paid_until:
        return "overdue"
    return "paid"


def resolve_payment_day(value, fallback: int | None = None) -> int:
    raw_value = str(value if value is not None else fallback or 1).strip()
    try:
        payment_day = int(raw_value)
    except (TypeError, ValueError):
        return 1
    if payment_day < 1 or payment_day > 31:
        return 1
    return payment_day


def parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expires_at")

"""enable rls on announcement and homework notification tables

Revision ID: 3c9e2a1b4d6f
Revises: f8b7c6d5e4a3
Create Date: 2026-05-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "3c9e2a1b4d6f"
down_revision: Union[str, None] = "f8b7c6d5e4a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RLS_TABLES = (
    "organization_announcements",
    "organization_announcement_dismissals",
    "group_homework_notifications",
)


def upgrade() -> None:
    for table_name in RLS_TABLES:
        op.execute(
            f'ALTER TABLE IF EXISTS public."{table_name}" ENABLE ROW LEVEL SECURITY'
        )


def downgrade() -> None:
    # Keep RLS enabled on downgrade to avoid reopening these public tables.
    pass

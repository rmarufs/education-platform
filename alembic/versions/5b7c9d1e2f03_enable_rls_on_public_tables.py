"""enable rls on public tables

Revision ID: 5b7c9d1e2f03
Revises: 3f2a1d8c9b7e
Create Date: 2026-05-20 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5b7c9d1e2f03"
down_revision: Union[str, None] = "3f2a1d8c9b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RLS_TABLES = (
    "contact_messages",
    "categories",
    "assessment_responses",
    "comments",
    "quiz_attempts",
    "answers",
    "alembic_version",
    "group_members",
    "organizations",
    "organization_students",
    "groups",
    "group_lessons",
    "organization_teachers",
    "group_materials",
    "group_modules",
    "group_payment_entries",
    "group_journal_entries",
    "vocabulary_items",
    "vocabulary_attempt_answers",
    "vocabulary_sets",
    "vocabulary_attempts",
    "group_lesson_chat_messages",
    "group_lesson_sessions",
)


def upgrade() -> None:
    for table_name in RLS_TABLES:
        op.execute(
            f'ALTER TABLE IF EXISTS public."{table_name}" ENABLE ROW LEVEL SECURITY'
        )


def downgrade() -> None:
    # Intentionally keep RLS enabled on downgrade. Disabling it would re-open
    # these public schema tables to Supabase PostgREST roles if no other guard
    # is present.
    pass

"""Add group lesson consistency constraints.

Revision ID: 20260608_group_lesson_c
Revises: 20260608_org_membership_b
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260608_group_lesson_c"
down_revision: Union[str, None] = "20260608_org_membership_b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_group_lessons_id_group_id",
        "group_lessons",
        ["id", "group_id"],
    )
    op.create_foreign_key(
        "fk_group_homeworks_lesson_group",
        "group_homeworks",
        "group_lessons",
        ["lesson_id", "group_id"],
        ["id", "group_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_group_journal_lesson_group",
        "group_journal_entries",
        "group_lessons",
        ["lesson_id", "group_id"],
        ["id", "group_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_group_lesson_progress_lesson_group",
        "group_lesson_progress",
        "group_lessons",
        ["lesson_id", "group_id"],
        ["id", "group_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_group_lesson_progress_lesson_group",
        "group_lesson_progress",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_group_journal_lesson_group",
        "group_journal_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_group_homeworks_lesson_group",
        "group_homeworks",
        type_="foreignkey",
    )
    op.drop_constraint("uq_group_lessons_id_group_id", "group_lessons", type_="unique")

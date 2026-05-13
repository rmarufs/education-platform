"""add group journal entries

Revision ID: 6b6d9e8f1a2b
Revises: 8f3a6c7b9d21
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6b6d9e8f1a2b"
down_revision: Union[str, None] = "8f3a6c7b9d21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_journal_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("grade IS NULL OR (grade >= 1 AND grade <= 5)", name="ck_group_journal_grade_range"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["group_lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "lesson_id", "student_id", name="uq_group_journal_entry"),
    )
    op.create_index("ix_group_journal_entries_group_id", "group_journal_entries", ["group_id"], unique=False)
    op.create_index("ix_group_journal_entries_lesson_id", "group_journal_entries", ["lesson_id"], unique=False)
    op.create_index("ix_group_journal_entries_student_id", "group_journal_entries", ["student_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_group_journal_entries_student_id", table_name="group_journal_entries")
    op.drop_index("ix_group_journal_entries_lesson_id", table_name="group_journal_entries")
    op.drop_index("ix_group_journal_entries_group_id", table_name="group_journal_entries")
    op.drop_table("group_journal_entries")

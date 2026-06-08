"""add group lesson progress

Revision ID: 2f4c8a9b1d6e
Revises: 5b7c9d1e2f03
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2f4c8a9b1d6e"
down_revision: Union[str, None] = "5b7c9d1e2f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_lesson_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "lesson_id", "student_id", name="uq_group_lesson_progress"),
    )
    op.create_index("ix_group_lesson_progress_group_id", "group_lesson_progress", ["group_id"], unique=False)
    op.create_index("ix_group_lesson_progress_lesson_id", "group_lesson_progress", ["lesson_id"], unique=False)
    op.create_index("ix_group_lesson_progress_student_id", "group_lesson_progress", ["student_id"], unique=False)
    op.execute('ALTER TABLE IF EXISTS public."group_lesson_progress" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_index("ix_group_lesson_progress_student_id", table_name="group_lesson_progress")
    op.drop_index("ix_group_lesson_progress_lesson_id", table_name="group_lesson_progress")
    op.drop_index("ix_group_lesson_progress_group_id", table_name="group_lesson_progress")
    op.drop_table("group_lesson_progress")

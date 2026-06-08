"""add group homework

Revision ID: 7e1f3a9c2b40
Revises: 2f4c8a9b1d6e
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e1f3a9c2b40"
down_revision: Union[str, None] = "2f4c8a9b1d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_homeworks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("group_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("material_url", sa.String(), nullable=True),
        sa.Column("material_type", sa.String(length=50), nullable=True),
        sa.Column("material_filename", sa.String(length=255), nullable=True),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "lesson_id", name="uq_group_homework_lesson"),
    )
    op.create_index("ix_group_homeworks_group_id", "group_homeworks", ["group_id"], unique=False)
    op.create_index("ix_group_homeworks_lesson_id", "group_homeworks", ["lesson_id"], unique=False)
    op.create_index("ix_group_homeworks_created_by_id", "group_homeworks", ["created_by_id"], unique=False)

    op.create_table(
        "group_homework_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("homework_id", sa.Integer(), sa.ForeignKey("group_homeworks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_url", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.UniqueConstraint("homework_id", "student_id", name="uq_group_homework_submission_student"),
    )
    op.create_index("ix_group_homework_submissions_homework_id", "group_homework_submissions", ["homework_id"], unique=False)
    op.create_index("ix_group_homework_submissions_student_id", "group_homework_submissions", ["student_id"], unique=False)

    op.execute('ALTER TABLE IF EXISTS public."group_homeworks" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE IF EXISTS public."group_homework_submissions" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_index("ix_group_homework_submissions_student_id", table_name="group_homework_submissions")
    op.drop_index("ix_group_homework_submissions_homework_id", table_name="group_homework_submissions")
    op.drop_table("group_homework_submissions")
    op.drop_index("ix_group_homeworks_created_by_id", table_name="group_homeworks")
    op.drop_index("ix_group_homeworks_lesson_id", table_name="group_homeworks")
    op.drop_index("ix_group_homeworks_group_id", table_name="group_homeworks")
    op.drop_table("group_homeworks")

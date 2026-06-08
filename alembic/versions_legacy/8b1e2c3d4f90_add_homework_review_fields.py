"""add homework review fields

Revision ID: 8b1e2c3d4f90
Revises: 4c2d8e1f9a70
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b1e2c3d4f90"
down_revision: Union[str, None] = "4c2d8e1f9a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("group_homework_submissions", sa.Column("teacher_comment", sa.Text(), nullable=True))
    op.add_column("group_homework_submissions", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("group_homework_submissions", sa.Column("reviewed_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_group_homework_submissions_reviewed_by",
        "group_homework_submissions",
        "users",
        ["reviewed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_group_homework_submissions_reviewed_by_id",
        "group_homework_submissions",
        ["reviewed_by_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_group_homework_submissions_reviewed_by_id", table_name="group_homework_submissions")
    op.drop_constraint(
        "fk_group_homework_submissions_reviewed_by",
        "group_homework_submissions",
        type_="foreignkey",
    )
    op.drop_column("group_homework_submissions", "reviewed_by_id")
    op.drop_column("group_homework_submissions", "reviewed_at")
    op.drop_column("group_homework_submissions", "teacher_comment")

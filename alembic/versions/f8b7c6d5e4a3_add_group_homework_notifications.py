"""add group homework notifications

Revision ID: f8b7c6d5e4a3
Revises: e6a1b2c3d4f5
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8b7c6d5e4a3"
down_revision: Union[str, None] = "e6a1b2c3d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_homework_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("homework_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False, server_default="new_homework"),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["homework_id"], ["group_homeworks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("homework_id", "student_id", "notification_type", name="uq_group_homework_notification_student"),
    )
    op.create_index("ix_group_homework_notifications_student_read", "group_homework_notifications", ["student_id", "read_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_group_homework_notifications_student_read", table_name="group_homework_notifications")
    op.drop_table("group_homework_notifications")

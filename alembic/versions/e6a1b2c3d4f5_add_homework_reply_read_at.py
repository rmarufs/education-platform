"""add homework reply read timestamp

Revision ID: e6a1b2c3d4f5
Revises: 9d3a5c7e1b20
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6a1b2c3d4f5"
down_revision: Union[str, None] = "9d3a5c7e1b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "group_homework_submissions",
        sa.Column("homework_reply_read_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("group_homework_submissions", "homework_reply_read_at")

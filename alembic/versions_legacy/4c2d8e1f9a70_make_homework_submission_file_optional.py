"""make homework submission file optional

Revision ID: 4c2d8e1f9a70
Revises: 7e1f3a9c2b40
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4c2d8e1f9a70"
down_revision: Union[str, None] = "7e1f3a9c2b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "group_homework_submissions",
        "file_url",
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("DELETE FROM group_homework_submissions WHERE file_url IS NULL")
    op.alter_column(
        "group_homework_submissions",
        "file_url",
        existing_type=sa.String(),
        nullable=False,
    )

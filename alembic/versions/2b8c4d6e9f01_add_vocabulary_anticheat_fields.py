"""add vocabulary anticheat fields

Revision ID: 2b8c4d6e9f01
Revises: 9f4d2c8a1b7e
Create Date: 2026-05-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b8c4d6e9f01"
down_revision: Union[str, None] = "9f4d2c8a1b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vocabulary_attempts",
        sa.Column(
            "anti_cheat_flags_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "vocabulary_attempts",
        sa.Column(
            "anti_cheat_teacher_visible",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "vocabulary_attempts",
        sa.Column("anti_cheat_last_flag_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vocabulary_attempts", "anti_cheat_last_flag_at")
    op.drop_column("vocabulary_attempts", "anti_cheat_teacher_visible")
    op.drop_column("vocabulary_attempts", "anti_cheat_flags_count")

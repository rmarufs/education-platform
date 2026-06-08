"""add guest accessible course flag

Revision ID: d4e5f6a7b8c9
Revises: c8a7d6e5f4b3
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c8a7d6e5f4b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GUEST_ACCESS_INDEX = "ux_courses_single_guest_accessible"


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column(
            "is_guest_accessible",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            GUEST_ACCESS_INDEX,
            "courses",
            ["is_guest_accessible"],
            unique=True,
            postgresql_where=sa.text("is_guest_accessible = true"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index(GUEST_ACCESS_INDEX, table_name="courses")
    op.drop_column("courses", "is_guest_accessible")

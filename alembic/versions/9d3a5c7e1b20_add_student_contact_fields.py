"""add student contact fields

Revision ID: 9d3a5c7e1b20
Revises: 7c4e2f8a9b10
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d3a5c7e1b20"
down_revision: Union[str, None] = "7c4e2f8a9b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("phone_number", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("parent_contact_name", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("parent_contact_phone", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "parent_contact_phone")
    op.drop_column("users", "parent_contact_name")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "birth_date")

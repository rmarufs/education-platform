"""add_cover_url_to_lessons

Revision ID: 3f2a1d8c9b7e
Revises: c4d8e2f1a901
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3f2a1d8c9b7e"
down_revision: Union[str, None] = "c4d8e2f1a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [column["name"] for column in inspector.get_columns("lessons")]
    if "cover_url" not in columns:
        op.add_column("lessons", sa.Column("cover_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [column["name"] for column in inspector.get_columns("lessons")]
    if "cover_url" in columns:
        op.drop_column("lessons", "cover_url")

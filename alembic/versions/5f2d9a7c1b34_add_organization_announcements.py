"""add organization announcements

Revision ID: 5f2d9a7c1b34
Revises: 8b1e2c3d4f90
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5f2d9a7c1b34"
down_revision: Union[str, None] = "8b1e2c3d4f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_announcements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_announcements_org_active_created",
        "organization_announcements",
        ["organization_id", "is_active", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_org_announcements_audience_expires",
        "organization_announcements",
        ["audience", "expires_at"],
        unique=False,
    )

    op.create_table(
        "organization_announcement_dismissals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("announcement_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["announcement_id"], ["organization_announcements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("announcement_id", "user_id", name="uq_announcement_user_dismissal"),
    )
    op.create_index(
        "ix_org_announcement_dismissals_user",
        "organization_announcement_dismissals",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_org_announcement_dismissals_user", table_name="organization_announcement_dismissals")
    op.drop_table("organization_announcement_dismissals")
    op.drop_index("ix_org_announcements_audience_expires", table_name="organization_announcements")
    op.drop_index("ix_org_announcements_org_active_created", table_name="organization_announcements")
    op.drop_table("organization_announcements")

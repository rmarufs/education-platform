"""add password reset tokens

Revision ID: c8a7d6e5f4b3
Revises: b3e7c9d2a4f6
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8a7d6e5f4b3"
down_revision: Union[str, None] = "b3e7c9d2a4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    should_create_table = True
    if not context.is_offline_mode():
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        should_create_table = not inspector.has_table("password_reset_tokens")

    if should_create_table:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("request_ip", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id "
        "ON password_reset_tokens (user_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_tokens_token_hash "
        "ON password_reset_tokens (token_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_expires_at "
        "ON password_reset_tokens (expires_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_used_at "
        "ON password_reset_tokens (used_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_tokens")

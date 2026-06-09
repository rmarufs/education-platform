"""Add soft membership fields to group members.

Revision ID: 20260610_gm_soft_a
Revises: 20260609_group_module_d
Create Date: 2026-06-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260610_gm_soft_a"
down_revision: Union[str, None] = "20260609_group_module_d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "group_members",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
    )
    op.add_column("group_members", sa.Column("removed_at", sa.DateTime(), nullable=True))
    op.add_column("group_members", sa.Column("left_at", sa.DateTime(), nullable=True))
    op.add_column("group_members", sa.Column("removed_by_id", sa.Integer(), nullable=True))
    op.add_column("group_members", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("group_members", sa.Column("last_joined_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_group_members_removed_by_id_users",
        "group_members",
        "users",
        ["removed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE group_members SET status = 'active' WHERE status IS NULL")


def downgrade() -> None:
    op.drop_constraint("fk_group_members_removed_by_id_users", "group_members", type_="foreignkey")
    op.drop_column("group_members", "last_joined_at")
    op.drop_column("group_members", "updated_at")
    op.drop_column("group_members", "removed_by_id")
    op.drop_column("group_members", "left_at")
    op.drop_column("group_members", "removed_at")
    op.drop_column("group_members", "status")

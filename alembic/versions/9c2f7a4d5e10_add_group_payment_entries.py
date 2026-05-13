"""add group payment entries

Revision ID: 9c2f7a4d5e10
Revises: 6b6d9e8f1a2b
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c2f7a4d5e10"
down_revision: Union[str, None] = "6b6d9e8f1a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_payment_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("marked_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["marked_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "student_id", "month", name="uq_group_payment_entry"),
    )
    op.create_index("ix_group_payment_entries_group_id", "group_payment_entries", ["group_id"], unique=False)
    op.create_index("ix_group_payment_entries_student_id", "group_payment_entries", ["student_id"], unique=False)
    op.create_index("ix_group_payment_entries_month", "group_payment_entries", ["month"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_group_payment_entries_month", table_name="group_payment_entries")
    op.drop_index("ix_group_payment_entries_student_id", table_name="group_payment_entries")
    op.drop_index("ix_group_payment_entries_group_id", table_name="group_payment_entries")
    op.drop_table("group_payment_entries")

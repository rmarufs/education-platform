"""add group fixed payment fields

Revision ID: b3e7c9d2a4f6
Revises: 065c20d48187
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3e7c9d2a4f6"
down_revision: Union[str, None] = "065c20d48187"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("group_members", sa.Column("payment_day", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("group_members", sa.Column("paid_until", sa.Date(), nullable=True))
    op.add_column("group_members", sa.Column("last_paid_at", sa.DateTime(), nullable=True))

    op.add_column("group_payment_entries", sa.Column("payment_day", sa.Integer(), nullable=True))
    op.add_column("group_payment_entries", sa.Column("paid_until", sa.Date(), nullable=True))
    op.add_column("group_payment_entries", sa.Column("action", sa.String(length=50), nullable=True))

    op.create_check_constraint(
        "ck_group_members_payment_day_range",
        "group_members",
        "payment_day IS NULL OR (payment_day >= 1 AND payment_day <= 31)",
    )
    op.create_check_constraint(
        "ck_group_payment_entries_payment_day_range",
        "group_payment_entries",
        "payment_day IS NULL OR (payment_day >= 1 AND payment_day <= 31)",
    )

    op.execute("UPDATE group_members SET payment_day = 1 WHERE payment_day IS NULL")


def downgrade() -> None:
    op.drop_constraint("ck_group_payment_entries_payment_day_range", "group_payment_entries", type_="check")
    op.drop_constraint("ck_group_members_payment_day_range", "group_members", type_="check")

    op.drop_column("group_payment_entries", "action")
    op.drop_column("group_payment_entries", "paid_until")
    op.drop_column("group_payment_entries", "payment_day")

    op.drop_column("group_members", "last_paid_at")
    op.drop_column("group_members", "paid_until")
    op.drop_column("group_members", "payment_day")

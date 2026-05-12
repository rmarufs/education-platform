"""add group modules and quiz urls for groups

Revision ID: 8f3a6c7b9d21
Revises: b7f3a9c2d1e4
Create Date: 2026-05-12 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f3a6c7b9d21"
down_revision: Union[str, None] = "b7f3a9c2d1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_modules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quiz_url", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_group_modules_id"), "group_modules", ["id"], unique=False)
    op.create_index("ix_group_modules_group_id", "group_modules", ["group_id"], unique=False)

    op.add_column("groups", sa.Column("quiz_url", sa.String(length=500), nullable=True))
    op.add_column("group_lessons", sa.Column("group_module_id", sa.Integer(), nullable=True))
    op.add_column("group_lessons", sa.Column("quiz_url", sa.String(length=500), nullable=True))
    op.create_foreign_key(
        "fk_group_lessons_group_module_id_group_modules",
        "group_lessons",
        "group_modules",
        ["group_module_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_group_lessons_group_module_id", "group_lessons", ["group_module_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_group_lessons_group_module_id", table_name="group_lessons")
    op.drop_constraint("fk_group_lessons_group_module_id_group_modules", "group_lessons", type_="foreignkey")
    op.drop_column("group_lessons", "quiz_url")
    op.drop_column("group_lessons", "group_module_id")
    op.drop_column("groups", "quiz_url")

    op.drop_index("ix_group_modules_group_id", table_name="group_modules")
    op.drop_index(op.f("ix_group_modules_id"), table_name="group_modules")
    op.drop_table("group_modules")

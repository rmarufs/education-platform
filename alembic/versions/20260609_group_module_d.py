"""Add group module consistency constraints.

Revision ID: 20260609_group_module_d
Revises: 20260608_group_lesson_c
Create Date: 2026-06-09
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260609_group_module_d"
down_revision: Union[str, None] = "20260608_group_lesson_c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_group_modules_id_group_id",
        "group_modules",
        ["id", "group_id"],
    )
    op.create_foreign_key(
        "fk_group_lessons_module_group",
        "group_lessons",
        "group_modules",
        ["group_module_id", "group_id"],
        ["id", "group_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_group_lessons_module_group",
        "group_lessons",
        type_="foreignkey",
    )
    op.drop_constraint("uq_group_modules_id_group_id", "group_modules", type_="unique")

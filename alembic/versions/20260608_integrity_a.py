"""Add basic data integrity constraints.

Revision ID: 20260608_integrity_a
Revises: 20260608_furuzon_baseline
Create Date: 2026-06-08
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260608_integrity_a"
down_revision: Union[str, None] = "20260608_furuzon_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_group_member_student",
        "group_members",
        ["group_id", "student_id"],
    )
    op.create_check_constraint(
        "ck_materials_single_target",
        "materials",
        "num_nonnulls(lesson_id, course_id) = 1",
    )
    op.create_check_constraint(
        "ck_quizzes_single_scope",
        "quizzes",
        "num_nonnulls(lesson_id, module_id, course_id) = 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_quizzes_single_scope", "quizzes", type_="check")
    op.drop_constraint("ck_materials_single_target", "materials", type_="check")
    op.drop_constraint("uq_group_member_student", "group_members", type_="unique")

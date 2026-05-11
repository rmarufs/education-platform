"""add_safe_performance_indexes

Revision ID: b7f3a9c2d1e4
Revises: e25a3ebae447
Create Date: 2026-05-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7f3a9c2d1e4"
down_revision: Union[str, None] = "e25a3ebae447"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = (
    ("ix_organizations_status_name", "organizations", "status, name"),
    ("ix_organizations_created_at", "organizations", "created_at"),
    ("ix_org_teachers_org_id_status", "organization_teachers", "organization_id, status"),
    ("ix_org_teachers_teacher_id_status", "organization_teachers", "teacher_id, status"),
    ("ix_org_students_org_id_status_created_at", "organization_students", "organization_id, status, created_at"),
    ("ix_org_students_student_id_status", "organization_students", "student_id, status"),
    ("ix_groups_org_id_created_at", "groups", "organization_id, created_at"),
    ("ix_groups_teacher_id_active_created_at", "groups", "teacher_id, is_active, created_at"),
    ("ix_group_members_student_id", "group_members", "student_id"),
    ("ix_group_lessons_group_id_order", "group_lessons", 'group_id, "order"'),
    ("ix_group_materials_lesson_id", "group_materials", "lesson_id"),
    ("ix_courses_rating", "courses", "rating"),
    ("ix_courses_category_id_rating", "courses", "category_id, rating"),
    ("ix_courses_teacher_id_created_at", "courses", "teacher_id, created_at"),
    ("ix_modules_course_id_order_index", "modules", "course_id, order_index"),
    ("ix_lessons_module_id_order_index", "lessons", "module_id, order_index"),
    ("ix_materials_course_id", "materials", "course_id"),
    ("ix_progress_student_completed_completed_at", "progress", "student_id, completed, completed_at"),
    ("ix_reviews_course_rating_created_at", "reviews", "course_id, rating, created_at"),
    ("ix_comments_lesson_parent_created_at", "comments", "lesson_id, parent_comment_id, created_at"),
    ("ix_comments_user_id", "comments", "user_id"),
    ("ix_quiz_attempts_student_id_quiz_id", "quiz_attempts", "student_id, quiz_id"),
    ("ix_quizzes_lesson_id", "quizzes", "lesson_id"),
    ("ix_quizzes_module_id", "quizzes", "module_id"),
    ("ix_quizzes_course_id", "quizzes", "course_id"),
    ("ix_questions_quiz_id", "questions", "quiz_id"),
    ("ix_answers_question_id", "answers", "question_id"),
)


def upgrade() -> None:
    for index_name, table_name, columns in INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name} ({columns})"
        )


def downgrade() -> None:
    for index_name, _, _ in reversed(INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {index_name}")

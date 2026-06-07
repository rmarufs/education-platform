"""
Deprecated: use app.services.course_service instead.
This file is kept for backward compatibility and will be removed later.
"""

from app.services.course_service import (
    _course_with_structure,
    _completed_lesson_ids,
    course_progress_state,
    is_module_complete_by_lessons,
    is_course_complete_by_lessons,
    _resolve_after_module,
    first_course_lesson_url,
    course_learning_url,
    next_after_lesson,
)

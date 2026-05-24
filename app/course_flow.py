from __future__ import annotations

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.course import Course
from app.models.lesson import Lesson
from app.models.module import Module
from app.models.progress import Progress


def _course_with_structure(db: Session, course_id: int) -> Course | None:
    return (
        db.query(Course)
        .options(
            selectinload(Course.modules).selectinload(Module.lessons),
        )
        .filter(Course.id == course_id)
        .first()
    )


def _completed_lesson_ids(db: Session, student_id: int, course: Course) -> set[int]:
    lesson_ids = [lesson.id for module in course.modules for lesson in module.lessons]
    return {
        lesson_id
        for lesson_id, in (
            db.query(Progress.lesson_id)
            .filter(
                Progress.student_id == student_id,
                Progress.completed == True,  # noqa: E712
                Progress.lesson_id.in_(lesson_ids),
            )
            .all()
        )
    } if lesson_ids else set()


def course_progress_state(db: Session, student_id: int, course_id: int) -> tuple[Course | None, set[int]]:
    course = _course_with_structure(db, course_id)
    if not course:
        return None, set()
    return course, _completed_lesson_ids(db, student_id, course)


def is_module_complete_by_lessons(module: Module, completed_lesson_ids: set[int]) -> bool:
    if not module.lessons:
        return True
    return all(lesson.id in completed_lesson_ids for lesson in module.lessons)


def is_course_complete_by_lessons(course: Course, completed_lesson_ids: set[int]) -> bool:
    if not course.modules:
        return True
    return all(is_module_complete_by_lessons(module, completed_lesson_ids) for module in course.modules)


def _resolve_after_module(course: Course, module: Module) -> str:
    modules = list(course.modules)
    current_index = next((idx for idx, item in enumerate(modules) if item.id == module.id), -1)

    for next_module in modules[current_index + 1:]:
        if next_module.lessons:
            return f"/lessons/{next_module.lessons[0].id}"

    return f"/courses/{course.id}/completed"


def first_course_lesson_url(course: Course) -> str | None:
    for module in course.modules:
        if module.lessons:
            return f"/lessons/{module.lessons[0].id}"
    return None


def course_learning_url(db: Session, student_id: int, course: Course) -> str | None:
    completed_lesson_ids = _completed_lesson_ids(db, student_id, course)
    if not completed_lesson_ids:
        return first_course_lesson_url(course)

    last_progress = (
        db.query(Progress)
        .join(Lesson, Progress.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .filter(
            Progress.student_id == student_id,
            Progress.completed == True,  # noqa: E712
            Module.course_id == course.id,
        )
        .order_by(Progress.completed_at.desc(), Progress.id.desc())
        .first()
    )
    if not last_progress:
        return first_course_lesson_url(course)

    return next_after_lesson(db, student_id, last_progress.lesson_id)


def next_after_lesson(db: Session, student_id: int, lesson_id: int) -> str:
    lesson = (
        db.query(Lesson)
        .options(joinedload(Lesson.module))
        .filter(Lesson.id == lesson_id)
        .first()
    )
    if not lesson or not lesson.module:
        return "/courses/catalog"

    course = _course_with_structure(db, lesson.module.course_id)
    if not course:
        return "/courses/catalog"

    module = next((item for item in course.modules if item.id == lesson.module_id), None)
    if not module:
        return f"/courses/{course.id}"

    lessons = list(module.lessons)
    current_index = next((idx for idx, item in enumerate(lessons) if item.id == lesson.id), -1)
    if current_index != -1 and current_index < len(lessons) - 1:
        return f"/lessons/{lessons[current_index + 1].id}"

    return _resolve_after_module(course, module)

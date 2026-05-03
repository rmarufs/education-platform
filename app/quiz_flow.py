from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.course import Course
from app.models.lesson import Lesson
from app.models.module import Module
from app.models.progress import Progress
from app.models.quiz import Quiz, QuizAttempt

QUIZ_PASS_PERCENTAGE = 80


def normalize_open_answer(value: str | None) -> str:
    return (value or "").strip().lower()


def quiz_owner_course_id(quiz: Quiz) -> int | None:
    if quiz.course_id:
        return quiz.course_id
    if quiz.module:
        return quiz.module.course_id
    if quiz.lesson and quiz.lesson.module:
        return quiz.lesson.module.course_id
    return None


def quiz_back_target(quiz: Quiz) -> tuple[str, str]:
    if quiz.lesson_id:
        return f"/lessons/{quiz.lesson_id}", "quiz.back_lesson"
    if quiz.module_id and quiz.module:
        return f"/courses/{quiz.module.course_id}#module-curriculum-{quiz.module_id}", "quiz.back_module"
    if quiz.course_id:
        return f"/courses/{quiz.course_id}", "quiz.back_course"
    return "/courses/catalog", "quiz.back_course"


def quiz_binding_label(quiz: Quiz) -> str:
    if quiz.lesson:
        return f"Урок: {quiz.lesson.title}"
    if quiz.module:
        return f"Модуль: {quiz.module.title}"
    if quiz.course:
        return f"Курс: {quiz.course.title}"
    return "Квиз"


def _course_with_structure(db: Session, course_id: int) -> Course | None:
    return (
        db.query(Course)
        .options(
            joinedload(Course.quiz),
            selectinload(Course.modules).joinedload(Module.quiz),
            selectinload(Course.modules).selectinload(Module.lessons).joinedload(Lesson.quiz),
        )
        .filter(Course.id == course_id)
        .first()
    )


def _state_sets(db: Session, student_id: int, course: Course) -> tuple[set[int], set[int]]:
    lesson_ids = [lesson.id for module in course.modules for lesson in module.lessons]
    quiz_ids = [
        quiz_id
        for quiz_id in (
            [course.quiz.id] if course.quiz else []
        ) + [
            module.quiz.id
            for module in course.modules
            if module.quiz
        ] + [
            lesson.quiz.id
            for module in course.modules
            for lesson in module.lessons
            if lesson.quiz
        ]
    ]

    completed_lesson_ids = {
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

    passed_quiz_ids = {
        quiz_id
        for quiz_id, in (
            db.query(QuizAttempt.quiz_id)
            .filter(
                QuizAttempt.student_id == student_id,
                QuizAttempt.quiz_id.in_(quiz_ids),
            )
            .all()
        )
    } if quiz_ids else set()

    return completed_lesson_ids, passed_quiz_ids


def course_progress_state(db: Session, student_id: int, course_id: int) -> tuple[Course | None, set[int], set[int]]:
    course = _course_with_structure(db, course_id)
    if not course:
        return None, set(), set()
    completed_lesson_ids, passed_quiz_ids = _state_sets(db, student_id, course)
    return course, completed_lesson_ids, passed_quiz_ids


def course_progress_state_from_obj(db: Session, student_id: int, course: Course) -> tuple[set[int], set[int]]:
    """Как course_progress_state, но принимает уже загруженный объект курса.
    Используйте, когда курс уже получен из БД, чтобы избежать повторного запроса."""
    return _state_sets(db, student_id, course)


def _lesson_quizzes_passed(lessons: Iterable[Lesson], passed_quiz_ids: set[int]) -> bool:
    return all(not lesson.quiz or lesson.quiz.id in passed_quiz_ids for lesson in lessons)


def _first_pending_lesson_quiz(module: Module, completed_lesson_ids: set[int], passed_quiz_ids: set[int]) -> int | None:
    for lesson in module.lessons:
        if lesson.id not in completed_lesson_ids:
            continue
        if lesson.quiz and lesson.quiz.id not in passed_quiz_ids:
            return lesson.quiz.id
    return None


def is_module_ready_for_quiz(module: Module, completed_lesson_ids: set[int], passed_quiz_ids: set[int]) -> bool:
    if not module.lessons:
        return True
    all_lessons_completed = all(lesson.id in completed_lesson_ids for lesson in module.lessons)
    return all_lessons_completed and _lesson_quizzes_passed(module.lessons, passed_quiz_ids)


def is_module_completed(module: Module, completed_lesson_ids: set[int], passed_quiz_ids: set[int]) -> bool:
    if not is_module_ready_for_quiz(module, completed_lesson_ids, passed_quiz_ids):
        return False
    return not module.quiz or module.quiz.id in passed_quiz_ids


def is_course_ready_for_quiz(course: Course, completed_lesson_ids: set[int], passed_quiz_ids: set[int]) -> bool:
    if not course.modules:
        return True
    return all(is_module_completed(module, completed_lesson_ids, passed_quiz_ids) for module in course.modules)


def is_course_completed(course: Course, completed_lesson_ids: set[int], passed_quiz_ids: set[int]) -> bool:
    if not is_course_ready_for_quiz(course, completed_lesson_ids, passed_quiz_ids):
        return False
    return not course.quiz or course.quiz.id in passed_quiz_ids


def quiz_is_unlocked(db: Session, student_id: int, quiz: Quiz) -> bool:
    course_id = quiz_owner_course_id(quiz)
    if not course_id:
        return False
    course = _course_with_structure(db, course_id)
    if not course:
        return False

    completed_lesson_ids, passed_quiz_ids = _state_sets(db, student_id, course)

    if quiz.lesson:
        return quiz.lesson.id in completed_lesson_ids
    if quiz.module:
        return is_module_ready_for_quiz(quiz.module, completed_lesson_ids, passed_quiz_ids)
    if quiz.course:
        return is_course_ready_for_quiz(course, completed_lesson_ids, passed_quiz_ids)
    return False


def lesson_quiz_unlocked(db: Session, student_id: int, lesson: Lesson) -> bool:
    if not lesson.module:
        return False
    course = _course_with_structure(db, lesson.module.course_id)
    if not course:
        return False
    completed_lesson_ids, _ = _state_sets(db, student_id, course)
    return lesson.id in completed_lesson_ids


def lesson_quiz_passed(db: Session, student_id: int, lesson: Lesson) -> bool:
    if not lesson.quiz:
        return True
    return (
        db.query(QuizAttempt.id)
        .filter(QuizAttempt.student_id == student_id, QuizAttempt.quiz_id == lesson.quiz.id)
        .first()
        is not None
    )


def _resolve_after_module(course: Course, module: Module, completed_lesson_ids: set[int], passed_quiz_ids: set[int]) -> str:
    modules = list(course.modules)
    current_index = next((idx for idx, item in enumerate(modules) if item.id == module.id), -1)

    for next_module in modules[current_index + 1:]:
        if next_module.lessons:
            return f"/lessons/{next_module.lessons[0].id}"
        if next_module.quiz and is_module_ready_for_quiz(next_module, completed_lesson_ids, passed_quiz_ids):
            if next_module.quiz.id not in passed_quiz_ids:
                return f"/quiz/{next_module.quiz.id}"

    if course.quiz and course.quiz.id not in passed_quiz_ids and is_course_ready_for_quiz(course, completed_lesson_ids, passed_quiz_ids):
        return f"/quiz/{course.quiz.id}"

    return f"/courses/{course.id}/completed"


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

    completed_lesson_ids, passed_quiz_ids = _state_sets(db, student_id, course)
    module = next((item for item in course.modules if item.id == lesson.module_id), None)
    if not module:
        return f"/courses/{course.id}"

    current_lesson = next((item for item in module.lessons if item.id == lesson.id), None)
    if current_lesson and current_lesson.quiz and current_lesson.quiz.id not in passed_quiz_ids:
        return f"/quiz/{current_lesson.quiz.id}"

    pending_lesson_quiz_id = _first_pending_lesson_quiz(module, completed_lesson_ids, passed_quiz_ids)
    if pending_lesson_quiz_id:
        return f"/quiz/{pending_lesson_quiz_id}"

    lessons = list(module.lessons)
    current_index = next((idx for idx, item in enumerate(lessons) if item.id == lesson.id), -1)
    if current_index != -1 and current_index < len(lessons) - 1:
        return f"/lessons/{lessons[current_index + 1].id}"

    if module.quiz and module.quiz.id not in passed_quiz_ids and is_module_ready_for_quiz(module, completed_lesson_ids, passed_quiz_ids):
        return f"/quiz/{module.quiz.id}"

    return _resolve_after_module(course, module, completed_lesson_ids, passed_quiz_ids)


def next_after_quiz(db: Session, student_id: int, quiz_id: int) -> str:
    quiz = (
        db.query(Quiz)
        .options(
            joinedload(Quiz.lesson).joinedload(Lesson.module),
            joinedload(Quiz.module),
            joinedload(Quiz.course),
        )
        .filter(Quiz.id == quiz_id)
        .first()
    )
    if not quiz:
        return "/courses/catalog"

    if quiz.lesson_id:
        return next_after_lesson(db, student_id, quiz.lesson_id)

    course_id = quiz_owner_course_id(quiz)
    if not course_id:
        return "/courses/catalog"

    course = _course_with_structure(db, course_id)
    if not course:
        return "/courses/catalog"

    completed_lesson_ids, passed_quiz_ids = _state_sets(db, student_id, course)

    if quiz.module_id:
        module = next((item for item in course.modules if item.id == quiz.module_id), None)
        if not module:
            return f"/courses/{course.id}"
        return _resolve_after_module(course, module, completed_lesson_ids, passed_quiz_ids)

    return f"/courses/{course.id}/completed"

from urllib.parse import urlparse
from sqlalchemy.orm import Session
from app.models.group import Group, GroupLesson, GroupLessonProgress

def ordered_group_lessons(group: Group) -> list[GroupLesson]:
    ordered_lessons = []
    seen_lesson_ids = set()
    for module in sorted(group.modules, key=lambda item: (item.order_index or 0, item.id)):
        for item in sorted(module.lessons, key=lambda lesson_item: (lesson_item.order or 0, lesson_item.id)):
            if item.group_id == group.id and item.id not in seen_lesson_ids:
                ordered_lessons.append(item)
                seen_lesson_ids.add(item.id)

    unassigned_lessons = sorted(
        [item for item in group.lessons if item.group_module_id is None and item.id not in seen_lesson_ids],
        key=lambda item: (item.order or 0, item.id),
    )
    ordered_lessons.extend(unassigned_lessons)
    return ordered_lessons

def get_next_group_lesson_for_student(db: Session, group: Group, student_id: int) -> GroupLesson | None:
    ordered_lessons_list = ordered_group_lessons(group)
    if not ordered_lessons_list:
        return None

    lesson_ids = [lesson.id for lesson in ordered_lessons_list]
    completed_lesson_ids = {
        lesson_id
        for (lesson_id,) in db.query(GroupLessonProgress.lesson_id).filter(
            GroupLessonProgress.group_id == group.id,
            GroupLessonProgress.student_id == student_id,
            GroupLessonProgress.lesson_id.in_(lesson_ids),
        ).all()
    }

    for lesson in ordered_lessons_list:
        if lesson.id not in completed_lesson_ids:
            return lesson

    return ordered_lessons_list[-1]

def validate_quiz_url(quiz_url: str) -> str:
    clean_url = quiz_url.strip()
    if not clean_url:
        raise ValueError("URL cannot be empty")
    parsed = urlparse(clean_url)
    if not all([parsed.scheme, parsed.netloc]):
        raise ValueError("Invalid URL format")
    return clean_url

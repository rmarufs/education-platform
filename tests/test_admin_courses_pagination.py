from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from app.models.course import Course
from app.models.lesson import Lesson
from app.models.module import Module
from app.models.progress import Progress
from app.models.user import User, UserRole


def _allow_multiple_non_guest_courses(db_session) -> None:
    db_session.execute(text("DROP INDEX IF EXISTS ux_courses_single_guest_accessible"))
    db_session.commit()


def _user(db_session, *, name: str, email: str, role: UserRole, created_at: datetime | None = None) -> User:
    user = User(
        name=name,
        email=email,
        password_hash="test-hash",
        role=role,
        is_active=True,
        created_at=created_at or datetime(2025, 1, 1),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _course(db_session, *, teacher: User, title: str, created_at: datetime, level: str = "Beginner") -> Course:
    course = Course(
        title=title,
        description=f"{title} description",
        teacher_id=teacher.id,
        level=level,
        created_at=created_at,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


def _module_with_lesson(db_session, course: Course, *, lesson_title: str) -> Lesson:
    module = Module(course_id=course.id, title=f"{course.title} module", order_index=1)
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)

    lesson = Lesson(module_id=module.id, title=lesson_title, order_index=1)
    db_session.add(lesson)
    db_session.commit()
    db_session.refresh(lesson)
    return lesson


def _admin(db_session) -> User:
    return _user(
        db_session,
        name="Admin Courses",
        email="admin-courses@example.test",
        role=UserRole.admin,
    )


def _teacher(db_session) -> User:
    return _user(
        db_session,
        name="Teacher Courses",
        email="teacher-courses@example.test",
        role=UserRole.teacher,
    )


def test_admin_courses_page_one_uses_page_size_and_created_at_sort(client, db_session, login_as):
    _allow_multiple_non_guest_courses(db_session)
    admin = _admin(db_session)
    teacher = _teacher(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        _course(
            db_session,
            teacher=teacher,
            title=f"Course {index}",
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    response = client.get("/admin/courses?page=1&per_page=3")

    assert response.status_code == 200
    body = response.text
    assert "Всего: 6 курсов" in body
    assert "Страница 1 из 2" in body
    assert "Teacher Courses" in body
    assert "Course 5" in body
    assert "Course 4" in body
    assert "Course 3" in body
    assert "Course 2" not in body
    assert body.index("Course 5") < body.index("Course 4") < body.index("Course 3")


def test_admin_courses_page_two_does_not_repeat_page_one(client, db_session, login_as):
    _allow_multiple_non_guest_courses(db_session)
    admin = _admin(db_session)
    teacher = _teacher(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        _course(
            db_session,
            teacher=teacher,
            title=f"Course {index}",
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    page_one = client.get("/admin/courses?page=1&per_page=3").text
    page_two = client.get("/admin/courses?page=2&per_page=3").text

    assert "Course 5" in page_one
    assert "Course 4" in page_one
    assert "Course 3" in page_one
    assert "Course 5" not in page_two
    assert "Course 4" not in page_two
    assert "Course 3" not in page_two
    assert "Course 2" in page_two
    assert "Course 1" in page_two
    assert "Course 0" in page_two


def test_admin_courses_student_counts_for_visible_page(client, db_session, login_as):
    _allow_multiple_non_guest_courses(db_session)
    admin = _admin(db_session)
    teacher = _teacher(db_session)
    student_one = _user(db_session, name="Student One", email="student-one@example.test", role=UserRole.student)
    student_two = _user(db_session, name="Student Two", email="student-two@example.test", role=UserRole.student)
    progress_course = _course(
        db_session,
        teacher=teacher,
        title="Progress Course",
        created_at=datetime(2026, 1, 3),
    )
    empty_course = _course(
        db_session,
        teacher=teacher,
        title="Empty Progress Course",
        created_at=datetime(2026, 1, 2),
    )
    hidden_course = _course(
        db_session,
        teacher=teacher,
        title="Hidden Old Course",
        created_at=datetime(2026, 1, 1),
    )

    first_lesson = _module_with_lesson(db_session, progress_course, lesson_title="Progress Lesson One")
    second_lesson = _module_with_lesson(db_session, progress_course, lesson_title="Progress Lesson Two")
    db_session.add_all([
        Progress(student_id=student_one.id, lesson_id=first_lesson.id),
        Progress(student_id=student_one.id, lesson_id=second_lesson.id),
        Progress(student_id=student_two.id, lesson_id=first_lesson.id),
    ])
    db_session.commit()

    login_as(client, admin)
    response = client.get("/admin/courses?page=1&per_page=2")

    assert response.status_code == 200
    body = response.text
    assert "Всего: 3 курсов" in body
    assert "Страница 1 из 2" in body
    assert "Progress Course" in body
    assert "Empty Progress Course" in body
    assert hidden_course.title not in body
    assert '<span style="font-weight:600;">2</span>' in body
    assert '<span style="font-weight:600;">0</span>' in body
    assert "Teacher Courses" in body


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page=-1",
        "per_page=0",
        "per_page=-1",
        "per_page=101",
    ],
)
def test_admin_courses_rejects_invalid_pagination_params(client, db_session, login_as, query):
    admin = _admin(db_session)

    login_as(client, admin)
    response = client.get(f"/admin/courses?{query}")

    assert response.status_code == 422


def test_admin_delete_course_redirect_still_goes_to_admin_courses(client, db_session, login_as):
    admin = _admin(db_session)
    teacher = _teacher(db_session)
    course = _course(
        db_session,
        teacher=teacher,
        title="Delete Redirect Course",
        created_at=datetime(2026, 1, 1),
    )

    csrf_token = login_as(client, admin)
    response = client.post(
        f"/admin/courses/{course.id}/delete",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/courses"

from app.models.course import Course
from app.models.group import Group, GroupHomework, GroupHomeworkNotification, GroupLesson
from app.models.organization import Organization
from app.models.user import User, UserRole


def _user(db_session, *, role: UserRole, email: str) -> User:
    user = User(
        name=email.split("@", 1)[0],
        email=email,
        password_hash="test-hash",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_delete_course_does_not_500_and_deletes_course(client, db_session, login_as):
    admin = _user(db_session, role=UserRole.admin, email="admin@example.test")
    teacher = _user(db_session, role=UserRole.teacher, email="teacher@example.test")
    course = Course(
        title="P0 Course",
        description="Runtime safety test",
        teacher_id=teacher.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    csrf_token = login_as(client, admin)
    response = client.post(
        f"/admin/courses/{course.id}/delete",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/courses"
    assert db_session.get(Course, course.id) is None


def test_delete_group_lesson_with_homework_does_not_500(client, db_session, login_as):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    student = _user(db_session, role=UserRole.student, email="student@example.test")
    organization = Organization(
        user_id=org_user.id,
        name="P0 Org",
        status="approved",
        is_open=True,
    )
    db_session.add(organization)
    db_session.commit()
    db_session.refresh(organization)

    group = Group(name="P0 Group", organization_id=organization.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    lesson = GroupLesson(group_id=group.id, title="P0 Lesson", order=1)
    db_session.add(lesson)
    db_session.commit()
    db_session.refresh(lesson)

    homework = GroupHomework(
        group_id=group.id,
        lesson_id=lesson.id,
        description="P0 homework",
    )
    db_session.add(homework)
    db_session.commit()
    db_session.refresh(homework)

    notification = GroupHomeworkNotification(
        homework_id=homework.id,
        student_id=student.id,
    )
    db_session.add(notification)
    db_session.commit()

    csrf_token = login_as(client, org_user)
    response = client.post(
        f"/groups/{group.id}/lessons/{lesson.id}/delete",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == f"/groups/{group.id}/manage"
    assert db_session.get(GroupLesson, lesson.id) is None

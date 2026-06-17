from app.models.group import Group, GroupLesson, GroupMember
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.services.group_permissions import (
    can_attempt_group_vocabulary,
    can_manage_group_content,
    is_active_group_member,
)


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


def _organization(db_session, owner: User, *, name: str) -> Organization:
    organization = Organization(
        user_id=owner.id,
        name=name,
        status="approved",
        is_open=True,
    )
    db_session.add(organization)
    db_session.commit()
    db_session.refresh(organization)
    return organization


def _group(db_session, organization: Organization, *, teacher: User | None = None) -> Group:
    group = Group(
        name="RBAC Group",
        organization_id=organization.id,
        teacher_id=teacher.id if teacher else None,
    )
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    return group


def _membership(db_session, group: Group, student: User, *, status: str = "active") -> GroupMember:
    membership = GroupMember(
        group_id=group.id,
        student_id=student.id,
        status=status,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    return membership


def _lesson(db_session, group: Group, *, title: str = "RBAC Lesson") -> GroupLesson:
    lesson = GroupLesson(group_id=group.id, title=title, description="Lesson", order=1)
    db_session.add(lesson)
    db_session.commit()
    db_session.refresh(lesson)
    return lesson


def test_organization_owner_can_manage_group_content(db_session):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization)

    assert can_manage_group_content(db_session, org_user, group) is True


def test_assigned_teacher_can_manage_group_content(db_session):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    teacher = _user(db_session, role=UserRole.teacher, email="teacher@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization, teacher=teacher)

    assert can_manage_group_content(db_session, teacher, group) is True


def test_unrelated_teacher_cannot_manage_group_content(db_session):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    teacher = _user(db_session, role=UserRole.teacher, email="teacher@example.test")
    other_teacher = _user(db_session, role=UserRole.teacher, email="other@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization, teacher=teacher)

    assert can_manage_group_content(db_session, other_teacher, group) is False


def test_active_student_can_attempt_but_cannot_manage_group_vocabulary(db_session):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    student = _user(db_session, role=UserRole.student, email="student@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization)
    _membership(db_session, group, student)

    assert is_active_group_member(db_session, group.id, student.id) is True
    assert can_attempt_group_vocabulary(db_session, student, group.id) is True
    assert can_manage_group_content(db_session, student, group) is False


def test_inactive_student_cannot_attempt_group_vocabulary(db_session):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    student = _user(db_session, role=UserRole.student, email="student@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization)
    _membership(db_session, group, student, status="removed")

    assert is_active_group_member(db_session, group.id, student.id) is False
    assert can_attempt_group_vocabulary(db_session, student, group.id) is False


def test_unrelated_organization_cannot_manage_group_content(db_session):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    other_org_user = _user(db_session, role=UserRole.organization, email="other-org@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    _organization(db_session, other_org_user, name="Other Org")
    group = _group(db_session, organization)

    assert can_manage_group_content(db_session, other_org_user, group) is False


def test_admin_does_not_get_group_vocabulary_access_by_default(db_session):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    admin = _user(db_session, role=UserRole.admin, email="admin@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization)

    assert can_manage_group_content(db_session, admin, group) is False
    assert can_attempt_group_vocabulary(db_session, admin, group.id) is False


def test_organization_owner_can_create_edit_delete_group_lessons(client, db_session, login_as):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization)
    lesson = _lesson(db_session, group, title="Existing Lesson")

    csrf_token = login_as(client, org_user)
    create_response = client.post(
        f"/groups/{group.id}/lessons/create",
        data={"title": "Created Lesson", "description": "Created", "order": "2"},
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )
    assert create_response.status_code == 302
    assert create_response.headers["location"] == f"/groups/{group.id}/manage?success=lesson_created"
    assert db_session.query(GroupLesson).filter_by(group_id=group.id, title="Created Lesson").first()

    edit_response = client.post(
        f"/groups/{group.id}/lessons/{lesson.id}/edit",
        data={"title": "Edited Lesson", "description": "Edited", "order": "3"},
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )
    assert edit_response.status_code == 302
    assert edit_response.headers["location"] == f"/groups/{group.id}/manage?success=lesson_saved"
    db_session.refresh(lesson)
    assert lesson.title == "Edited Lesson"

    delete_response = client.post(
        f"/groups/{group.id}/lessons/{lesson.id}/delete",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )
    assert delete_response.status_code == 302
    assert delete_response.headers["location"] == f"/groups/{group.id}/manage"
    assert db_session.get(GroupLesson, lesson.id) is None


def test_assigned_teacher_can_create_edit_delete_group_lessons(client, db_session, login_as):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    teacher = _user(db_session, role=UserRole.teacher, email="teacher@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization, teacher=teacher)
    lesson = _lesson(db_session, group, title="Teacher Lesson")

    csrf_token = login_as(client, teacher)
    create_response = client.post(
        f"/groups/{group.id}/lessons/create",
        data={"title": "Teacher Created", "description": "Created", "order": "2"},
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )
    assert create_response.status_code == 302
    assert create_response.headers["location"] == f"/groups/{group.id}/manage?success=lesson_created"

    edit_response = client.post(
        f"/groups/{group.id}/lessons/{lesson.id}/edit",
        data={"title": "Teacher Edited", "description": "Edited", "order": "3"},
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )
    assert edit_response.status_code == 302
    assert edit_response.headers["location"] == f"/groups/{group.id}/manage?success=lesson_saved"
    db_session.refresh(lesson)
    assert lesson.title == "Teacher Edited"

    delete_response = client.post(
        f"/groups/{group.id}/lessons/{lesson.id}/delete",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )
    assert delete_response.status_code == 302
    assert delete_response.headers["location"] == f"/groups/{group.id}/manage"
    assert db_session.get(GroupLesson, lesson.id) is None


def test_unrelated_teacher_and_admin_are_denied_group_lesson_management(client, db_session, login_as):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    teacher = _user(db_session, role=UserRole.teacher, email="teacher@example.test")
    other_teacher = _user(db_session, role=UserRole.teacher, email="other@example.test")
    admin = _user(db_session, role=UserRole.admin, email="admin@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization, teacher=teacher)

    csrf_token = login_as(client, other_teacher)
    teacher_response = client.post(
        f"/groups/{group.id}/lessons/create",
        data={"title": "Denied", "description": "Denied", "order": "1"},
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )
    assert teacher_response.status_code == 403

    csrf_token = login_as(client, admin)
    admin_response = client.post(
        f"/groups/{group.id}/lessons/create",
        data={"title": "Denied", "description": "Denied", "order": "1"},
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )
    assert admin_response.status_code == 403


def test_active_student_can_view_group_lesson(client, db_session, login_as):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    student = _user(db_session, role=UserRole.student, email="student@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization)
    lesson = _lesson(db_session, group)
    _membership(db_session, group, student)

    login_as(client, student)
    response = client.get(
        f"/groups/{group.id}/lessons/{lesson.id}",
        follow_redirects=False,
    )

    assert response.status_code == 200


def test_inactive_student_is_denied_group_lesson_view(client, db_session, login_as):
    org_user = _user(db_session, role=UserRole.organization, email="org@example.test")
    student = _user(db_session, role=UserRole.student, email="student@example.test")
    organization = _organization(db_session, org_user, name="Owner Org")
    group = _group(db_session, organization)
    lesson = _lesson(db_session, group)
    _membership(db_session, group, student, status="removed")

    login_as(client, student)
    response = client.get(
        f"/groups/{group.id}/lessons/{lesson.id}",
        follow_redirects=False,
    )

    assert response.status_code == 403

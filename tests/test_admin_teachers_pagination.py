from datetime import datetime, timedelta

import pytest

from app.models.organization import Organization, OrganizationTeacher
from app.models.user import User, UserRole


def _user(
    db_session,
    *,
    name: str,
    email: str,
    role: UserRole,
    created_at: datetime | None = None,
    documents: str | None = None,
) -> User:
    user = User(
        name=name,
        email=email,
        password_hash="test-hash",
        role=role,
        is_active=True,
        created_at=created_at or datetime(2025, 1, 1),
        documents=documents,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _admin(db_session) -> User:
    return _user(
        db_session,
        name="Admin Teachers",
        email="admin-teachers@example.test",
        role=UserRole.admin,
    )


def _organization(db_session, *, name: str = "Admin Teacher Org") -> Organization:
    owner = _user(
        db_session,
        name=f"{name} Owner",
        email=f"{name.lower().replace(' ', '-')}@example.test",
        role=UserRole.organization,
    )
    org = Organization(user_id=owner.id, name=name, status="approved", is_open=True)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


def _link_teacher(db_session, *, org: Organization, teacher: User, status: str) -> OrganizationTeacher:
    link = OrganizationTeacher(organization_id=org.id, teacher_id=teacher.id, status=status)
    db_session.add(link)
    db_session.commit()
    db_session.refresh(link)
    return link


def test_admin_teachers_pending_page_one_uses_page_size_and_sort(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        _user(
            db_session,
            name=f"Pending-{index}",
            email=f"pending-{index}@example.test",
            role=UserRole.teacher_pending,
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    response = client.get("/admin/teachers?pending_page=1&active_page=1&per_page=3")

    assert response.status_code == 200
    body = response.text
    assert "Заявки на рассмотрении (6)" in body
    assert "Активные преподаватели (0)" in body
    assert "Страница 1 из 2" in body
    assert "Pending-5" in body
    assert "Pending-4" in body
    assert "Pending-3" in body
    assert "Pending-2" not in body
    assert body.index("Pending-5") < body.index("Pending-4") < body.index("Pending-3")
    assert "active_page=1&amp;per_page=3&amp;pending_page=2" in body


def test_admin_teachers_pending_page_two_does_not_repeat_page_one(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        _user(
            db_session,
            name=f"Pending-{index}",
            email=f"pending-{index}@example.test",
            role=UserRole.teacher_pending,
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    page_one = client.get("/admin/teachers?pending_page=1&per_page=3").text
    page_two = client.get("/admin/teachers?pending_page=2&per_page=3").text

    assert "Pending-5" in page_one
    assert "Pending-4" in page_one
    assert "Pending-3" in page_one
    assert "Pending-5" not in page_two
    assert "Pending-4" not in page_two
    assert "Pending-3" not in page_two
    assert "Pending-2" in page_two
    assert "Pending-1" in page_two
    assert "Pending-0" in page_two


def test_admin_teachers_active_page_one_uses_page_size_and_sort(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        _user(
            db_session,
            name=f"Active-{index}",
            email=f"active-{index}@example.test",
            role=UserRole.teacher,
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    response = client.get("/admin/teachers?pending_page=1&active_page=1&per_page=3")

    assert response.status_code == 200
    body = response.text
    assert "Заявки на рассмотрении (0)" in body
    assert "Активные преподаватели (6)" in body
    assert "Страница 1 из 2" in body
    assert "Active-5" in body
    assert "Active-4" in body
    assert "Active-3" in body
    assert "Active-2" not in body
    assert body.index("Active-5") < body.index("Active-4") < body.index("Active-3")
    assert "pending_page=1&amp;per_page=3&amp;active_page=2" in body


def test_admin_teachers_active_page_two_does_not_repeat_page_one(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        _user(
            db_session,
            name=f"Active-{index}",
            email=f"active-{index}@example.test",
            role=UserRole.teacher,
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    page_one = client.get("/admin/teachers?active_page=1&per_page=3").text
    page_two = client.get("/admin/teachers?active_page=2&per_page=3").text

    assert "Active-5" in page_one
    assert "Active-4" in page_one
    assert "Active-3" in page_one
    assert "Active-5" not in page_two
    assert "Active-4" not in page_two
    assert "Active-3" not in page_two
    assert "Active-2" in page_two
    assert "Active-1" in page_two
    assert "Active-0" in page_two


def test_admin_teachers_keeps_pending_active_org_and_document_rendering(client, db_session, login_as):
    admin = _admin(db_session)
    org = _organization(db_session, name="Visible Teacher Org")
    pending = _user(
        db_session,
        name="Visible Pending Teacher",
        email="visible-pending@example.test",
        role=UserRole.teacher_pending,
        created_at=datetime(2026, 1, 2),
        documents="teacher_documents/visible.pdf",
    )
    active = _user(
        db_session,
        name="Visible Active Teacher",
        email="visible-active@example.test",
        role=UserRole.teacher,
        created_at=datetime(2026, 1, 3),
    )
    student = _user(
        db_session,
        name="Not A Teacher",
        email="not-a-teacher@example.test",
        role=UserRole.student,
        created_at=datetime(2026, 1, 4),
    )
    _link_teacher(db_session, org=org, teacher=pending, status="pending")
    _link_teacher(db_session, org=org, teacher=active, status="accepted")

    login_as(client, admin)
    response = client.get("/admin/teachers?pending_page=1&active_page=1&per_page=25")

    assert response.status_code == 200
    body = response.text
    assert "Заявки на рассмотрении (1)" in body
    assert "Активные преподаватели (1)" in body
    assert pending.name in body
    assert active.name in body
    assert student.name not in body
    assert "Visible Teacher Org" in body
    assert f"/admin/teachers/{pending.id}/document" in body
    assert f"/admin/teachers/{pending.id}/approve" in body
    assert f"/admin/teachers/{pending.id}/reject" in body
    assert f"/admin/teachers/{active.id}/remove-from-org" in body


@pytest.mark.parametrize(
    "query",
    [
        "pending_page=0",
        "pending_page=-1",
        "active_page=0",
        "active_page=-1",
        "per_page=0",
        "per_page=-1",
        "per_page=101",
    ],
)
def test_admin_teachers_rejects_invalid_pagination_params(client, db_session, login_as, query):
    admin = _admin(db_session)

    login_as(client, admin)
    response = client.get(f"/admin/teachers?{query}")

    assert response.status_code == 422


def test_admin_teacher_approve_redirect_still_goes_to_admin_teachers(client, db_session, login_as):
    admin = _admin(db_session)
    teacher = _user(
        db_session,
        name="Approve Pending Teacher",
        email="approve-pending@example.test",
        role=UserRole.teacher_pending,
    )

    csrf_token = login_as(client, admin)
    response = client.post(
        f"/admin/teachers/{teacher.id}/approve",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/teachers"


def test_admin_teacher_reject_redirect_still_goes_to_admin_teachers(client, db_session, login_as):
    admin = _admin(db_session)
    teacher = _user(
        db_session,
        name="Reject Pending Teacher",
        email="reject-pending@example.test",
        role=UserRole.teacher_pending,
    )

    csrf_token = login_as(client, admin)
    response = client.post(
        f"/admin/teachers/{teacher.id}/reject",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/teachers"


def test_admin_teacher_remove_from_org_redirect_still_goes_to_admin_teachers(client, db_session, login_as):
    admin = _admin(db_session)
    org = _organization(db_session, name="Remove Teacher Org")
    teacher = _user(
        db_session,
        name="Remove Active Teacher",
        email="remove-active@example.test",
        role=UserRole.teacher,
    )
    _link_teacher(db_session, org=org, teacher=teacher, status="accepted")

    csrf_token = login_as(client, admin)
    response = client.post(
        f"/admin/teachers/{teacher.id}/remove-from-org",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/teachers"

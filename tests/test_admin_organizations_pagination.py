from datetime import datetime, timedelta

import pytest

from app.models.organization import Organization
from app.models.user import User, UserRole


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


def _admin(db_session) -> User:
    return _user(
        db_session,
        name="Admin Organizations",
        email="admin-organizations@example.test",
        role=UserRole.admin,
    )


def _organization(
    db_session,
    *,
    name: str,
    owner: User,
    status: str = "pending",
    phone: str | None = None,
    created_at: datetime,
) -> Organization:
    org = Organization(
        user_id=owner.id,
        name=name,
        status=status,
        phone=phone,
        is_open=True,
        created_at=created_at,
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


def test_admin_organizations_page_one_uses_page_size_and_created_at_sort(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        owner = _user(
            db_session,
            name=f"Owner {index}",
            email=f"owner-{index}@example.test",
            role=UserRole.organization,
        )
        _organization(
            db_session,
            name=f"Org {index}",
            owner=owner,
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    response = client.get("/admin/organizations?page=1&per_page=3")

    assert response.status_code == 200
    body = response.text
    assert "Всего: 6 учебных центров" in body
    assert "Страница 1 из 2" in body
    assert "Org 5" in body
    assert "Org 4" in body
    assert "Org 3" in body
    assert "Org 2" not in body
    assert body.index("Org 5") < body.index("Org 4") < body.index("Org 3")
    assert "per_page=3&amp;page=2" in body


def test_admin_organizations_page_two_does_not_repeat_page_one(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        owner = _user(
            db_session,
            name=f"Owner {index}",
            email=f"owner-two-{index}@example.test",
            role=UserRole.organization,
        )
        _organization(
            db_session,
            name=f"Org {index}",
            owner=owner,
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    page_one = client.get("/admin/organizations?page=1&per_page=3").text
    page_two = client.get("/admin/organizations?page=2&per_page=3").text

    assert "Org 5" in page_one
    assert "Org 4" in page_one
    assert "Org 3" in page_one
    assert "Org 5" not in page_two
    assert "Org 4" not in page_two
    assert "Org 3" not in page_two
    assert "Org 2" in page_two
    assert "Org 1" in page_two
    assert "Org 0" in page_two


def test_admin_organizations_owner_and_status_actions_render(client, db_session, login_as):
    admin = _admin(db_session)
    pending_owner = _user(
        db_session,
        name="Pending Owner",
        email="pending-owner@example.test",
        role=UserRole.organization,
    )
    approved_owner = _user(
        db_session,
        name="Approved Owner",
        email="approved-owner@example.test",
        role=UserRole.organization,
    )
    rejected_owner = _user(
        db_session,
        name="Rejected Owner",
        email="rejected-owner@example.test",
        role=UserRole.organization,
    )
    pending = _organization(
        db_session,
        name="Pending Org",
        owner=pending_owner,
        status="pending",
        phone="+992000000001",
        created_at=datetime(2026, 1, 3),
    )
    approved = _organization(
        db_session,
        name="Approved Org",
        owner=approved_owner,
        status="approved",
        created_at=datetime(2026, 1, 2),
    )
    rejected = _organization(
        db_session,
        name="Rejected Org",
        owner=rejected_owner,
        status="rejected",
        created_at=datetime(2026, 1, 1),
    )

    login_as(client, admin)
    response = client.get("/admin/organizations?page=1&per_page=25")

    assert response.status_code == 200
    body = response.text
    assert "Всего: 3 учебных центров" in body
    assert "Pending Owner" in body
    assert "pending-owner@example.test" in body
    assert "+992000000001" in body
    assert "Одобрена" in body
    assert "Отклонена" in body
    assert "Ожидает" in body
    assert f"/admin/organizations/{pending.id}/approve" in body
    assert f"/admin/organizations/{pending.id}/reject" in body
    assert f"/admin/organizations/{pending.id}/delete" in body
    assert f"/admin/organizations/{approved.id}/approve" not in body
    assert f"/admin/organizations/{approved.id}/reject" in body
    assert f"/admin/organizations/{rejected.id}/approve" in body
    assert f"/admin/organizations/{rejected.id}/reject" not in body


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
def test_admin_organizations_rejects_invalid_pagination_params(client, db_session, login_as, query):
    admin = _admin(db_session)

    login_as(client, admin)
    response = client.get(f"/admin/organizations?{query}")

    assert response.status_code == 422


def test_admin_organization_approve_redirect_still_goes_to_admin_organizations(client, db_session, login_as):
    admin = _admin(db_session)
    owner = _user(
        db_session,
        name="Approve Org Owner",
        email="approve-org-owner@example.test",
        role=UserRole.organization,
    )
    org = _organization(
        db_session,
        name="Approve Org",
        owner=owner,
        status="pending",
        created_at=datetime(2026, 1, 1),
    )

    csrf_token = login_as(client, admin)
    response = client.post(
        f"/admin/organizations/{org.id}/approve",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/organizations"


def test_admin_organization_reject_redirect_still_goes_to_admin_organizations(client, db_session, login_as):
    admin = _admin(db_session)
    owner = _user(
        db_session,
        name="Reject Org Owner",
        email="reject-org-owner@example.test",
        role=UserRole.organization,
    )
    org = _organization(
        db_session,
        name="Reject Org",
        owner=owner,
        status="pending",
        created_at=datetime(2026, 1, 1),
    )

    csrf_token = login_as(client, admin)
    response = client.post(
        f"/admin/organizations/{org.id}/reject",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/organizations"


def test_admin_organization_delete_not_found_redirect_preserves_behavior(client, db_session, login_as):
    admin = _admin(db_session)

    csrf_token = login_as(client, admin)
    response = client.post(
        "/admin/organizations/999/delete",
        headers={"x-csrf-token": csrf_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/admin/organizations?error=not_found"

from datetime import datetime, timedelta

import pytest

from app.models.user import User, UserRole


def _user(db_session, *, name: str, email: str, role: UserRole = UserRole.student, created_at: datetime) -> User:
    user = User(
        name=name,
        email=email,
        password_hash="test-hash",
        role=role,
        is_active=True,
        created_at=created_at,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _admin(db_session) -> User:
    return _user(
        db_session,
        name="Admin User",
        email="admin-users@example.test",
        role=UserRole.admin,
        created_at=datetime(2025, 1, 1),
    )


def test_admin_users_page_one_uses_page_size(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        _user(
            db_session,
            name=f"Student {index}",
            email=f"student-{index}@example.test",
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    response = client.get("/admin/users?page=1&per_page=3")

    assert response.status_code == 200
    body = response.text
    assert "Всего: 7 пользователей" in body
    assert "Страница 1 из 3" in body
    assert "Student 5" in body
    assert "Student 4" in body
    assert "Student 3" in body
    assert "Student 2" not in body
    assert "Student 1" not in body
    assert "Student 0" not in body


def test_admin_users_page_two_does_not_repeat_page_one(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(6):
        _user(
            db_session,
            name=f"Student {index}",
            email=f"student-{index}@example.test",
            created_at=base_time + timedelta(minutes=index),
        )

    login_as(client, admin)
    page_one = client.get("/admin/users?page=1&per_page=3").text
    page_two = client.get("/admin/users?page=2&per_page=3").text

    assert "Student 5" in page_one
    assert "Student 4" in page_one
    assert "Student 3" in page_one
    assert "Student 5" not in page_two
    assert "Student 4" not in page_two
    assert "Student 3" not in page_two
    assert "Student 2" in page_two
    assert "Student 1" in page_two
    assert "Student 0" in page_two


def test_admin_users_search_works_with_pagination_and_metadata(client, db_session, login_as):
    admin = _admin(db_session)
    base_time = datetime(2026, 1, 1)
    for index in range(5):
        _user(
            db_session,
            name=f"Alice {index}",
            email=f"alice-{index}@example.test",
            created_at=base_time + timedelta(minutes=index),
        )
    for index in range(3):
        _user(
            db_session,
            name=f"Bob {index}",
            email=f"bob-{index}@example.test",
            created_at=base_time + timedelta(hours=1, minutes=index),
        )

    login_as(client, admin)
    response = client.get("/admin/users?q=alice&page=2&per_page=2")

    assert response.status_code == 200
    body = response.text
    assert "Всего: 5 пользователей" in body
    assert "Страница 2 из 3" in body
    assert "Alice 2" in body
    assert "Alice 1" in body
    assert "Alice 4" not in body
    assert "Bob 0" not in body
    assert "q=alice&amp;per_page=2&amp;page=3" in body


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
def test_admin_users_rejects_invalid_pagination_params(client, db_session, login_as, query):
    admin = _admin(db_session)

    login_as(client, admin)
    response = client.get(f"/admin/users?{query}")

    assert response.status_code == 422

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.models.organization import Organization, OrganizationTeacher
from app.models.user import User, UserRole
from app.utils.private_uploads import (
    APPLICATION_ATTACHMENTS,
    TEACHER_DOCUMENTS,
    private_upload_destination,
    resolve_private_upload_path,
)


def _user(db_session, *, role: UserRole, email: str, documents: str | None = None) -> User:
    user = User(
        name=email.split("@", 1)[0],
        email=email,
        password_hash="test-hash",
        role=role,
        documents=documents,
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


def test_teacher_document_unauthorized_does_not_return_file(
    client,
    db_session,
    write_private_file,
):
    storage_key = write_private_file(TEACHER_DOCUMENTS, "teacher.pdf", b"private-teacher-doc")
    teacher = _user(
        db_session,
        role=UserRole.teacher_pending,
        email="pending-teacher@example.test",
        documents=storage_key,
    )

    response = client.get(
        f"/admin/teachers/{teacher.id}/document",
        follow_redirects=False,
    )

    assert response.status_code in {302, 403}
    assert response.content != b"private-teacher-doc"


def test_teacher_document_admin_access_returns_file(
    client,
    db_session,
    login_as,
    write_private_file,
):
    admin = _user(db_session, role=UserRole.admin, email="admin-docs@example.test")
    storage_key = write_private_file(TEACHER_DOCUMENTS, "teacher-admin.pdf", b"teacher-doc")
    teacher = _user(
        db_session,
        role=UserRole.teacher_pending,
        email="teacher-docs@example.test",
        documents=storage_key,
    )

    login_as(client, admin)
    response = client.get(f"/admin/teachers/{teacher.id}/document")

    assert response.status_code == 200
    assert response.content == b"teacher-doc"


def test_organization_attachment_authorization(
    client,
    db_session,
    login_as,
    write_private_file,
):
    admin = _user(db_session, role=UserRole.admin, email="admin-attach@example.test")
    owner_user = _user(db_session, role=UserRole.organization, email="owner@example.test")
    non_owner_user = _user(db_session, role=UserRole.organization, email="nonowner@example.test")
    teacher = _user(db_session, role=UserRole.teacher, email="teacher-owner@example.test")

    owning_org = _organization(db_session, owner_user, name="Owning Org")
    _organization(db_session, non_owner_user, name="Other Org")

    storage_key = write_private_file(
        APPLICATION_ATTACHMENTS,
        "application.pdf",
        b"application-attachment",
    )
    application = OrganizationTeacher(
        organization_id=owning_org.id,
        teacher_id=teacher.id,
        status="pending",
        attachment=storage_key,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    url = f"/organization/teacher-applications/{application.id}/attachment"

    login_as(client, admin)
    assert client.get(url).status_code == 200

    login_as(client, owner_user)
    owner_response = client.get(url)
    assert owner_response.status_code == 200
    assert owner_response.content == b"application-attachment"

    login_as(client, teacher)
    assert client.get(url).status_code == 200

    login_as(client, non_owner_user)
    non_owner_response = client.get(url)
    assert non_owner_response.status_code == 403
    assert non_owner_response.content != b"application-attachment"


def test_static_guard_blocks_sensitive_legacy_paths_but_keeps_assets(client):
    blocked_files = [
        Path("static/documents/p0-static-guard.pdf"),
        Path("static/uploads/applications/p0-static-guard.pdf"),
    ]
    for path in blocked_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"blocked")

    try:
        assert client.get("/static/documents/p0-static-guard.pdf").status_code == 404
        assert client.get("/static/uploads/applications/p0-static-guard.pdf").status_code == 404
        assert client.get("/static/css/style.css").status_code == 200
    finally:
        for path in blocked_files:
            path.unlink(missing_ok=True)


def test_private_upload_resolver_rejects_path_traversal(private_upload_dirs):
    with pytest.raises(HTTPException):
        resolve_private_upload_path("../secret.pdf", TEACHER_DOCUMENTS)
    with pytest.raises(HTTPException):
        resolve_private_upload_path("teacher_documents/../secret.pdf", TEACHER_DOCUMENTS)
    with pytest.raises(HTTPException):
        resolve_private_upload_path("/etc/passwd", TEACHER_DOCUMENTS)
    with pytest.raises(HTTPException):
        resolve_private_upload_path(
            "application_attachments/../../secret.pdf",
            APPLICATION_ATTACHMENTS,
        )

    storage_key, destination = private_upload_destination(
        TEACHER_DOCUMENTS,
        "../../../safe-name.pdf",
    )
    assert storage_key == "teacher_documents/safe-name.pdf"
    assert destination.parent == private_upload_dirs["teacher_documents"]

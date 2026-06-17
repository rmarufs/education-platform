import base64
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTO_APPLY_MIGRATIONS", "false")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("CLOUDINARY_CLOUD_NAME", "test-cloud")
os.environ.setdefault("CLOUDINARY_API_KEY", "test-key")
os.environ.setdefault("CLOUDINARY_API_SECRET", "test-secret")

from app.config import SECRET_KEY
from app.database import Base, get_db

import app.models.category  # noqa: F401
import app.models.comment  # noqa: F401
import app.models.contact  # noqa: F401
import app.models.course  # noqa: F401
import app.models.group  # noqa: F401
import app.models.lesson  # noqa: F401
import app.models.material  # noqa: F401
import app.models.module  # noqa: F401
import app.models.organization  # noqa: F401
import app.models.progress  # noqa: F401
import app.models.quiz  # noqa: F401
import app.models.review  # noqa: F401
import app.models.user  # noqa: F401
import app.models.vocabulary  # noqa: F401
import main

app = main.app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def connect(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "num_nonnulls",
            -1,
            lambda *args: sum(value is not None for value in args),
        )

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch):
    def override_get_db():
        yield db_session

    monkeypatch.setattr(main, "_load_request_user", lambda request: None)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _signed_session_cookie(data: dict) -> str:
    payload = base64.b64encode(json.dumps(data).encode("utf-8"))
    return TimestampSigner(str(SECRET_KEY)).sign(payload).decode("utf-8")


@pytest.fixture()
def login_as():
    def _login(client: TestClient, user, *, csrf_token: str | None = None) -> str:
        token = csrf_token or "test-csrf-token"
        client.cookies.clear()
        client.cookies.set(
            "session",
            _signed_session_cookie({"user_id": user.id, "_csrf_token": token}),
        )
        return token

    return _login


@pytest.fixture()
def private_upload_dirs(tmp_path, monkeypatch):
    import app.utils.private_uploads as private_uploads

    private_root = tmp_path / "private_uploads"
    legacy_static = tmp_path / "static"
    private_dirs = {
        private_uploads.TEACHER_DOCUMENTS: private_root / private_uploads.TEACHER_DOCUMENTS,
        private_uploads.APPLICATION_ATTACHMENTS: private_root / private_uploads.APPLICATION_ATTACHMENTS,
    }
    legacy_dirs = {
        private_uploads.TEACHER_DOCUMENTS: legacy_static / "documents",
        private_uploads.APPLICATION_ATTACHMENTS: legacy_static / "uploads" / "applications",
    }

    for directory in [*private_dirs.values(), *legacy_dirs.values()]:
        directory.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(private_uploads, "PRIVATE_UPLOAD_ROOT", private_root)
    monkeypatch.setattr(private_uploads, "_PRIVATE_DIRS", private_dirs)
    monkeypatch.setattr(private_uploads, "_LEGACY_DIRS", legacy_dirs)

    return {
        "private_root": private_root,
        "legacy_static": legacy_static,
        "teacher_documents": private_dirs[private_uploads.TEACHER_DOCUMENTS],
        "application_attachments": private_dirs[private_uploads.APPLICATION_ATTACHMENTS],
    }


@pytest.fixture()
def write_private_file(private_upload_dirs):
    def _write(category: str, filename: str, content: bytes = b"test-file") -> str:
        directory = private_upload_dirs[category]
        path = Path(directory) / filename
        path.write_bytes(content)
        return f"{category}/{filename}"

    return _write

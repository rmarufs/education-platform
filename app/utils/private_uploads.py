from pathlib import Path

from fastapi import HTTPException


PRIVATE_UPLOAD_ROOT = Path("data") / "private_uploads"
TEACHER_DOCUMENTS = "teacher_documents"
APPLICATION_ATTACHMENTS = "application_attachments"

_PRIVATE_DIRS = {
    TEACHER_DOCUMENTS: PRIVATE_UPLOAD_ROOT / TEACHER_DOCUMENTS,
    APPLICATION_ATTACHMENTS: PRIVATE_UPLOAD_ROOT / APPLICATION_ATTACHMENTS,
}

_LEGACY_DIRS = {
    TEACHER_DOCUMENTS: Path("static") / "documents",
    APPLICATION_ATTACHMENTS: Path("static") / "uploads" / "applications",
}

_LEGACY_PREFIXES = {
    TEACHER_DOCUMENTS: ("/static/documents/", "static/documents/"),
    APPLICATION_ATTACHMENTS: (
        "/static/uploads/applications/",
        "static/uploads/applications/",
    ),
}


def private_upload_destination(category: str, filename: str) -> tuple[str, Path]:
    """Return a storage key and filesystem destination for a new private upload."""
    upload_dir = _PRIVATE_DIRS[category]
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(filename.replace("\\", "/")).name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Некорректное имя файла")

    base_resolved = upload_dir.resolve(strict=False)
    destination = (upload_dir / safe_name).resolve(strict=False)
    if not destination.is_relative_to(base_resolved):
        raise HTTPException(status_code=400, detail="Некорректное имя файла")

    storage_key = f"{category}/{safe_name}"
    return storage_key, destination


def resolve_private_upload_path(value: str | None, category: str) -> Path:
    """Resolve a private storage key or legacy static path to a safe local file."""
    if not value:
        raise HTTPException(status_code=404, detail="Файл не найден")

    raw_value = value.strip()
    base_dir = _PRIVATE_DIRS[category]
    relative_value = None

    private_prefix = f"{category}/"
    if raw_value.startswith(private_prefix):
        relative_value = raw_value.removeprefix(private_prefix)
    else:
        for prefix in _LEGACY_PREFIXES[category]:
            if raw_value.startswith(prefix):
                base_dir = _LEGACY_DIRS[category]
                relative_value = raw_value.removeprefix(prefix)
                break

    if relative_value is None:
        raise HTTPException(status_code=404, detail="Файл не найден")

    relative_path = Path(relative_value)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise HTTPException(status_code=404, detail="Файл не найден")

    base_resolved = base_dir.resolve(strict=False)
    file_path = (base_dir / relative_path).resolve(strict=False)
    if not file_path.is_relative_to(base_resolved):
        raise HTTPException(status_code=404, detail="Файл не найден")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return file_path


def delete_private_upload(value: str | None, category: str) -> None:
    try:
        file_path = resolve_private_upload_path(value, category)
    except HTTPException:
        return
    try:
        file_path.unlink()
    except OSError:
        return

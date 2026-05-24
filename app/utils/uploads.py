import os
import re
from dataclasses import dataclass
from typing import Iterable

from fastapi import HTTPException, UploadFile


IMAGE_CONTENT_TYPES = {
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}

DOCUMENT_CONTENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/x-zip-compressed",
    },
    ".ppt": {"application/vnd.ms-powerpoint"},
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
        "application/x-zip-compressed",
    },
    ".txt": {"text/plain"},
}

MEDIA_CONTENT_TYPES = {
    ".mp4": {"video/mp4"},
    ".mov": {"video/quicktime"},
    ".webm": {"video/webm"},
}

UPLOAD_CONTENT_TYPES = {
    **IMAGE_CONTENT_TYPES,
    **DOCUMENT_CONTENT_TYPES,
    **MEDIA_CONTENT_TYPES,
}

GENERIC_BINARY_CONTENT_TYPES = {"application/octet-stream", "binary/octet-stream"}


@dataclass(frozen=True)
class ValidatedUpload:
    original_filename: str
    safe_filename: str
    extension: str
    size: int
    content_type: str


def safe_upload_filename(filename: str) -> str:
    raw_name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    base, ext = os.path.splitext(raw_name)
    ext = ext.lower()
    safe_base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
    if not safe_base:
        safe_base = "file"
    return f"{safe_base[:80]}{ext}"


def _normalize_extensions(extensions: Iterable[str]) -> set[str]:
    normalized = set()
    for ext in extensions:
        clean_ext = ext.lower().strip()
        if not clean_ext:
            continue
        normalized.add(clean_ext if clean_ext.startswith(".") else f".{clean_ext}")
    return normalized


def _upload_size(file: UploadFile) -> int:
    try:
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
    finally:
        file.file.seek(0)
    return size


def _read_file_header(file: UploadFile, length: int = 512) -> bytes:
    try:
        file.file.seek(0)
        return file.file.read(length)
    finally:
        file.file.seek(0)


def _content_matches_extension(file: UploadFile, extension: str) -> bool:
    header = _read_file_header(file)
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if extension == ".pdf":
        return header.startswith(b"%PDF")
    if extension in {".docx", ".pptx"}:
        return header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06") or header.startswith(b"PK\x07\x08")
    if extension in {".doc", ".ppt"}:
        return header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension == ".txt":
        return b"\x00" not in header
    if extension in {".mp4", ".mov"}:
        return b"ftyp" in header[:16]
    if extension == ".webm":
        return header.startswith(b"\x1a\x45\xdf\xa3")
    return False


def validate_upload_file(
    file: UploadFile,
    *,
    allowed_extensions: Iterable[str],
    max_bytes: int,
    missing_message: str = "Файл не выбран",
    invalid_type_message: str = "Недопустимый тип файла",
    too_large_message: str = "Файл слишком большой",
    empty_message: str = "Файл пустой",
) -> ValidatedUpload:
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail=missing_message)

    allowed_exts = _normalize_extensions(allowed_extensions)
    original_filename = file.filename.replace("\\", "/").split("/")[-1].strip()
    extension = os.path.splitext(original_filename)[1].lower()
    if extension not in allowed_exts:
        raise HTTPException(status_code=400, detail=invalid_type_message)

    content_type = (file.content_type or "").split(";", 1)[0].lower().strip()
    allowed_content_types = UPLOAD_CONTENT_TYPES.get(extension, set())
    if content_type not in allowed_content_types:
        if content_type not in GENERIC_BINARY_CONTENT_TYPES or not _content_matches_extension(file, extension):
            raise HTTPException(status_code=400, detail=invalid_type_message)

    if not _content_matches_extension(file, extension):
        raise HTTPException(status_code=400, detail=invalid_type_message)

    size = _upload_size(file)
    if size <= 0:
        raise HTTPException(status_code=400, detail=empty_message)
    if size > max_bytes:
        raise HTTPException(status_code=400, detail=too_large_message)

    return ValidatedUpload(
        original_filename=original_filename,
        safe_filename=safe_upload_filename(original_filename),
        extension=extension,
        size=size,
        content_type=content_type,
    )

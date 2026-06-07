"""Upload service for handling file uploads and Cloudinary operations."""

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.utils.image import compress_and_upload_avatar
from app.utils.uploads import validate_upload_file

AVATAR_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
AVATAR_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


async def upload_user_avatar(file: UploadFile, user: User, db: Session) -> str:
    """Validate, compress, and upload user avatar to Cloudinary, then update DB."""
    validate_upload_file(
        file,
        allowed_extensions=AVATAR_ALLOWED_EXTS,
        max_bytes=AVATAR_MAX_BYTES,
        invalid_type_message="Разрешены только JPG, JPEG, PNG и WEBP",
        too_large_message="Файл не должен превышать 10 МБ",
    )

    file_bytes = await file.read()

    avatar_url = compress_and_upload_avatar(file_bytes, user.id)

    user.avatar_url = avatar_url
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if org:
            org.logo_url = avatar_url
    db.commit()

    return avatar_url


def delete_user_avatar(user: User, db: Session) -> None:
    """Delete user avatar from Cloudinary and clear it in DB."""
    try:
        import cloudinary.uploader as _uploader
        _uploader.destroy(f"avatars/user_{user.id}", invalidate=True, resource_type="image")
    except Exception:
        pass  # Не блокируем удаление из БД, если Cloudinary недоступен

    user.avatar_url = None
    if user.is_org:
        org = db.query(Organization).filter(Organization.user_id == user.id).first()
        if org:
            org.logo_url = None
    db.commit()

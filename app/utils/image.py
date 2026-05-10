"""Утилита для сжатия и загрузки аватаров пользователей в Cloudinary."""
from PIL import Image
import io
import cloudinary.uploader


def compress_and_upload_avatar(file_bytes: bytes, user_id: int) -> str:
    """
    Сжимает изображение до 400x400 квадрата, оптимизирует до ≤100KB и загружает в Cloudinary.
    Возвращает secure_url загруженного аватара.
    """
    img = Image.open(io.BytesIO(file_bytes))

    # Конвертация RGBA / палитровых изображений в RGB
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Кроп по центру в квадрат
    width, height = img.size
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    img = img.crop((left, top, left + size, top + size))

    # Масштабирование до 400x400
    img = img.resize((400, 400), Image.LANCZOS)

    # Сжатие до ≤100KB
    output = io.BytesIO()
    quality = 85
    while quality > 10:
        output.seek(0)
        output.truncate()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        if output.tell() <= 100 * 1024:
            break
        quality -= 10

    output.seek(0)

    result = cloudinary.uploader.upload(
        output,
        public_id=f"avatars/user_{user_id}",
        overwrite=True,
        resource_type="image",
    )
    return result["secure_url"]

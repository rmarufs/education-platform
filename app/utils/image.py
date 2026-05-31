"""Утилита для сжатия и загрузки изображений в Cloudinary."""
from PIL import Image, ImageOps
import io

try:
    import cloudinary.uploader
except ModuleNotFoundError:
    cloudinary = None


def compress_and_upload_avatar(file_bytes, user_id: int = None, public_id: str = None) -> str:
    """
    Сжимает изображение до 400x400 квадрата, оптимизирует до ≤100KB и загружает в Cloudinary.
    Возвращает secure_url загруженного аватара.
    """
    if not cloudinary:
        raise RuntimeError("Cloudinary недоступен для загрузки аватара")
    if hasattr(file_bytes, "read"):
        file_bytes = file_bytes.read()
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

    pid = public_id or f"avatars/user_{user_id}"
    result = cloudinary.uploader.upload(
        output,
        public_id=pid,
        overwrite=True,
        resource_type="image",
    )
    return result["secure_url"]


def upload_group_cover_image(file_bytes, public_id: str) -> str:
    """
    Загружает обложку группы без crop, сохраняя исходные пропорции.
    Большие изображения уменьшаются до разумного размера, маленькие не увеличиваются.
    """
    if not cloudinary:
        raise RuntimeError("Cloudinary недоступен для загрузки обложки группы")
    if hasattr(file_bytes, "read"):
        file_bytes = file_bytes.read()

    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)
    img.thumbnail((1280, 900), Image.LANCZOS)

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=86, optimize=True)
    output.seek(0)

    result = cloudinary.uploader.upload(
        output,
        public_id=public_id,
        overwrite=True,
        resource_type="image",
    )
    return result["secure_url"]


def upload_lesson_image(file_bytes, public_id: str) -> str:
    """
    Загружает основную картинку урока в Cloudinary без crop/resize,
    чтобы сохранить исходный формат и соотношение сторон.
    """
    if not cloudinary:
        raise RuntimeError("Cloudinary недоступен для загрузки изображения урока")
    if hasattr(file_bytes, "seek"):
        file_bytes.seek(0)
    result = cloudinary.uploader.upload(
        file_bytes,
        public_id=public_id,
        overwrite=True,
        resource_type="image",
    )
    return result["secure_url"]

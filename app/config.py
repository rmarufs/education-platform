# Конфигурация приложения
import os
from dotenv import load_dotenv

# Загружаем переменные из .env (если файл существует)
load_dotenv()

# ── Обязательные переменные окружения ──────────────────────────────────────

def _get_required_env(key: str, description: str = "") -> str:
    """Получить обязательную переменную окружения или выбросить ошибку."""
    value = os.getenv(key)
    if not value:
        desc_msg = f" ({description})" if description else ""
        raise RuntimeError(
            f"❌ КРИТИЧЕСКАЯ ОШИБКА: Переменная окружения '{key}' не установлена{desc_msg}.\n"
            f"Установите её в .env файле или передайте через переменные окружения."
        )
    return value

# Секретный ключ для подписи cookie-сессий (ОБЯЗАТЕЛЕН)
SECRET_KEY = _get_required_env("SECRET_KEY", "используется для подписи сессии cookies")

# URL подключения к базе данных (ОБЯЗАТЕЛЕН)
DATABASE_URL = _get_required_env("DATABASE_URL", "PostgreSQL connection string")

# Cloudinary API (ОБЯЗАТЕЛЕН для хостинга изображений)
CLOUDINARY_CLOUD_NAME = _get_required_env("CLOUDINARY_CLOUD_NAME", "имя облака Cloudinary")
CLOUDINARY_API_KEY = _get_required_env("CLOUDINARY_API_KEY", "API ключ Cloudinary")
CLOUDINARY_API_SECRET = _get_required_env("CLOUDINARY_API_SECRET", "API секрет Cloudinary")

# Названиеплатформы
PLATFORM_NAME = os.getenv("PLATFORM_NAME", "Фурузон")

# Время жизни сессии (в секундах)
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", 60 * 60 * 24 * 7))  # По умолчанию 7 дней

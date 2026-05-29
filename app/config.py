# Конфигурация приложения
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env
# Сначала пытаемся загрузить из config/.env, потом из корня проекта
env_path = Path(__file__).parent.parent / "config" / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

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

# Настройки Web Push Notifications
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS_SUB = os.getenv("VAPID_CLAIMS_SUB", "mailto:admin@example.com")

def _get_bool_env(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
IS_PRODUCTION = APP_ENV not in {"development", "dev", "local", "test"}

# Production defaults are intentionally conservative. Development can keep
# convenience behavior through config/.env without changing application code.
ENABLE_API_DOCS = _get_bool_env("ENABLE_API_DOCS", not IS_PRODUCTION)
AUTO_APPLY_MIGRATIONS = _get_bool_env("AUTO_APPLY_MIGRATIONS", not IS_PRODUCTION)

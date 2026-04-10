# Конфигурация приложения
import os
from dotenv import load_dotenv

# Загружаем переменные из .env (если файл существует)
load_dotenv()

# Секретный ключ для подписи cookie-сессий (из .env или дефолтный для разработки)
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")

# URL подключения к базе данных (PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost/education_db")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dyjgc9lc5")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "988373662391686")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

# Название платформы
PLATFORM_NAME = "Фурузон"

# Время жизни сессии (в секундах)
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 дней

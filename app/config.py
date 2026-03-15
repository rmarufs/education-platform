# Конфигурация приложения
import os
from dotenv import load_dotenv

# Загружаем переменные из .env (если файл существует)
load_dotenv()

# Секретный ключ для подписи cookie-сессий (из .env или дефолтный для разработки)
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")

# Путь к базе данных SQLite
DATABASE_URL = "sqlite:///./data/database.db"

# Название платформы
PLATFORM_NAME = "EduHub"

# Время жизни сессии (в секундах)
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 дней

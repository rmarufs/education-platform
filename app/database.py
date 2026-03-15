# Настройка базы данных SQLAlchemy + SQLite
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

# Создаём движок SQLite
# check_same_thread=False нужен для SQLite при использовании с FastAPI
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Фабрика сессий БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Базовый класс для всех моделей
class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency для получения сессии базы данных в роутерах."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Создаёт все таблицы в базе данных при старте приложения."""
    from app.models import user, course, category  # noqa
    from app.models import module, lesson, material  # noqa
    from app.models import quiz, progress, review, comment  # noqa
    Base.metadata.create_all(bind=engine)


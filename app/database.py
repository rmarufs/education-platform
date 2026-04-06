# Настройка базы данных SQLAlchemy + PostgreSQL
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

# Создаём движок PostgreSQL
engine = create_engine(DATABASE_URL)

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


def _migrate_enum_and_columns():
    """Добавляет новые значения enum и столбцы, если их ещё нет."""
    with engine.connect() as conn:
        # 1. Добавляем новые значения в enum-тип userrole
        for val in ("teacher_pending", "admin"):
            try:
                conn.execute(text(
                    f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{val}'"
                ))
                conn.commit()
            except Exception:
                conn.rollback()

        # 2. Добавляем столбец documents, если его нет
        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS documents VARCHAR(500)"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # 3. Добавляем столбец is_active, если его нет
        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # 4. Добавляем столбец bio, если его нет
        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT"
            ))
            conn.commit()
        except Exception:
            conn.rollback()


def init_db():
    """Создаёт все таблицы в базе данных при старте приложения."""
    from app.models import user, course, category  # noqa
    from app.models import module, lesson, material  # noqa
    from app.models import quiz, progress, review, comment  # noqa
    from app.models import contact  # noqa
    Base.metadata.create_all(bind=engine)

    # Миграция: добавить новые роли и столбцы
    _migrate_enum_and_columns()

# Настройка базы данных SQLAlchemy + PostgreSQL
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

# Создаём движок PostgreSQL с оптимизированным пулом соединений
engine = create_engine(
    DATABASE_URL,
    # Пул соединений: оптимизировано для Render и малых инстансов
    pool_size=5,              # Базовое количество соединений в пуле
    max_overflow=10,          # Максимум дополнительных соединений сверх pool_size
    pool_pre_ping=True,       # Проверять соединение перед использованием (исправляет stale connections)
    pool_recycle=3600,        # Переиспользовать соединение каждый час (PostgreSQL по умолчанию таймаут 1ч)
    echo=False,               # Не логировать SQL запросы (вкл. в разработке при отладке)
    connect_args={
        "connect_timeout": 10,
        "application_name": "education_platform",
    }
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





def _create_performance_indexes():
    """Создаёт индексы для оптимизации поиска и фильтрации."""
    with engine.connect() as conn:
        # Индексы для быстрого поиска по названиям
        indexes_to_create = [
            ("idx_courses_title", "courses", "title"),
            ("idx_lessons_title", "lessons", "title"),
            ("idx_modules_title", "modules", "title"),
            ("idx_categories_name", "categories", "name"),
            # Индексы для внешних ключей (улучшают JOIN)
            ("idx_courses_category_id", "courses", "category_id"),
            ("idx_courses_teacher_id", "courses", "teacher_id"),
            ("idx_modules_course_id", "modules", "course_id"),
            ("idx_lessons_module_id", "lessons", "module_id"),
            ("idx_materials_lesson_id", "materials", "lesson_id"),
            ("idx_progress_student_id", "progress", "student_id"),
            ("idx_progress_lesson_id", "progress", "lesson_id"),
            ("idx_reviews_student_id", "reviews", "student_id"),
            ("idx_comments_lesson_id", "comments", "lesson_id"),
        ]
        
        for index_name, table_name, column_name in indexes_to_create:
            try:
                conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})"
                ))
                conn.commit()
            except Exception as e:
                conn.rollback()
                # Индекс может уже существовать, что нормально


def init_db():
    """Создаёт индексы для базы данных при старте приложения."""
    
    # Оптимизация: создать индексы для быстрого поиска
    _create_performance_indexes()

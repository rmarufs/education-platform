# Настройка базы данных SQLAlchemy + PostgreSQL
from sqlalchemy import create_engine, text, inspect
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
        inspector = inspect(engine)

        # 1. Добавляем новые значения в enum-тип userrole
        if engine.dialect.name == "postgresql":
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

        # 5. Добавляем описание модуля, если его нет
        try:
            conn.execute(text(
                "ALTER TABLE modules ADD COLUMN IF NOT EXISTS description TEXT"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # 6. Добавляем обложку курса, если её нет
        try:
            conn.execute(text(
                "ALTER TABLE courses ADD COLUMN IF NOT EXISTS image VARCHAR(500)"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        question_columns = {column["name"] for column in inspector.get_columns("questions")}
        if "correct_text" not in question_columns:
            try:
                conn.execute(text(
                    "ALTER TABLE questions ADD COLUMN correct_text VARCHAR(500)"
                ))
                conn.commit()
            except Exception:
                conn.rollback()

        quiz_columns = {column["name"] for column in inspector.get_columns("quizzes")}
        lesson_column = next((column for column in inspector.get_columns("quizzes") if column["name"] == "lesson_id"), None)
        needs_quiz_rebuild = (
            engine.dialect.name == "sqlite"
            and (
                "module_id" not in quiz_columns
                or "course_id" not in quiz_columns
                or "save_results" not in quiz_columns
                or (lesson_column and not lesson_column.get("nullable", True))
            )
        )

        if needs_quiz_rebuild:
            try:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                conn.execute(text("""
                    CREATE TABLE quizzes_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        lesson_id INTEGER,
                        module_id INTEGER,
                        course_id INTEGER,
                        title VARCHAR(200) NOT NULL,
                        save_results BOOLEAN NOT NULL DEFAULT 1,
                        FOREIGN KEY(lesson_id) REFERENCES lessons (id) ON DELETE CASCADE,
                        FOREIGN KEY(module_id) REFERENCES modules (id) ON DELETE CASCADE,
                        FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
                    )
                """))
                conn.execute(text("""
                    INSERT INTO quizzes_new (id, lesson_id, module_id, course_id, title, save_results)
                    SELECT id, lesson_id, NULL, NULL, title, 1
                    FROM quizzes
                """))
                conn.execute(text("DROP TABLE quizzes"))
                conn.execute(text("ALTER TABLE quizzes_new RENAME TO quizzes"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_quizzes_id ON quizzes (id)"))
                conn.execute(text("PRAGMA foreign_keys=ON"))
                conn.commit()
            except Exception:
                conn.rollback()
                try:
                    conn.execute(text("PRAGMA foreign_keys=ON"))
                except Exception:
                    conn.rollback()
        else:
            if "module_id" not in quiz_columns:
                try:
                    conn.execute(text(
                        "ALTER TABLE quizzes ADD COLUMN module_id INTEGER REFERENCES modules(id) ON DELETE CASCADE"
                    ))
                    conn.commit()
                except Exception:
                    conn.rollback()

            if "course_id" not in quiz_columns:
                try:
                    conn.execute(text(
                        "ALTER TABLE quizzes ADD COLUMN course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE"
                    ))
                    conn.commit()
                except Exception:
                    conn.rollback()

            if "save_results" not in quiz_columns:
                try:
                    if engine.dialect.name == "sqlite":
                        conn.execute(text(
                            "ALTER TABLE quizzes ADD COLUMN save_results BOOLEAN NOT NULL DEFAULT 1"
                        ))
                    else:
                        conn.execute(text(
                            "ALTER TABLE quizzes ADD COLUMN save_results BOOLEAN NOT NULL DEFAULT TRUE"
                        ))
                    conn.commit()
                except Exception:
                    conn.rollback()

            if engine.dialect.name == "postgresql" and lesson_column and not lesson_column.get("nullable", True):
                try:
                    conn.execute(text(
                        "ALTER TABLE quizzes ALTER COLUMN lesson_id DROP NOT NULL"
                    ))
                    conn.commit()
                except Exception:
                    conn.rollback()

        table_names = set(inspector.get_table_names())
        if "quiz_results" in table_names and "quiz_attempts" in table_names:
            try:
                conn.execute(text("""
                    INSERT INTO quiz_results (student_id, quiz_id, score, total, percentage, passed, created_at)
                    SELECT qa.student_id,
                           qa.quiz_id,
                           qa.correct,
                           qa.total,
                           qa.score,
                           CASE WHEN qa.score > :pass_threshold THEN TRUE ELSE FALSE END,
                           qa.completed_at
                    FROM quiz_attempts qa
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM quiz_results qr
                        WHERE qr.student_id = qa.student_id
                          AND qr.quiz_id = qa.quiz_id
                          AND qr.created_at = qa.completed_at
                    )
                """), {"pass_threshold": 80})
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

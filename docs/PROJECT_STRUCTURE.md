# 📐 Структура проекта - Детальное описание

## 🎯 Архитектура на высоком уровне

```
┌─────────────────────────────────────────────────────────┐
│            Frontend (HTML/CSS/JavaScript)               │
│         /templates и /static/js/css                     │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP
┌─────────────────────▼────────────────────────────────────┐
│             FastAPI Application (main.py)               │
│         Маршрутизация, валидация, бизнес-логика         │
└────────────┬───────────────────┬───────────────────┬─────┘
             │                   │                   │
    ┌────────▼────────┐ ┌────────▼────────┐ ┌──────▼──────┐
    │   SQLAlchemy    │ │   Supabase      │ │  Cloudinary │
    │   ORM           │ │   Storage       │ │  CDN        │
    │                 │ │   (Видео)       │ │  (Изображен)│
    │  PostgreSQL     │ │   RLS Policies  │ │             │
    │  Database       │ │                 │ │             │
    └─────────────────┘ └─────────────────┘ └─────────────┘
```

---

## 📁 Подробное описание каждой папки

### `/app/` - Ядро приложения

#### `/app/models/`
**ORM модели (SQLAlchemy)**

```
user.py            → User (профили, аутентификация)
course.py          → Course (курсы, описание, статус)
module.py          → Module (модули внутри курса)
lesson.py          → Lesson (уроки с видео)
category.py        → Category (категории курсов)
quiz.py            → Quiz, QuizQuestion, QuizAnswer (квизы)
comment.py         → Comment (комментарии на уроках)
review.py          → Review (отзывы о курсах)
progress.py        → Progress (отслеживание прогресса)
material.py        → Material (учебные материалы)
contact.py         → Contact (сообщения с формы контактов)
```

**Особенности:**
- ✅ Relationships (связи между моделями)
- ✅ Timestamps (created_at, updated_at)
- ✅ Status fields (draft, published, archived)

---

#### `/app/routers/` - API Endpoints

```
auth.py           → POST /api/auth/register, /api/auth/login
users.py          → GET/PUT /api/users/profile
courses.py        → GET /api/courses, POST /api/courses (админ)
lessons.py        → GET /api/lessons/{id}
modules.py        → GET /api/modules/{id}
videos.py         → POST /api/videos/upload, GET /api/videos/stream ⭐ НОВОЕ
quizzes.py        → GET /api/quizzes/{id}, POST /api/quizzes/answer
comments.py       → POST /api/comments, GET /api/comments/{lesson_id}
reviews.py        → POST /api/reviews, GET /api/reviews/{course_id}
profile.py        → GET/PUT /api/profile
pages.py          → GET /pages/about, /pages/contact
admin.py          → Админ-панель, управление контентом
```

**Паттерны:**
- 🔐 Проверка прав доступа (permissions)
- 📄 Pydantic schemas для валидации
- ⚙️ Dependency injection (get_db, get_current_user)

---

#### Основные файлы `/app/`

| Файл | Назначение |
|------|-----------|
| `config.py` | Переменные окружения, конфиг Supabase |
| `database.py` | Подключение к БД, session management |
| `dependencies.py` | Shared dependencies для маршрутов |
| `video_service.py` | Работа с Supabase Storage для видео ⭐ |
| `quiz_flow.py` | Логика проведения квизов |
| `init_video_tables.py` | Автоматическая миграция при старте |

---

### `/templates/` - HTML шаблоны Jinja2

```
base.html                    → Базовый шаблон (navbar, footer)
index.html                   → Главная страница
login.html / register.html   → Аутентификация
dashboard_student.html       → Личный кабинет студента
dashboard_teacher.html       → Личный кабинет преподавателя
course_page.html             → Просмотр курса
lesson_page.html             → Видеоурок + комментарии
quiz_page.html               → Квиз
profile.html                 → Профиль пользователя
create_quiz.html             → Создание квиза
course_manage.html           → Управление курсом (учитель)
teacher_quiz_results.html    → Результаты квизов

/admin/
├── base_admin.html          → Админ-панель базовый шаблон
├── users.html               → Управление пользователями
├── teachers.html            → Управление преподавателями
├── courses.html             → Управление курсами
└── index.html               → Админ главная

/errors/
├── 403.html                 → Доступ запрещен
├── 404.html                 → Не найдено
└── 500.html                 → Ошибка сервера
```

---

### `/static/` - Статические файлы

```
/css/
  admin.css          → Стили админ-панели
  style.css          → Основные стили
  video_upload.css   → Стили для загрузки видео

/js/
  auth.js            → Логика аутентификации
  courses.js         → Управление курсами
  quiz_builder.js    → Построитель квизов
  video_upload.js    → Upload видео в Supabase
  video_playback.js  → Плеер видео ⭐
  main.js            → Основной JS
  i18n.js            → Интернационализация
  richtext.js        → WYSIWYG редактор

/images/             → PNG, SVG иконки

/uploads/
  /courses/          → Изображения курсов
  /materials/        → Материалы курсов
  /videos/           → Видео (загруженные)

/documents/          → Скачиваемые документы
```

---

### `/docs/` - 📚 Документация

```
QUICKSTART_VIDEO.md              → Быстрый старт за 5 мин
VIDEO_INTEGRATION.md             → Полная техническая документация
DEPLOYMENT_CHECKLIST.md          → Функциональное тестирование
VIDEO_IMPLEMENTATION_SUMMARY.md  → История изменений

/optimization/
  OPTIMIZATION_REPORT.md         → Отчёт о производительности
  IMPLEMENTATION_GUIDE.md        → Гайд по внедрению
  CODE_CHANGES_REFERENCE.md      → Справка по изменениям
  README_OPTIMIZATIONS.md        → Введение в оптимизации
```

---

### `/scripts/` - 🔧 Утилиты

```
setup_video_bucket.py    → Инициализация Supabase Storage
manage_rls.py            → Управление RLS политиками
```

**Как добавить новый скрипт:**

```python
#!/usr/bin/env python3
"""
Краткое описание скрипта.

Использование:
    python scripts/my_script.py [args]

Требования:
    - config/.env с необходимыми переменными
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# Загруженяем переменные окружения
env_path = Path(__file__).parent.parent / "config" / ".env"
load_dotenv(env_path)

# Ваш код
if __name__ == "__main__":
    main()
```

---

### `/migrations/` - Миграции БД

```
001_add_video_filename.sql      → Добавление поля video_filename в Lesson
```

**Структура миграции:**
```sql
-- Миграция: Добавление видео-поддержки
-- Версия: 001
-- Дата: YYYY-MM-DD

ALTER TABLE lesson ADD COLUMN video_filename VARCHAR(255);
ALTER TABLE lesson ADD COLUMN video_url TEXT;
```

---

### `/config/` - ⚙️ Конфигурация

```
.env.example         → Пример всех переменных окружения
.env.production      → Production конфиг (НЕ в git!)
```

**Переменные окружения:**
```env
# БД
DATABASE_URL=postgresql://...

# Supabase
SUPABASE_URL=...
SUPABASE_KEY=...

# Security
SECRET_KEY=...

# Cloudinary
CLOUDINARY_CLOUD_NAME=...

# Приложение
DEBUG=False
PLATFORM_NAME=Education Platform
```

---

### `/data/` - 💾 Данные и логи

```
/logs/               → Логи приложения
  server.log
  access.log
  errors.log

/backups/            → Резервные копии БД
  backup_2026-04-26.sql
  backup_2026-04-25.sql

education_platform.db → SQLite БД (разработка только!)
```

---

### `/tests/` - ✅ Тесты

```
/unit/               → Unit тесты
  test_models.py
  test_video_service.py
  test_auth.py

/integration/        → Integration тесты
  test_api_endpoints.py
  test_video_upload.py

/fixtures/           → Фикстуры для тестов
  users.json
  courses.json
```

**Структура теста:**
```python
import pytest
from app.models import User
from app.routers import auth

class TestUserAuthentication:
    def test_user_registration(self, client):
        """Тест регистрации пользователя"""
        response = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "secure123"
        })
        assert response.status_code == 201
```

---

## 🔄 Поток данных для видео

```
1. User загружает видео
   ↓
2. frontend отправляет на /api/videos/upload
   ↓
3. video_service.py:
   - Загружает в Supabase Storage
   - Возвращает video_filename
   ↓
4. Сохраняем в БД: lesson.video_filename
   ↓
5. Чтение видео:
   - /api/videos/stream?filename=...
   - Проверяем permissions
   - Возвращаем Supabase URL
   ↓
6. frontend использует video_playback.js
   для проигрывания с DRM/RLS защитой
```

---

## 📊 Модель данных (упрощённая ERD)

```
┌─────────────────┐
│      User       │
├─────────────────┤
│ id (PK)         │
│ email           │
│ password_hash   │
│ full_name       │
│ role            │
└────────┬────────┘
         │ 1:N
         │
    ┌────▼──────────┐
    │     Course     │
    ├────────────────┤
    │ id (PK)        │
    │ title          │
    │ instructor_id  │ ──→ User
    │ category_id    │ ──→ Category
    │ status         │
    └────┬───────────┘
         │ 1:N
         │
    ┌────▼──────────┐
    │     Module     │
    ├────────────────┤
    │ id (PK)        │
    │ course_id      │ ──→ Course
    │ order          │
    └────┬───────────┘
         │ 1:N
         │
    ┌────▼──────────┐
    │     Lesson     │
    ├────────────────┤
    │ id (PK)        │
    │ module_id      │ ──→ Module
    │ title          │
    │ video_filename │ ⭐
    └────────────────┘
```

---

## 🚀 Разработка нового функционала

### Добавление нового API Endpoint

1. **Создать модель** (если нужна):
```python
# app/models/new_model.py
from sqlalchemy import Column, String, Integer
from app.database import Base

class NewModel(Base):
    __tablename__ = "new_models"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
```

2. **Создать router**:
```python
# app/routers/new_feature.py
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/new-feature", tags=["new-feature"])

@router.get("/items")
async def get_items(current_user = Depends(get_current_user)):
    """Получить список элементов"""
    return {"items": []}
```

3. **Зарегистрировать router в main.py**:
```python
from app.routers import new_feature
app.include_router(new_feature.router)
```

4. **Добавить миграцию БД** (если нужна):
```sql
-- migrations/NNN_create_new_model.sql
CREATE TABLE new_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 📋 Чеклист перед коммитом

- [ ] Код следует PEP8 (flake8, black)
- [ ] Добавлены типы (type hints)
- [ ] Написаны unit тесты
- [ ] Обновлена документация
- [ ] Нет hardcoded значений (используйте .env)
- [ ] Error handling реализован
- [ ] CORS и безопасность проверены

---

**Версия документа:** 2.0  
**Дата:** 26 апреля 2026 г.

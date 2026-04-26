# 🎯 Быстрый старт для новых разработчиков

Добро пожаловать в образовательную платформу! Этот документ поможет вам быстро начать разработку.

## ⏱️ За 5 минут до кода

### Шаг 1️⃣ - Клонируем и подготавливаем окружение (2 мин)

```bash
# Клонируем проект
git clone <repository-url>
cd education_platform

# Создаём и активируем виртуальное окружение
python -m venv venv
source venv/bin/activate  # macOS/Linux

# Устанавливаем зависимости
pip install -r requirements.txt
```

### Шаг 2️⃣ - Конфигурируем приложение (2 мин)

```bash
# Копируем пример окружения
cp config/.env.example config/.env

# Открываем и заполняем config/.env
nano config/.env
# Минимум необходимо заполнить:
# - SUPABASE_URL
# - SUPABASE_KEY
# - SECRET_KEY
```

### Шаг 3️⃣ - Запускаем приложение (1 мин)

```bash
# Запускаем развёртывание
python main.py

# Открываем в браузере
# http://localhost:8000
```

✅ **Готово!** Приложение работает локально.

---

## 📂 Понимаем структуру проекта

**Вот что где находится:**

```
education_platform/
├── main.py               ← ⭐ ЗДЕСЬ запускается приложение
├── app/                  ← Основной код
│   ├── models/           ← ORM модели БД
│   └── routers/          ← API endpoints
├── templates/            ← HTML страницы
├── static/               ← CSS, JS, изображения
├── docs/                 ← 📚 Полная документация
├── scripts/              ← 🔧 Утилиты
├── config/               ← ⚙️ Конфигурация (.env)
└── data/                 ← 💾 Логи и резервные копии
```

**Полное описание:** [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

---

## 🔧 Основные команды

### Запуск приложения

```bash
# Разработка (с auto-reload)
python main.py

# Production (через Gunicorn)
gunicorn -w 4 main:app
```

### Работа с БД

```bash
# Создание миграции
# (если используется Alembic)
# alembic revision --autogenerate -m "description"

# Применение миграций
# alembic upgrade head
```

### Тестирование

```bash
# Запустить все тесты
pytest

# С покрытием
pytest --cov=app

# Только одну папку
pytest tests/unit
```

### Форматирование кода

```bash
# Автоматическое форматирование
black app/

# Проверка стиля
flake8 app/
```

---

## 🚀 Первый код - Добавляем API Endpoint

### Задача: Создать API для получения списка курсов

#### 1️⃣ Проверяем модель (app/models/course.py)

```python
class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    # ... остальные поля
```

#### 2️⃣ Создаём/обновляем router (app/routers/courses.py)

```python
from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.models.course import Course

router = APIRouter(prefix="/api/courses", tags=["courses"])

@router.get("/")
async def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db = Depends(get_db)
):
    """Получить список курсов"""
    courses = db.query(Course).offset(skip).limit(limit).all()
    return {"total": len(courses), "courses": courses}
```

#### 3️⃣ Регистрируем router в main.py

```python
from app.routers import courses

app.include_router(courses.router)
```

#### 4️⃣ Тестируем

```bash
# Запускаем приложение
python main.py

# В другом терминале
curl http://localhost:8000/api/courses/

# Или открываем
# http://localhost:8000/docs  ← интерактивная документация!
```

✅ **Готово!** Ваш API работает.

---

## 📖 Основные концепции

### Models (Модели)
Определяют структуру таблиц в БД.

```python
# app/models/user.py
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
```

### Routers (Маршруты)
API endpoints и бизнес-логика.

```python
# app/routers/auth.py
@router.post("/register")
async def register(email: str, password: str, db = Depends(get_db)):
    # Логика регистрации
    pass
```

### Templates (Шаблоны)
HTML страницы с Jinja2.

```html
<!-- templates/course_page.html -->
{% extends "base.html" %}
{% block content %}
    <h1>{{ course.title }}</h1>
    <p>{{ course.description }}</p>
{% endblock %}
```

### Services (Сервисы)
Сложная бизнес-логика в отдельных файлах.

```python
# app/video_service.py
class VideoService:
    def upload_to_supabase(self, file):
        # Логика загрузки
        pass
```

---

## 🎬 Видео интеграция (быстрый обзор)

Платформа поддерживает видео через Supabase Storage!

**Как загружается видео:**

```
1. Студент загружает видео на форму
   ↓
2. JavaScript (video_upload.js) отправляет на /api/videos/upload
   ↓
3. Backend (video_service.py) загружает в Supabase
   ↓
4. Сохраняет video_filename в БД
   ↓
5. При просмотре используется video_playback.js с защитой
```

**Полная документация:** [VIDEO_INTEGRATION.md](VIDEO_INTEGRATION.md)

---

## 🐛 Решение проблем

### ❌ "Module 'app' not found"
**Решение:**
```bash
# Убедитесь, что находитесь в папке проекта
cd /path/to/education_platform

# Убедитесь, что venv активирован
source venv/bin/activate
```

### ❌ "Database connection failed"
**Решение:**
```bash
# Проверьте config/.env
cat config/.env

# Проверьте подключение к PostgreSQL
psql -h localhost -U your_user -d your_db
```

### ❌ "Supabase API error"
**Решение:**
```bash
# Проверьте SUPABASE_URL и SUPABASE_KEY в config/.env
# Посмотрите логи
tail -f data/logs/error.log
```

---

## 📚 Полезная документация

| Документ | Для кого | Время |
|----------|----------|--------|
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Понимание структуры | 10 мин |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Как делать вклады | 15 мин |
| [VIDEO_INTEGRATION.md](VIDEO_INTEGRATION.md) | Работа с видео | 20 мин |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production развёртывание | 30 мин |
| [docs/](../) | Все документы | ∞ |

---

## 🎯 Чек-лист нового разработчика

- [ ] Клонировал репозиторий
- [ ] Создал виртуальное окружение
- [ ] Установил зависимости (`pip install -r requirements.txt`)
- [ ] Заполнил `config/.env`
- [ ] Запустил приложение (`python main.py`)
- [ ] Открыл http://localhost:8000 в браузере
- [ ] Попробовал интерактивную документацию (http://localhost:8000/docs)
- [ ] Прочитал PROJECT_STRUCTURE.md
- [ ] Создал feature branch (`git checkout -b feature/my-feature`)
- [ ] Понимаю основы FastAPI, SQLAlchemy и Jinja2

---

## 💡 Советы для быстрого старта

### 1. Используйте Swagger UI
```
http://localhost:8000/docs
```
Интерактивная документация всех API endpoints! Можно тестировать прямо отсюда.

### 2. Смотрите примеры в существующем коде
Наши роутеры уже имеют много примеров. Следуйте тому же паттерну.

### 3. Используйте type hints
```python
# ✅ Хорошо
def get_user(user_id: int) -> Optional[User]:
    pass

# ❌ Плохо
def get_user(user_id):
    pass
```

### 4. Пишите docstrings
```python
def upload_video(file: UploadFile) -> dict:
    """
    Загружает видео в Supabase Storage.
    
    Args:
        file: Видео файл
    
    Returns:
        dict: {"filename": "...", "url": "..."}
    """
    pass
```

### 5. Читайте логи
```bash
tail -f data/logs/error.log
```

---

## 🤝 Нужна помощь?

1. **Прочитайте документацию** - большинство вопросов там
2. **Посмотрите существующий код** - есть примеры для всего
3. **Создайте Issue** - напишите подробно о проблеме
4. **Спросите в Discussion** - сообщество поможет

---

## 🚀 Следующие шаги

Когда будете готовы:

1. **Создайте feature branch:** `git checkout -b feature/your-feature`
2. **Добавьте код** и **тесты**
3. **Отправьте PR** с описанием

→ **Подробнее:** [CONTRIBUTING.md](CONTRIBUTING.md)

---

**Добро пожаловать в команду! 🎓**

*Последнее обновление: 26 апреля 2026 г.*

# 🎓 Образовательная Платформа

Современная веб-платформа для онлайн-обучения с поддержкой курсов, видео, квизов и отслеживанием прогресса студентов.

## 📋 Содержание

- [Быстрый старт](#быстрый-старт)
- [Структура проекта](#структура-проекта)
- [Технологии](#технологии)
- [Установка](#установка)
- [Запуск](#запуск)
- [Документация](#документация)

## 🚀 Быстрый старт

### Требования
- Python 3.9+
- PostgreSQL
- Supabase (для хранения видео)

### Локальное развёртывание (5 минут)

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Создать файл окружения
cp config/.env.example config/.env
# Заполнить SUPABASE_URL и SUPABASE_KEY

# 3. Запустить приложение
python main.py
```

→ **Подробные инструкции:** [📖 QUICKSTART](./docs/QUICKSTART_VIDEO.md)

## 📂 Структура проекта

```
education_platform/
│
├── 📄 main.py                      # Точка входа приложения (FastAPI)
├── 📄 requirements.txt             # Зависимости Python
│
├── 📁 app/                         # Основной код приложения
│   ├── __init__.py
│   ├── config.py                   # Конфигурация
│   ├── database.py                 # Подключение БД
│   ├── dependencies.py             # Зависимости
│   ├── video_service.py            # Сервис работы с видео (Supabase)
│   ├── quiz_flow.py                # Логика квизов
│   │
│   ├── 📁 models/                  # ORM модели
│   │   ├── user.py, course.py, lesson.py
│   │   ├── quiz.py, comment.py, review.py
│   │   └── ...
│   │
│   ├── 📁 routers/                 # API endpoints
│   │   ├── auth.py                 # Аутентификация
│   │   ├── courses.py              # Управление курсами
│   │   ├── lessons.py              # Уроки
│   │   ├── videos.py               # API видео ⭐ НОВОЕ
│   │   ├── quizzes.py              # Квизы
│   │   └── ...
│   │
│   └── 📁 init_video_tables.py     # Автоматическая миграция видео-таблиц
│
├── 📁 templates/                   # HTML шаблоны Jinja2
│   ├── base.html                   # Базовый шаблон
│   ├── index.html, login.html, register.html
│   ├── course_page.html, lesson_page.html
│   ├── admin/                      # Админ-панель
│   └── errors/                     # Страницы ошибок
│
├── 📁 static/                      # Статические файлы
│   ├── css/                        # Стили
│   ├── js/                         # JavaScript
│   ├── images/                     # Изображения
│   ├── uploads/                    # Загруженные материалы
│   └── documents/
│
├── 📁 docs/                        # 📚 ДОКУМЕНТАЦИЯ
│   ├── QUICKSTART_VIDEO.md         # Быстрый старт видео
│   ├── VIDEO_INTEGRATION.md        # Полная документация видео
│   ├── DEPLOYMENT_CHECKLIST.md     # Чеклист развёртывания
│   ├── VIDEO_IMPLEMENTATION_SUMMARY.md
│   │
│   └── 📁 optimization/            # Отчёты оптимизации
│       ├── IMPLEMENTATION_GUIDE.md
│       ├── OPTIMIZATION_REPORT.md
│       └── README_OPTIMIZATIONS.md
│
├── 📁 scripts/                     # 🔧 УТИЛИТЫ
│   ├── manage_rls.py               # Управление RLS политиками
│   ├── setup_video_bucket.py       # Инициализация видео-хранилища
│   └── README.md                   # Инструкции по скриптам
│
├── 📁 migrations/                  # 🔄 SQL МИГРАЦИИ
│   └── 001_add_video_filename.sql
│
├── 📁 config/                      # ⚙️ КОНФИГУРАЦИЯ
│   ├── .env.example                # Пример переменных окружения
│   └── .env.production             # Production конфиг (не в git)
│
├── 📁 data/                        # 💾 ДАННЫЕ И ЛОГИ
│   ├── logs/                       # Логи приложения
│   │   └── server.log
│   ├── backups/                    # Резервные копии БД
│   └── education_platform.db       # SQLite БД (разработка)
│
├── 📁 tests/                       # ✅ ТЕСТЫ
│   └── (тесты будут добавлены)
│
├── .env.example                    # Устарелое, см. config/.env.example
├── .gitignore
├── .python-version
├── pyproject.toml
└── README.md                       # 👈 ВЫ ТУТ

```

## 🛠 Технологии

| Компонент | Технология |
|-----------|-----------|
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic |
| **БД** | PostgreSQL (production), SQLite (dev) |
| **Видео** | Supabase Storage, Cloudinary |
| **Фронтенд** | Jinja2, HTML5, CSS3, JavaScript |
| **Аутентификация** | bcrypt, JWT (session-based) |
| **Деплой** | Gunicorn, NGINX |

## 📥 Установка

### 1. Клонируем репозиторий
```bash
git clone <repository-url>
cd education_platform
```

### 2. Создаём виртуальное окружение
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# или
venv\Scripts\activate     # Windows
```

### 3. Устанавливаем зависимости
```bash
pip install -r requirements.txt
```

### 4. Конфигурируем переменные окружения
```bash
cp config/.env.example config/.env
# Заполните:
# - DATABASE_URL (PostgreSQL)
# - SUPABASE_URL и SUPABASE_KEY
# - SECRET_KEY для сессий
# - CLOUDINARY_CLOUD_NAME и API ключи
```

## ▶️ Запуск

### Локальная разработка
```bash
python main.py
# Приложение будет доступно на http://localhost:8000
```

### Production
```bash
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

## 📚 Документация

### Основные документы
- 🎥 [**QUICKSTART_VIDEO.md**](./docs/QUICKSTART_VIDEO.md) - За 5 минут до первого видео
- 📖 [**VIDEO_INTEGRATION.md**](./docs/VIDEO_INTEGRATION.md) - Полная архитектура и API
- ✅ [**DEPLOYMENT_CHECKLIST.md**](./docs/DEPLOYMENT_CHECKLIST.md) - Функциональное тестирование
- 📋 [**VIDEO_IMPLEMENTATION_SUMMARY.md**](./docs/VIDEO_IMPLEMENTATION_SUMMARY.md) - История изменений

### Отчёты и гайды
- [Optimization Report](./docs/optimization/OPTIMIZATION_REPORT.md)
- [Implementation Guide](./docs/optimization/IMPLEMENTATION_GUIDE.md)

### Скрипты и утилиты
- [Scripts README](./scripts/README.md) - Как использовать скрипты

## 🔐 Безопасность

- ✅ RLS политики в Supabase
- ✅ CORS конфигурация
- ✅ SQL injection защита (ORM)
- ✅ CSRF токены
- ✅ Хэширование паролей (bcrypt)
- ✅ Secure session cookies

## 📊 Ключевые фичи

- 🎓 **Курсы и модули** - Полная система управления контентом
- 🎥 **Видео с защитой** - Хранение в Supabase Storage
- 📝 **Квизы и оценки** - Встроенная система тестирования
- 👥 **Профили пользователей** - Отслеживание прогресса
- 💬 **Комментарии и отзывы** - Взаимодействие студентов
- 🔍 **Поиск** - Полнотекстовый поиск по контенту
- 📊 **Аналитика** - Мониторинг прогресса студентов

## 🐛 Troubleshooting

### Видео не загружается
→ Проверьте [VIDEO_INTEGRATION.md#Troubleshooting](./docs/VIDEO_INTEGRATION.md#troubleshooting)

### Ошибка БД
→ Проверьте подключение в `.env` и доступ к PostgreSQL

### Supabase API ошибки
→ Смотрите логи в `data/logs/server.log`

## 🤝 Вклад

Задачи для разработки находятся в GitHub Issues. Перед тем как начать работу:

1. Выберите задачу
2. Создайте feature branch: `git checkout -b feature/description`
3. Сделайте commit: `git commit -am 'Add feature'`
4. Push: `git push origin feature/description`
5. Создайте Pull Request

## 📝 Лицензия

[Указать лицензию]

---

**Последнее обновление:** 26 апреля 2026 г.  
**Версия:** 2.0 (с видео интеграцией)  
**Статус:** ✅ Production Ready

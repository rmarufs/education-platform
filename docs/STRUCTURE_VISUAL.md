# 📊 Визуальная структура проекта

## Полное дерево проекта

```
education_platform/
│
├── 📄 README.md                    ← ГЛАВНАЯ СТРАНИЦА ПРОЕКТА
├── 📄 main.py                      ← ТОЧКА ВХОДА (запуск приложения)
├── 📄 requirements.txt             ← Зависимости Python
├── 📄 .gitignore                   ← Git игнорирования
│
├── 📁 app/                         ← 🎯 ОСНОВНОЙ КОД ПРИЛОЖЕНИЯ
│   ├── __init__.py
│   ├── config.py                   ← Конфигурация (SUPABASE_URL и т.д.)
│   ├── database.py                 ← Подключение к БД, SessionLocal
│   ├── dependencies.py             ← Общие зависимости (get_db, get_current_user)
│   ├── video_service.py            ← Сервис работы с видео (Supabase) ⭐
│   ├── quiz_flow.py                ← Логика проведения квизов
│   ├── init_video_tables.py        ← Автоматическая миграция видео-таблиц
│   │
│   ├── 📁 models/                  ← ORM модели (SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── user.py                 ← User (профили, аутентификация)
│   │   ├── course.py               ← Course (курсы)
│   │   ├── module.py               ← Module (модули в курсе)
│   │   ├── lesson.py               ← Lesson (уроки с видео) ⭐
│   │   ├── category.py             ← Category (категории)
│   │   ├── quiz.py                 ← Quiz (квизы и вопросы)
│   │   ├── comment.py              ← Comment (комментарии)
│   │   ├── review.py               ← Review (отзывы)
│   │   ├── progress.py             ← Progress (прогресс студента)
│   │   ├── material.py             ← Material (учебные материалы)
│   │   └── contact.py              ← Contact (сообщения контактной формы)
│   │
│   └── 📁 routers/                 ← API Endpoints (FastAPI маршруты)
│       ├── __init__.py
│       ├── auth.py                 ← POST /api/auth/register, /login
│       ├── users.py                ← GET/PUT /api/users/profile
│       ├── courses.py              ← GET /api/courses
│       ├── modules.py              ← GET /api/modules/{id}
│       ├── lessons.py              ← GET /api/lessons/{id}
│       ├── videos.py               ← POST /api/videos/upload ⭐
│       ├── quizzes.py              ← GET/POST /api/quizzes
│       ├── comments.py             ← POST /api/comments
│       ├── reviews.py              ← POST /api/reviews
│       ├── profile.py              ← GET/PUT /api/profile
│       ├── pages.py                ← GET /pages/about, /contact
│       └── admin.py                ← Админ-панель и управление
│
├── 📁 templates/                   ← HTML Jinja2 шаблоны
│   ├── base.html                   ← Базовый шаблон (navbar, footer)
│   ├── index.html                  ← Главная страница
│   ├── login.html                  ← Форма входа
│   ├── register.html               ← Форма регистрации
│   ├── dashboard_student.html      ← Личный кабинет студента
│   ├── dashboard_teacher.html      ← Личный кабинет преподавателя
│   ├── course_page.html            ← Просмотр курса
│   ├── lesson_page.html            ← Видеоурок + комментарии
│   ├── quiz_page.html              ← Страница квиза
│   ├── profile.html                ← Профиль пользователя
│   ├── create_quiz.html            ← Создание квиза
│   ├── course_manage.html          ← Управление курсом (учитель)
│   ├── course_completed.html       ← Сертификат завершения
│   ├── search.html                 ← Поиск по курсам
│   ├── _course_macros.html         ← Макросы для курсов
│   ├── _quiz_authoring_macros.html ← Макросы для квизов
│   ├── _teacher_sidebar.html       ← Сайдбар преподавателя
│   │
│   ├── 📁 admin/                   ← Админ-панель
│   │   ├── base_admin.html         ← Базовый админ-шаблон
│   │   ├── index.html              ← Админ главная
│   │   ├── users.html              ← Управление пользователями
│   │   ├── teachers.html           ← Управление преподавателями
│   │   └── courses.html            ← Управление курсами
│   │
│   └── 📁 errors/                  ← Страницы ошибок
│       ├── 403.html                ← Доступ запрещен
│       ├── 404.html                ← Не найдено
│       └── 500.html                ← Ошибка сервера
│
├── 📁 static/                      ← Статические файлы (CSS, JS, изображения)
│   ├── 📁 css/
│   │   ├── style.css               ← Основные стили
│   │   ├── admin.css               ← Стили админ-панели
│   │   └── video_upload.css        ← Стили загрузки видео
│   │
│   ├── 📁 js/
│   │   ├── main.js                 ← Основной JavaScript
│   │   ├── auth.js                 ← Логика аутентификации
│   │   ├── courses.js              ← Управление курсами
│   │   ├── quiz_builder.js         ← Построитель квизов
│   │   ├── video_upload.js         ← Upload видео в Supabase ⭐
│   │   ├── video_playback.js       ← Плеер видео ⭐
│   │   ├── i18n.js                 ← Интернационализация
│   │   └── richtext.js             ← WYSIWYG редактор
│   │
│   ├── 📁 images/                  ← PNG, SVG иконки
│   ├── 📁 documents/               ← Скачиваемые документы
│   │
│   └── 📁 uploads/                 ← Загруженные пользователями файлы
│       ├── 📁 courses/             ← Изображения курсов
│       ├── 📁 materials/           ← Материалы курсов
│       └── 📁 videos/              ← Видео файлы (локальное хранилище)
│
├── 📁 docs/                        ← 📚 ПОЛНАЯ ДОКУМЕНТАЦИЯ
│   ├── README.md                   ← Указатель документации
│   ├── GETTING_STARTED.md          ← Быстрый старт (5 мин) ✨ НОВОЕ
│   ├── PROJECT_STRUCTURE.md        ← Описание структуры ✨ НОВОЕ
│   ├── CONTRIBUTING.md             ← Гайд для разработчиков ✨ НОВОЕ
│   ├── DEPLOYMENT.md               ← Production развёртывание ✨ НОВОЕ
│   ├── QUICKSTART_VIDEO.md         ← Быстрый старт видео
│   ├── VIDEO_INTEGRATION.md        ← Полная архитектура видео
│   ├── DEPLOYMENT_CHECKLIST.md     ← Чеклист развёртывания
│   ├── README_VIDEO.md             ← Навигатор видео документов
│   ├── VIDEO_IMPLEMENTATION_SUMMARY.md ← История изменений
│   │
│   └── 📁 optimization/            ← Отчёты оптимизации
│       ├── OPTIMIZATION_REPORT.md
│       ├── IMPLEMENTATION_GUIDE.md
│       ├── CODE_CHANGES_REFERENCE.md
│       └── README_OPTIMIZATIONS.md
│
├── 📁 scripts/                     ← 🔧 УТИЛИТЫ И СКРИПТЫ
│   ├── README.md                   ← Описание скриптов ✨ НОВОЕ
│   ├── setup_video_bucket.py       ← Инициализация Supabase Storage
│   ├── manage_rls.py               ← Управление RLS политиками
│   └── .gitkeep
│
├── 📁 migrations/                  ← 🔄 SQL МИГРАЦИИ БАЗЫ ДАННЫХ
│   └── 001_add_video_filename.sql
│
├── 📁 config/                      ← ⚙️ КОНФИГУРАЦИЯ (НЕ В GIT)
│   ├── .env.example                ← Пример всех переменных окружения
│   ├── .env.production             ← Production конфиг ✨ НОВОЕ
│   └── (config/.env ← .gitignore)
│
├── 📁 data/                        ← 💾 ДАННЫЕ И ЛОГИ
│   ├── 📁 logs/
│   │   ├── server.log
│   │   ├── access.log
│   │   ├── errors.log
│   │   └── .gitkeep
│   │
│   ├── 📁 backups/                 ← Резервные копии БД
│   │   └── .gitkeep
│   │
│   └── education_platform.db       ← SQLite БД (только для разработки)
│
├── 📁 tests/                       ← ✅ АВТОМАТИЧЕСКИЕ ТЕСТЫ
│   ├── __init__.py
│   ├── 📁 unit/                    ← Unit тесты
│   │   ├── test_models.py
│   │   ├── test_video_service.py
│   │   └── test_auth.py
│   │
│   ├── 📁 integration/             ← Integration тесты
│   │   ├── test_api_endpoints.py
│   │   └── test_video_upload.py
│   │
│   ├── 📁 fixtures/                ← Фикстуры для тестов
│   │   ├── users.json
│   │   └── courses.json
│   │
│   └── .gitkeep
│
└── 📁 venv/                        ← Виртуальное окружение (не в git!)
    └── (Python пакеты)
```

---

## 🎯 Легенда

| Символ | Значение |
|--------|----------|
| 📄 | Файл |
| 📁 | Папка |
| 📚 | Документация |
| 🎯 | Основной код |
| 🔧 | Утилиты |
| ⚙️ | Конфигурация |
| 💾 | Данные |
| ✅ | Тесты |
| 🔄 | Миграции |
| ⭐ | Новое (видео) |
| ✨ | Новое (эта организация) |

---

## 🚀 Когда добавляется новая фича

**Пример: Система уведомлений**

```
1. Создаём модель
   └─ app/models/notification.py

2. Создаём router
   └─ app/routers/notifications.py
   
3. Добавляем миграцию БД
   └─ migrations/NNN_add_notifications.sql
   
4. Пишем тесты
   └─ tests/unit/test_notification_*.py
   
5. Создаём шаблон (если нужен UI)
   └─ templates/notifications.html
   
6. Добавляем документацию
   └─ docs/NOTIFICATIONS.md
   
7. Обновляем README.md и главную документацию
```

---

## 📈 Размер проекта

```
Основной код:      ~3,500 строк (Python)
Шаблоны:          ~2,000 строк (HTML/Jinja2)
Фронтенд:         ~1,500 строк (JavaScript)
Тесты:            ~500+ строк
Документация:     ~15,000+ строк (Markdown)
─────────────────────────────
Итого:            ~22,500+ строк кода
```

---

## 💡 Важные моменты

1. **config/.env НЕ в git** - для безопасности (.gitignore)
2. **venv/ НЕ в git** - виртуальное окружение локально
3. **data/logs/* НЕ в git** - логи генерируются локально
4. **static/uploads/* частично в git** - добавьте .gitkeep в каждую папку

---

## 🔗 Связанные документы

- 📖 [README.md](../README.md) - Главный файл проекта
- 📚 [GETTING_STARTED.md](GETTING_STARTED.md) - Быстрый старт для новичков
- 🔍 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Детальное описание
- 🤝 [CONTRIBUTING.md](CONTRIBUTING.md) - Гайд для разработчиков
- 🚀 [DEPLOYMENT.md](DEPLOYMENT.md) - Production развёртывание

---

**Версия:** 2.0  
**Дата:** 26 апреля 2026 г.  
**Статус:** ✅ Production Ready

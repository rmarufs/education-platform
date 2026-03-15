# EduHub — Образовательная платформа

Минималистичная образовательная платформа (MVP) для студентов и преподавателей.

**Стек:** FastAPI · SQLite · SQLAlchemy · Jinja2 · Vanilla CSS/JS

---

## Быстрый старт

### 1. Клонируй репозиторий
```bash
git clone <repo-url>
cd education_platform
```

### 2. Создай и активируй виртуальное окружение
```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Установи зависимости
```bash
pip install -r requirements.txt
```

### 4. Настрой переменные окружения
```bash
cp .env.example .env
# Открой .env и замени SECRET_KEY на случайную строку
```

### 5. Запусти сервер
```bash
uvicorn main:app --reload
```

Открой **http://127.0.0.1:8000** в браузере.

---

## Структура проекта

```
education_platform/
├── main.py                    # Точка входа FastAPI
├── requirements.txt
├── .env.example               # Шаблон переменных окружения
│
├── app/
│   ├── config.py              # Настройки (читает .env)
│   ├── database.py            # SQLAlchemy + SQLite
│   ├── models/
│   │   ├── user.py            # Модель пользователя
│   │   └── course.py          # Модель курса
│   └── routers/
│       ├── auth.py            # Регистрация, логин, выход
│       ├── users.py           # Дашборды (student / teacher)
│       └── courses.py         # CRUD курсов
│
├── templates/                 # Jinja2 HTML шаблоны
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard_student.html
│   ├── dashboard_teacher.html
│   └── course_page.html
│
└── static/
    ├── css/style.css          # Дизайн-система
    └── js/
        ├── i18n.js            # Переключение языка RU / TJ
        ├── main.js            # Общие утилиты
        ├── auth.js            # Валидация форм
        └── courses.js         # Управление курсами
```

---

## Функционал

| Функция | Студент | Преподаватель |
|---------|:-------:|:-------------:|
| Просмотр списка курсов | ✅ | ✅ |
| Открыть страницу курса | ✅ | ✅ |
| Создать курс | — | ✅ |
| Редактировать курс | — | ✅ |
| Удалить курс | — | ✅ |
| Переключение языка RU/TJ | ✅ | ✅ |

---

## Переменные окружения (`.env`)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `SECRET_KEY` | Ключ подписи сессий | `change-this-...` |
| `APP_ENV` | Окружение (`development`/`production`) | `development` |
| `PORT` | Порт сервера | `8000` |

---

## API документация

После запуска доступна по адресу: **http://127.0.0.1:8000/api/docs**

---

## Технологии

- **[FastAPI](https://fastapi.tiangolo.com/)** — backend фреймворк
- **[SQLAlchemy](https://sqlalchemy.org/)** — ORM для SQLite
- **[Jinja2](https://jinja.palletsprojects.com/)** — HTML-шаблоны
- **[bcrypt](https://pypi.org/project/bcrypt/)** — хеширование паролей
- **Starlette Sessions** — cookie-сессии

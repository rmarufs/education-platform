# 🤝 Гайд для разработчиков (Contributing)

Спасибо за интерес к развитию платформы! Этот документ описывает, как начать разработку и делать вклады.

## 🎯 Перед тем как начать

### Требования
- Python 3.9+
- Git
- PostgreSQL (или SQLite для локальной разработки)
- Supabase аккаунт (для видео)

### Инструменты для разработки
```bash
# Форматирование кода
pip install black flake8

# Тестирование
pip install pytest pytest-cov

# Линтинг типов
pip install mypy
```

---

## 📖 Настройка локального окружения

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
pip install black flake8 pytest pytest-cov mypy
```

### 4. Копируем пример конфига
```bash
cp config/.env.example config/.env
# Заполните config/.env необходимыми значениями
```

### 5. Инициализируем БД
```bash
# Суперсервис инициализации (в main.py)
python main.py
# Затем Ctrl+C

# Или используйте migration команду
# python -m alembic upgrade head
```

---

## 🏗️ Структура для новой фичи

Когда добавляете новый функционал:

```
📋 Новая фича: Система уведомлений

├── 📁 Model
│   ├── app/models/notification.py
│   └── Миграция БД: migrations/NNN_add_notifications.sql
│
├── 🔌 Router
│   ├── app/routers/notifications.py
│   └── Зарегистрировать в main.py
│
├── 🎨 Template
│   └── templates/notifications.html
│
├── 💾 Service (если сложная логика)
│   └── app/notification_service.py
│
├── ✅ Tests
│   ├── tests/unit/test_notification_model.py
│   ├── tests/unit/test_notification_router.py
│   └── tests/integration/test_notification_flow.py
│
├── 📚 Документация
│   └── docs/NOTIFICATIONS.md
│
└── 🎯 Обновления
    ├── requirements.txt (если новые зависимости)
    ├── .gitignore (если новые файлы для игнора)
    └── README.md (если критично для пользователей)
```

---

## 🔄 Git Workflow

### 1. Создаём feature branch
```bash
git checkout -b feature/notification-system
# или
git checkout -b fix/video-playback-bug
# или
git checkout -b docs/add-api-guide
```

**Соглашение по именованию:**
- `feature/...` - новые фичи
- `fix/...` - исправления багов
- `docs/...` - документация
- `refactor/...` - рефакторинг
- `test/...` - тесты

### 2. Разработка

**Следуйте этим правилам:**

✅ **DO:**
```python
# Используйте type hints
def get_user(user_id: int) -> Optional[User]:
    """Получить пользователя по ID"""
    return db.query(User).filter(User.id == user_id).first()

# Структурируйте код
def process_video():
    """Сложный процесс в отдельные функции"""
    metadata = extract_metadata()
    thumbnail = generate_thumbnail()
    return upload_to_storage()

# Обрабатывайте ошибки
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Ошибка: {e}")
    raise HTTPException(status_code=400, detail="Clear message")
```

❌ **DON'T:**
```python
# Без типов
def get_user(user_id):
    pass

# Hardcoded значения
db_url = "postgresql://localhost:5432/db"

# Игнорирование ошибок
try:
    something()
except:
    pass

# Очень длинные функции
def do_everything():  # 500 строк кода
    pass
```

### 3. Тестирование

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Только юнит-тесты
pytest tests/unit

# Линтинг
flake8 app/
black --check app/
mypy app/
```

**Пример теста:**
```python
# tests/unit/test_notification_service.py
import pytest
from app.notification_service import send_notification

class TestNotificationService:
    def test_send_notification_success(self):
        """Успешная отправка уведомления"""
        result = send_notification(user_id=1, message="Test")
        assert result.status == "sent"
    
    def test_send_notification_invalid_user(self):
        """Ошибка при неверном пользователе"""
        with pytest.raises(ValueError):
            send_notification(user_id=999999, message="Test")
```

### 4. Форматирование кода

```bash
# Автоматическое форматирование
black app/

# Проверка стиля
flake8 app/

# Проверка типов
mypy app/
```

### 5. Коммиты

**Хорошие сообщения коммитов:**

```bash
# Феатура
git commit -m "feat: добавить систему уведомлений"

# Исправление
git commit -m "fix: исправить загрузку видео в Chrome"

# Документация
git commit -m "docs: обновить API документацию"

# Рефакторинг
git commit -m "refactor: переструктурировать video_service"

# Тесты
git commit -m "test: добавить интеграционные тесты для API"
```

**Структура коммита:**
```
feat: краткое описание (50 символов макс)

Более подробное описание изменений.
Объясните ЧТО и ПОЧЕМУ, не КАК.

- Пункт 1
- Пункт 2

Closes #123  (связанная issue)
```

### 6. Push и Pull Request

```bash
git push origin feature/notification-system
```

**Создайте PR на GitHub с:**
- ✅ Описание фичи
- ✅ Скриншоты (если UI изменения)
- ✅ Чеклист тестирования
- ✅ Связанные issues

---

## 📝 Документирование

### Docstrings (PEP 257)
```python
def send_notification(user_id: int, message: str) -> dict:
    """
    Отправить уведомление пользователю.
    
    Используется Supabase для хранения, отправляется по email.
    
    Args:
        user_id: ID пользователя
        message: Текст сообщения (максимум 500 символов)
    
    Returns:
        dict: {"id": notification_id, "status": "sent"}
    
    Raises:
        ValueError: Если user_id не существует
        Exception: Если Supabase недоступна
    
    Example:
        >>> result = send_notification(1, "Welcome!")
        >>> print(result['status'])
        'sent'
    """
    pass
```

### Комментарии
```python
# ❌ Плохо
x = y + 1  # добавить 1

# ✅ Хорошо
# Смещаем индекс на 1 для учета системных резервных полей
x = y + 1
```

### Обновление документации
- Обновите [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) если изменили структуру
- Добавьте [docs/](./docs/) файл если добавили крупную фичу
- Обновите [README.md](../README.md) если изменилась инструкция по запуску

---

## 🐛 Работа с bugами

### Нашли баг?

1. **Проверьте, что это действительно баг:**
   - Воспроизвести проблему
   - Проверить в разных браузерах/окружениях
   - Посмотреть логи в `data/logs/`

2. **Создайте GitHub Issue:**
```
Заголовок: Видео не загружается в Safari

Описание:
- Версия: 2.0
- Браузер: Safari 15.x
- Шаги воспроизведения:
  1. Откройте курс
  2. Нажмите на видеоурок
  3. Видео не загружается
  
Ожидается: Видео должно загружаться
Получается: Черный экран, ошибка в консоли

Ошибка: ... (из консоли браузера)
Окружение: macOS 12, Python 3.10
```

3. **Создайте feature branch:**
```bash
git checkout -b fix/safari-video-loading
```

4. **Исправьте баг + тест:**
```python
# tests/unit/test_video_playback.py
def test_video_playback_safari():
    """Проверить загрузку видео в Safari"""
    # Имитируем Safari User-Agent
    # Проверяем, что видео загружается
    pass
```

---

## 📊 Коды отступов и форматирование

- **Indentation:** 4 spaces (не табуляция!)
- **Line length:** максимум 88 символов
- **Кодировка:** UTF-8

---

## 🚀 Перед финальным push

**Чеклист:**
- [ ] Все тесты проходят (`pytest`)
- [ ] Код отформатирован (`black app/`)
- [ ] Нет ошибок линтера (`flake8 app/`)
- [ ] Типы проверены (`mypy app/`)
- [ ] Документация обновлена
- [ ] Нет логирования критичных данных
- [ ] Нет hardcoded API ключей
- [ ] Новые зависимости добавлены в `requirements.txt`

---

## 📚 Полезные ссылки

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Supabase Docs](https://supabase.com/docs)
- [Python PEP 8](https://www.python.org/dev/peps/pep-0008/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

## 💬 Вопросы?

Создайте Discussion в GitHub или свяжитесь с мейнтейнерами.

**Спасибо за вклад! 🙏**

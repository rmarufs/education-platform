# 🔧 Скрипты управления (scripts/)

Утилиты для инициализации, конфигурирования и управления платформой.

## 📋 Доступные скрипты

### 1. **setup_video_bucket.py** - Инициализация видео-хранилища
Создаёт структуру папок и политики RLS в Supabase для хранения видео.

```bash
python scripts/setup_video_bucket.py
```

**Что делает:**
- ✅ Создаёт bucket `education_videos` в Supabase
- ✅ Настраивает папки: `/courses/`, `/lessons/`, `/materials/`
- ✅ Устанавливает RLS политики (только авторизованные пользователи)
- ✅ Конфигурирует CORS

**Требования:**
- `config/.env` с `SUPABASE_URL` и `SUPABASE_KEY`

---

### 2. **manage_rls.py** - Управление RLS политиками

Утилита для управления правилами доступа (Row Level Security) в Supabase.

```bash
# Просмотр текущих политик
python scripts/manage_rls.py --list

# Создание новой политики
python scripts/manage_rls.py --create --table videos --policy admin_access

# Удаление политики
python scripts/manage_rls.py --delete --table videos --policy old_policy
```

**Требования:**
- `config/.env` с учётными данными Supabase

---

## 🚀 Как добавить новый скрипт

1. Создайте файл в папке `scripts/`
2. Добавьте shebang: `#!/usr/bin/env python3`
3. Добавьте docstring с описанием
4. Используйте переменные из `config/.env`

**Пример:**
```python
#!/usr/bin/env python3
"""
Описание скрипта
Использование: python scripts/my_script.py [args]
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
env_path = Path(__file__).parent.parent / "config" / ".env"
load_dotenv(env_path)

# Ваш код здесь
```

---

## ⚙️ Переменные окружения

Все скрипты используют переменные из `config/.env`:

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# PostgreSQL (для прямого доступа)
DATABASE_URL=postgresql://user:password@localhost:5432/edu_db
```

---

## 📚 Связанная документация

- [VIDEO_INTEGRATION.md](../docs/VIDEO_INTEGRATION.md) - Архитектура видео
- [DEPLOYMENT_CHECKLIST.md](../docs/DEPLOYMENT_CHECKLIST.md) - Чеклист развёртывания


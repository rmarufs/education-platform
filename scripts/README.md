# Скрипты проекта

В этой папке лежат небольшие вспомогательные утилиты для разработки и проверки проекта.

## Доступные скрипты

### `check_i18n.py`

Проверяет, что ключи `data-i18n` из HTML-шаблонов зарегистрированы в `static/js/i18n.js`.

```bash
python3 scripts/check_i18n.py
```

Скрипт выводит список отсутствующих ключей или сообщение, что все найденные ключи зарегистрированы.

---

## Как добавить новый скрипт

1. Создайте файл в папке `scripts/`.
2. Добавьте короткий docstring с описанием назначения.
3. Если нужны переменные окружения, загружайте их из `config/.env`.
4. Обновите этот README с командой запуска и кратким описанием.

```python
#!/usr/bin/env python3
"""
Описание скрипта.
Использование: python3 scripts/my_script.py [args]
"""

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / "config" / ".env"
load_dotenv(env_path)
```

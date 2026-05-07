import re
import json
from pathlib import Path

# Находим все ключи в шаблонах
template_keys = set()
for f in Path('templates').rglob('*.html'):
    content = f.read_text()
    keys = re.findall(r'data-i18n="([^"]+)"', content)
    template_keys.update(keys)

# Находим все ключи в i18n.js
i18n_content = Path('static/js/i18n.js').read_text()
i18n_keys = set(re.findall(r'"([a-z][a-z0-9_.]+)":\s*"', i18n_content))

# Находим незарегистрированные
missing = template_keys - i18n_keys
if missing:
    print(f"❌ Найдено {len(missing)} незарегистрированных ключей:")
    for k in sorted(missing):
        print(f"  - {k}")
else:
    print("✅ Все ключи зарегистрированы!")

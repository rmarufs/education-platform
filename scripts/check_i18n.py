import re
from pathlib import Path

I18N_KEY_RE = re.compile(r"^[a-z][a-z0-9_.]+$")

# Находим все ключи в шаблонах
template_keys = set()
dynamic_keys = set()
for f in Path('templates').rglob('*.html'):
    content = f.read_text()
    keys = re.findall(r'data-i18n="([^"]+)"', content)
    for key in keys:
        if I18N_KEY_RE.fullmatch(key):
            template_keys.add(key)
        else:
            dynamic_keys.add(key)

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
    if dynamic_keys:
        print(f"ℹ️ Пропущено {len(dynamic_keys)} динамических data-i18n выражений.")
    print("✅ Все ключи зарегистрированы!")

"""
Единственный экземпляр Jinja2Templates для всего приложения.
Все кастомные фильтры регистрируются здесь, чтобы они были
доступны в любом роутере, который импортирует этот модуль.
"""
import base64
from fastapi.templating import Jinja2Templates
import markupsafe

templates = Jinja2Templates(directory="templates")

def clean_html_filter(value):
    if not value:
        return ""
    return markupsafe.Markup(value)

templates.env.filters["clean_html"] = clean_html_filter


def _obfuscate_yt(s: str) -> str:
    """Caesar+Base64 обфускация YouTube-ID для шаблонов."""
    if not s:
        return ""
    shifted = "".join(chr(ord(c) + 3) for c in s[::-1])
    return base64.b64encode(shifted.encode("utf-8")).decode("utf-8")


templates.env.filters["b64encode"] = _obfuscate_yt

import re
import bleach
from bleach.css_sanitizer import CSSSanitizer

# ── Разрешённые теги ───────────────────────────────────────────────────────────
ALLOWED_TAGS = frozenset([
    'p', 'b', 'i', 'strong', 'em', 'ul', 'ol', 'li',
    'a', 'br', 'span', 'div', 'h1', 'h2', 'h3',
])

# ── Разрешённые атрибуты ───────────────────────────────────────────────────────
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style'],
    'a': ['href', 'target', 'rel'],
}

# ── CSS-санитайзер (bleach v6+) ────────────────────────────────────────────────
_css_sanitizer = CSSSanitizer(allowed_css_properties=[
    'color', 'background-color', 'font-size', 'font-weight',
    'text-align', 'margin', 'padding', 'border',
])

# ── Cleaner (переиспользуемый объект, эффективнее чем bleach.clean()) ──────────
_cleaner = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    css_sanitizer=_css_sanitizer,
    strip=True,
    strip_comments=True,
)


def sanitize_html(html_content: str) -> str:
    """
    Очищает входящий HTML, разрешая только безопасные теги и атрибуты.
    Совместима с bleach v6+. Защищает от Stored XSS атак.
    """
    if not html_content:
        return ""
    try:
        return _cleaner.clean(html_content)
    except Exception:
        # В крайнем случае — полное экранирование
        return bleach.clean(html_content, tags=[], strip=True)

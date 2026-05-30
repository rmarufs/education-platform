import bleach

ALLOWED_TAGS = [
    'p', 'b', 'i', 'strong', 'em', 'ul', 'ol', 'li', 
    'a', 'br', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    's', 'strike'
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style'],
    'a': ['href', 'target', 'rel']
}

# Ограничиваем потенциально опасные CSS свойства
ALLOWED_STYLES = [
    "color",
    "background-color",
    "font-weight",
    "font-style",
    "text-decoration",
    "text-align",
    "font-size",
    "line-height",
    "margin-left",
    "margin-right",
    "padding-left",
    "padding-right",
]

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

from bleach.css_sanitizer import CSSSanitizer
css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)

def sanitize_html(html_content: str) -> str:
    """
    Очищает входящий HTML, разрешая только безопасные теги и атрибуты.
    Защищает от Stored XSS атак.
    """
    if not html_content:
        return ""
    
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=css_sanitizer,
        strip=True
    )

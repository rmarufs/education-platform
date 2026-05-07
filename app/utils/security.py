import bleach

ALLOWED_TAGS = [
    'p', 'b', 'i', 'strong', 'em', 'ul', 'ol', 'li', 
    'a', 'br', 'span', 'div', 'h1', 'h2', 'h3'
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style'],
    'a': ['href', 'target', 'rel']
}

# Ограничиваем потенциально опасные CSS свойства (например, url() или expression())
ALLOWED_STYLES = [
    'color', 'background-color', 'font-size', 'font-weight', 
    'text-align', 'margin', 'padding', 'border'
]

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
        styles=ALLOWED_STYLES,
        strip=True  # Удалять недопустимые теги вместо их эскейпинга
    )

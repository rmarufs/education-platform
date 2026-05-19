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

# Ограничиваем потенциально опасные CSS свойства (например, url() или expression())
ALLOWED_STYLES = [
    'color', 'background-color', 'font-size', 'font-weight', 
    'text-align', 'margin', 'padding', 'border'
]

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

try:
    from bleach.css_sanitizer import CSSSanitizer
    css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_STYLES)
except ImportError:
    css_sanitizer = None

def sanitize_html(html_content: str) -> str:
    """
    Очищает входящий HTML, разрешая только безопасные теги и атрибуты.
    Защищает от Stored XSS атак.
    """
    if not html_content:
        return ""
    
    kwargs = {
        "tags": ALLOWED_TAGS,
        "attributes": ALLOWED_ATTRIBUTES,
        "protocols": ALLOWED_PROTOCOLS,
        "strip": True
    }
    if css_sanitizer:
        kwargs["css_sanitizer"] = css_sanitizer
        
    return bleach.clean(html_content, **kwargs)

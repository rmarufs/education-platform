import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.config import SMTP_EMAIL, SMTP_FROM_NAME, SMTP_PASSWORD, SMTP_PORT, SMTP_SERVER


logger = logging.getLogger(__name__)


def is_email_configured() -> bool:
    return bool(SMTP_SERVER and SMTP_EMAIL and SMTP_PASSWORD)


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    if not is_email_configured():
        logger.warning("SMTP is not configured; email was not sent.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_EMAIL))
    message["To"] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=20) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as smtp:
            smtp.starttls(context=context)
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(message)

    return True

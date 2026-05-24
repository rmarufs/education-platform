import hmac
import logging
import secrets
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.datastructures import Headers


logger = logging.getLogger(__name__)


CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def is_valid_csrf_token(request: Request, token: str | None) -> bool:
    expected = request.session.get(CSRF_SESSION_KEY)
    if not expected or not token:
        return False
    return hmac.compare_digest(str(expected), str(token))


def extract_csrf_token_from_body(body: bytes, content_type: str) -> str | None:
    if not body:
        return None

    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        values = parsed.get(CSRF_FORM_FIELD)
        return values[0] if values else None

    if "multipart/form-data" in content_type:
        marker = f'name="{CSRF_FORM_FIELD}"'.encode("utf-8")
        field_index = body.find(marker)
        if field_index == -1:
            return None

        value_start = body.find(b"\r\n\r\n", field_index)
        if value_start == -1:
            return None
        value_start += 4

        value_end = body.find(b"\r\n", value_start)
        if value_end == -1:
            value_end = len(body)
        return body[value_start:value_end].decode("utf-8", errors="replace").strip()

    return None


class CSRFMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith("/static/"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        get_csrf_token(request)

        method = scope.get("method", "GET").upper()
        if method in SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        token = headers.get(CSRF_HEADER)
        app_receive = receive

        if not token:
            content_type = headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
                body = await self._read_body(receive)
                token = extract_csrf_token_from_body(body, content_type)
                body_sent = False

                async def replay_receive():
                    nonlocal body_sent
                    if not body_sent:
                        body_sent = True
                        return {"type": "http.request", "body": body, "more_body": False}
                    return await receive()

                app_receive = replay_receive

        if not is_valid_csrf_token(request, token):
            logger.warning("CSRF validation failed: method=%s path=%s", method, path)
            message = "CSRF token is missing or invalid."
            accept = headers.get("accept", "")
            if path.startswith("/api/") or "application/json" in accept:
                response = JSONResponse({"detail": message}, status_code=403)
            else:
                response = PlainTextResponse(message, status_code=403)
            await response(scope, receive, send)
            return

        await self.app(scope, app_receive, send)

    async def _read_body(self, receive) -> bytes:
        body_parts = []
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                break
            body_parts.append(message.get("body", b""))
            more_body = message.get("more_body", False)
        return b"".join(body_parts)

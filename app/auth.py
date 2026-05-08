import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import RedirectResponse

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-key-change-me")
SESSION_COOKIE_NAME = "ds_memory_admin_session"
LEGACY_SESSION_COOKIE_NAMES = ("admin_session",)
SESSION_MAX_AGE = 60 * 60 * 8


def _base64_url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64_url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(value: str) -> str:
    return hmac.new(
        APP_SECRET_KEY.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _create_session_token(username: str) -> str:
    payload = {
        "username": username,
        "role": "admin",
        "exp": int(time.time()) + SESSION_MAX_AGE,
    }
    encoded_payload = _base64_url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    return f"{encoded_payload}.{_sign(encoded_payload)}"


def _read_session_token(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None

    encoded_payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(encoded_payload)):
        return None

    try:
        payload = json.loads(_base64_url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError):
        return None

    if payload.get("username") != ADMIN_USERNAME:
        return None
    if payload.get("role") != "admin":
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None

    return payload


def _current_admin(request: Request) -> dict | None:
    return _read_session_token(request.cookies.get(SESSION_COOKIE_NAME))


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def _safe_next_url(value: str | None, default: str = "/admin") -> str:
    if not value:
        return default
    if not value.startswith("/") or value.startswith("//"):
        return default
    if "\r" in value or "\n" in value:
        return default
    return value


def _redirect_to_login(next_url: str) -> RedirectResponse:
    query = urlencode({"next": _safe_next_url(next_url, "/")})
    return _no_store(RedirectResponse(url=f"/login?{query}", status_code=303))

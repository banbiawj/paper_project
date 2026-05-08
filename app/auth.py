import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path
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
PASSWORD_ITERATIONS = 260000
USER_STATUS_ACTIVE = "active"
USER_STATUS_DISABLED = "disabled"


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


def _data_root() -> Path:
    return Path(os.getenv("DS_MEMORY_DATA_ROOT", "static/data"))


def _users_file() -> Path:
    return _data_root() / "users.json"


def _now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _read_users() -> list[dict]:
    path = _users_file()
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("users.json 必须是 JSON 列表")
    return [user for user in data if isinstance(user, dict)]


def _write_users(users: list[dict]) -> None:
    path = _users_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def _public_user(user: dict) -> dict:
    public = dict(user)
    public.pop("password_hash", None)
    return public


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}$"
        f"{salt}${_base64_url_encode(digest)}"
    )


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected_digest = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(_base64_url_encode(digest), expected_digest)


def _find_user_by_login(login: str) -> dict | None:
    value = (login or "").strip()
    lowered = value.lower()
    if not value:
        return None
    for user in _read_users():
        username = str(user.get("username", "")).strip()
        email = str(user.get("email", "")).strip().lower()
        if username == value or username.lower() == lowered or email == lowered:
            return user
    return None


def _find_user_by_id(user_id: str) -> dict | None:
    for user in _read_users():
        if str(user.get("id", "")) == user_id:
            return user
    return None


def _create_user(username: str, email: str, password: str) -> dict:
    username = (username or "").strip()
    email = (email or "").strip().lower()
    password = password or ""

    if not username:
        raise ValueError("用户名不能为空")
    if not email:
        raise ValueError("邮箱不能为空")
    if "@" not in email:
        raise ValueError("邮箱格式不正确")
    if not password:
        raise ValueError("密码不能为空")
    if username.lower() == ADMIN_USERNAME.lower():
        raise ValueError("用户名已存在")

    users = _read_users()
    for user in users:
        if str(user.get("username", "")).strip().lower() == username.lower():
            raise ValueError("用户名已存在")
        if str(user.get("email", "")).strip().lower() == email:
            raise ValueError("邮箱已存在")

    now = _now_string()
    user = {
        "id": uuid.uuid4().hex,
        "username": username,
        "email": email,
        "password_hash": _hash_password(password),
        "role": "user",
        "status": USER_STATUS_ACTIVE,
        "created_at": now,
        "updated_at": now,
        "last_login_at": "",
    }
    users.append(user)
    _write_users(users)
    return user


def _authenticate_user(login: str, password: str) -> tuple[dict | None, str | None]:
    user = _find_user_by_login(login)
    if not user or not _verify_password(password or "", str(user.get("password_hash", ""))):
        return None, "账号或密码错误"
    if user.get("status") != USER_STATUS_ACTIVE:
        return None, "账号已被禁用"
    return user, None


def _update_user_login(user_id: str) -> None:
    users = _read_users()
    now = _now_string()
    for user in users:
        if str(user.get("id", "")) == user_id:
            user["last_login_at"] = now
            user["updated_at"] = now
            _write_users(users)
            return


def _create_session_token(username: str, role: str = "admin") -> str:
    payload = {
        "username": username,
        "role": role,
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

    if int(payload.get("exp", 0)) < int(time.time()):
        return None

    role = payload.get("role")
    username = str(payload.get("username", ""))
    if role == "admin":
        if username != ADMIN_USERNAME:
            return None
        return payload
    if role == "user":
        user = _find_user_by_login(username)
        if not user or user.get("status") != USER_STATUS_ACTIVE:
            return None
        payload["user_id"] = user.get("id", "")
        return payload

    return None


def _current_session(request: Request) -> dict | None:
    return _read_session_token(request.cookies.get(SESSION_COOKIE_NAME))


def _current_admin(request: Request) -> dict | None:
    payload = _current_session(request)
    if payload and payload.get("role") == "admin":
        return payload
    return None


def _current_user(request: Request) -> dict | None:
    payload = _current_session(request)
    if payload and payload.get("role") == "user":
        return payload
    return None


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

from typing import Union,Generic, TypeVar
import uvicorn
import os
import base64
import hashlib
import hmac
import json
import time
from typing import List
from urllib.parse import parse_qs, urlencode
from fastapi import FastAPI, File, UploadFile, HTTPException,Path, Request ,Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel , Field
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse,JSONResponse,RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.v1 import api_router

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-key-change-me")
SESSION_COOKIE_NAME = "ds_memory_admin_session"
LEGACY_SESSION_COOKIE_NAMES = ("admin_session",)
SESSION_MAX_AGE = 60 * 60 * 8

# 允许跨域的源，可以写具体域名或 ["*"] 允许所有
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # 允许的源
    allow_credentials=True,
    allow_methods=["*"],            # 允许的 HTTP 方法，如 ["GET", "POST"]
    allow_headers=["*"],            # 允许的 HTTP 请求头
)



app.include_router(api_router, prefix="/api/v1")


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


async def _read_urlencoded_form(request: Request) -> dict:
    body = await request.body()
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not _current_admin(request):
        return _redirect_to_login("/")
    # 可以传入动态参数
    return _no_store(
        templates.TemplateResponse(request, "index.html", {"title": "FastAPI 示例"})
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    next_url = _safe_next_url(request.query_params.get("next"))
    if _current_admin(request):
        return _no_store(RedirectResponse(url=next_url, status_code=303))
    return _no_store(
        templates.TemplateResponse(
            request,
            "login.html",
            {"error": None, "username": "", "next_url": next_url},
        )
    )


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request):
    form_data = await _read_urlencoded_form(request)
    username = form_data.get("username", "").strip()
    password = form_data.get("password", "")
    remember = form_data.get("remember") == "on"
    next_url = _safe_next_url(form_data.get("next"))

    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        return _no_store(
            templates.TemplateResponse(
                request,
                "login.html",
                {"error": "账号或密码错误", "username": username, "next_url": next_url},
                status_code=401,
            )
        )

    response = _no_store(RedirectResponse(url=next_url, status_code=303))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_create_session_token(username),
        max_age=SESSION_MAX_AGE if remember else None,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    admin = _current_admin(request)
    if not admin:
        return _redirect_to_login("/admin")
    return _no_store(
        templates.TemplateResponse(
            request,
            "admin.html",
            {"admin_user": admin["username"]},
        )
    )


@app.post("/logout")
async def logout():
    response = _no_store(RedirectResponse(url="/login", status_code=303))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    for cookie_name in LEGACY_SESSION_COOKIE_NAMES:
        response.delete_cookie(cookie_name, path="/")
    return response


if __name__ == "__main__":
   uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)


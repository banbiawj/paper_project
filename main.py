from typing import Union,Generic, TypeVar
import uvicorn
from typing import List
from urllib.parse import parse_qs
from fastapi import FastAPI, File, UploadFile, HTTPException,Path, Request ,Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel , Field
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse,JSONResponse,RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.v1 import api_router
from app.auth import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    LEGACY_SESSION_COOKIE_NAMES,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
    _authenticate_user,
    _create_user,
    _create_session_token,
    _current_admin,
    _current_session,
    _current_user,
    _no_store,
    _redirect_to_login,
    _safe_next_url,
    _update_user_login,
)

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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


async def _read_urlencoded_form(request: Request) -> dict:
    body = await request.body()
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not _current_session(request):
        return _redirect_to_login("/")
    # 可以传入动态参数
    return _no_store(
        templates.TemplateResponse(request, "index.html", {"title": "FastAPI 示例"})
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    requested_next = request.query_params.get("next")
    if _current_admin(request):
        return _no_store(RedirectResponse(url="/admin", status_code=303))
    if _current_user(request):
        next_url = _safe_next_url(requested_next, "/")
        if next_url.startswith("/admin"):
            next_url = "/"
        return _no_store(RedirectResponse(url=next_url, status_code=303))
    next_url = _safe_next_url(requested_next, "")
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
    requested_next = form_data.get("next")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        response = _no_store(
            RedirectResponse(
                url="/admin",
                status_code=303,
            )
        )
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=_create_session_token(username, "admin"),
            max_age=SESSION_MAX_AGE if remember else None,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response

    user, user_error = _authenticate_user(username, password)
    if not user:
        return _no_store(
            templates.TemplateResponse(
                request,
                "login.html",
                {
                    "error": user_error or "账号或密码错误",
                    "username": username,
                    "next_url": _safe_next_url(requested_next, ""),
                },
                status_code=401,
            )
        )

    _update_user_login(user["id"])
    next_url = _safe_next_url(requested_next, "/")
    if next_url.startswith("/admin"):
        next_url = "/"
    response = _no_store(RedirectResponse(url=next_url, status_code=303))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_create_session_token(user["username"], "user"),
        max_age=SESSION_MAX_AGE if remember else None,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if _current_admin(request):
        return _no_store(RedirectResponse(url="/admin", status_code=303))
    if _current_user(request):
        return _no_store(RedirectResponse(url="/", status_code=303))
    return _no_store(
        templates.TemplateResponse(
            request,
            "register.html",
            {"error": None, "username": "", "email": ""},
        )
    )


@app.post("/register", response_class=HTMLResponse)
async def register(request: Request):
    form_data = await _read_urlencoded_form(request)
    username = form_data.get("username", "").strip()
    email = form_data.get("email", "").strip()
    password = form_data.get("password", "")
    confirm_password = form_data.get("confirm_password", "")

    error = None
    if password != confirm_password:
        error = "两次输入的密码不一致"

    try:
        if error:
            raise ValueError(error)
        user = _create_user(username, email, password)
    except ValueError as exc:
        return _no_store(
            templates.TemplateResponse(
                request,
                "register.html",
                {"error": str(exc), "username": username, "email": email},
                status_code=400,
            )
        )

    response = _no_store(RedirectResponse(url="/", status_code=303))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_create_session_token(user["username"], "user"),
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


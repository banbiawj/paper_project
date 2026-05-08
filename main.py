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
    _create_session_token,
    _current_admin,
    _no_store,
    _redirect_to_login,
    _safe_next_url,
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


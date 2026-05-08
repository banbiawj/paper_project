from typing import Union,Generic, TypeVar
import uvicorn
import os
from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException,Path, Request ,Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel , Field
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router

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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # 可以传入动态参数
    return templates.TemplateResponse(request, "index.html", {"title": "FastAPI 示例"})


if __name__ == "__main__":
   uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)


from typing import Union,Generic, TypeVar
import uvicorn
import os
import json
from typing import List
from fastapi import FastAPI,APIRouter, File, UploadFile, HTTPException,Path, Request ,Form
from pydantic import BaseModel , Field
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mylib.File import JsonOperate as J
from enum import Enum

IDIOM_PATH ="static/data/idiom"
WORDS_PATH ="static/data/words"


router =  APIRouter()
ROOTPATH = os.getcwd()

T = TypeVar("T")

class REST_API_standard(BaseModel, Generic[T]):
    code: int
    message: str
    data: T  # T 就是泛型参数


class ErrorResponse(BaseModel):
    code: int
    message: str


class TextResponse(BaseModel):
    error: str
    criterion: str
    position: str

class limit(str,Enum):
    idiom="idiom"
    words="words"


class FavoriteListRequest(BaseModel):
    TypeName:limit = Field(default=limit.idiom)
    BookName:str = Field(default="词库")



# 获取，收藏夹目录列表
@router.post("/FavoriteList", response_model=REST_API_standard)
async def FavoriteList(request: FavoriteListRequest):
    try:
        Type = request.TypeName
        BookName =  request.BookName
        # 从 request 里拿到前端传来的数据

        if Type =="idiom":
            Favorite_path = os.path.join(IDIOM_PATH,BookName )
        elif Type =="words":
            Favorite_path = os.path.join(WORDS_PATH,BookName )

        FavoriteList_list = J.list_files_in_directory(Favorite_path)
        result = REST_API_standard(
            code=200,
            message=("succeed"),
            data = {
                'FavoriteList_list':FavoriteList_list,
            }
        )
        return result
    except Exception as e:
        error = ErrorResponse(code=500, message=f"analyse failed: {e}")
        return JSONResponse(
            status_code=500,       # <-- HTTP 状态码
            content=error.model_dump()   # <-- 用 BaseModel 转 dict
        )


# 获取，书籍目录列表
@router.post("/BookshelfList", response_model=REST_API_standard)
async def BookshelfList():
    try:
        # 从 request 里拿到前端传来的数据
        idiom_BookshelfList_path =IDIOM_PATH
        idiom_BookshelfList_list = J.get_folder_names(idiom_BookshelfList_path)
        words_BookshelfList_path =WORDS_PATH
        words_BookshelfList_list = J.get_folder_names(words_BookshelfList_path)
        result = REST_API_standard(
            code=200,
            message=("succeed"),
            data = {
                'idiom_BookshelfList_list':idiom_BookshelfList_list,
                'words_BookshelfList_list':words_BookshelfList_list
            }
        )
        return result
    except Exception as e:
        error = ErrorResponse(code=500, message=f"analyse failed: {e}")
        return JSONResponse(
            status_code=500,       # <-- HTTP 状态码
            content=error.model_dump()   # <-- 用 BaseModel 转 dict
        )

class limit(str,Enum):
    idiom="idiom"
    words="words"


class CreateFavoriteRequest(BaseModel):
    TypeName:limit = Field(default=limit.idiom)
    BookName:str = Field()


# 创建书籍
@router.post("/CreateBook", response_model=REST_API_standard)
async def CreateBook(request: CreateFavoriteRequest):
    try:
        # 从 request 里拿到前端传来的数据
        typename = request.TypeName
        bookname = request.BookName
        if typename =="idiom":
            create_path =IDIOM_PATH
        elif typename =="words":
            create_path =WORDS_PATH
        JsonPath = J.create_folder_and_list(create_path,bookname)
        create_favorite_path = os.path.join(create_path,bookname)
        # 创建全部和默认收藏夹[2026/1/19]
        J.create_json_file(create_favorite_path,"default.json")
        J.create_json_file(create_favorite_path,"query.json")
        
        result = REST_API_standard(
            code=200,
            message=("succeed"),
            data = JsonPath
        )
        return result
    except Exception as e:
        error = ErrorResponse(code=500, message=f"analyse failed: {e}")
        return JSONResponse(
            status_code=500,       # <-- HTTP 状态码
            content=error.model_dump()   # <-- 用 BaseModel 转 dict
        )

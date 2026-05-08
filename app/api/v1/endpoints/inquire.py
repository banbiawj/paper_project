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
from enum import Enum

from mylib.Agent import inquire as A
from mylib.File import JsonOperate as J

IDIOM_PATH ="static/data/idiom"
WORDS_PATH ="static/data/words"


router =  APIRouter()

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

class Data_File(BaseModel):
    filename:str
    saved:str

class UploadStatus(BaseModel):
    code:int
    message:str
    data:Data_File

class limit(str,Enum):
    idiom="idiom"
    words="words"

class InquireRequest(BaseModel):
    TypeName:limit = Field(default=limit.idiom)
    InquireContent:str


@router.post("/query", response_model=REST_API_standard)
async def inquire_idiom(request: InquireRequest):
    try:
        # 从 request 里拿到前端传来的数据
        query = request.InquireContent
        type = request.TypeName
        if type == "idiom":
            path =IDIOM_PATH
            path = os.path.join(path,"词库")
            query_list = J.read_json_file(path,"query")
            query_result =J.find_in_json(query_list,'word',query)
            print(f"'{query}'-本地成语查询结果：{query_result}")
            if query_result !=None:
                analyse_result = query_result
            else:
                analyse_result = A.inquire_idiom(query)
        elif type == "words":
            path =WORDS_PATH
            path = os.path.join(path,"词库")
            query_list = J.read_json_file(path,"query")
            query_result =J.find_in_json(query_list,'word',query)
            print(f"'{query}'-本地词语查询结果：{query_result}")
            if query_result !=None:
                analyse_result = query_result
            else:
                analyse_result = A.inquire_words(query)
        # print(analyse_result)
        list=[]
        list.append(analyse_result)
        result = REST_API_standard(
            code=200,
            message=("succeed"),
            data = list
        )
        return result
    except Exception as e:
        error = ErrorResponse(code=500, message=f"analyse failed: {e}")
        return JSONResponse(
            status_code=500,       # <-- HTTP 状态码
            content=error.model_dump()   # <-- 用 BaseModel 转 dict
        )
    
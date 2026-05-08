from typing import Union,Generic, TypeVar
import uvicorn
import os
from typing import List
from fastapi import FastAPI,APIRouter, File, UploadFile, HTTPException,Path, Request ,Form
from pydantic import BaseModel , Field
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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


class AnalyseRequest(BaseModel):
    filename:str


@router.post("/analyse")
async def get_analyse():
    return "analyse API"
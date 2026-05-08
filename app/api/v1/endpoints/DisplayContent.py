from enum import Enum
from typing import Generic, TypeVar

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import storage
from app.auth import _current_user


router = APIRouter()
T = TypeVar("T")

IDIOM_PATH = "static/data/idiom"
WORDS_PATH = "static/data/words"


class REST_API_standard(BaseModel, Generic[T]):
    code: int
    message: str
    data: T


class ErrorResponse(BaseModel):
    code: int
    message: str


class limit(str, Enum):
    idiom = "idiom"
    words = "words"


class FavoriteListRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    BookName: str = Field(default="词库")


class CreateFavoriteRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    BookName: str = Field()


def _owner_user_id(request: Request) -> str | None:
    user = _current_user(request)
    if not user:
        return None
    user_id = str(user.get("user_id", "")).strip()
    return user_id or None


def _type_value(value: limit | str) -> str:
    return value.value if isinstance(value, limit) else str(value)


def _error_response(exc: Exception) -> JSONResponse:
    error = ErrorResponse(code=500, message=f"analyse failed: {exc}")
    return JSONResponse(status_code=500, content=error.model_dump())


@router.post("/FavoriteList", response_model=REST_API_standard)
async def FavoriteList(payload: FavoriteListRequest, http_request: Request):
    try:
        categories = storage.list_categories(
            _owner_user_id(http_request),
            _type_value(payload.TypeName),
            payload.BookName,
        )
        return REST_API_standard(
            code=200,
            message="succeed",
            data={"FavoriteList_list": categories},
        )
    except Exception as exc:
        return _error_response(exc)


@router.post("/BookshelfList", response_model=REST_API_standard)
async def BookshelfList(http_request: Request):
    try:
        owner_user_id = _owner_user_id(http_request)
        return REST_API_standard(
            code=200,
            message="succeed",
            data={
                "idiom_BookshelfList_list": storage.list_books(owner_user_id, "idiom"),
                "words_BookshelfList_list": storage.list_books(owner_user_id, "words"),
            },
        )
    except Exception as exc:
        return _error_response(exc)


@router.post("/CreateBook", response_model=REST_API_standard)
async def CreateBook(payload: CreateFavoriteRequest, http_request: Request):
    try:
        owner_user_id = _owner_user_id(http_request)
        type_name = _type_value(payload.TypeName)
        storage.create_book(owner_user_id, type_name, payload.BookName)
        return REST_API_standard(
            code=200,
            message="succeed",
            data=storage.list_books(owner_user_id, type_name),
        )
    except Exception as exc:
        return _error_response(exc)

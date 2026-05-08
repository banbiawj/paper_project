from enum import Enum
from typing import Any, Generic, TypeVar

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


class CreateFavoriteRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    FavoriteName: str = Field()
    PresentPath: str = Field()


class SaveDataRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    FavoriteName: str = "default"
    PresentPath: str
    message: dict[str, Any]


class ReadDataRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    FavoriteName: str = Field()
    PresentPath: str = Field()


class DeleteDataRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    FavoriteName: str = "default"
    PresentPath: str
    message: dict[str, Any]


class AlterDataRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    FavoriteName: str = "default"
    PresentPath: str
    message: dict[str, Any]


def _owner_user_id(request: Request) -> str | None:
    user = _current_user(request)
    if not user:
        return None
    user_id = str(user.get("user_id", "")).strip()
    return user_id or None


def _type_value(value: limit | str) -> str:
    return value.value if isinstance(value, limit) else str(value)


def _sqlite_uri(type_name: str, book: str, category: str) -> str:
    return f"sqlite://{type_name}/{book}/{category}"


def _sync_entry_to_shared(
    owner_user_id: str | None,
    type_name: str,
    book: str,
    category: str,
    entry: dict[str, Any],
) -> None:
    if owner_user_id is None:
        return
    storage.create_book(None, type_name, book)
    storage.create_category(None, type_name, book, category)
    storage.save_entry(None, type_name, book, category, entry)


def _error_response(exc: Exception) -> JSONResponse:
    error = ErrorResponse(code=500, message=f"analyse failed: {exc}")
    return JSONResponse(status_code=500, content=error.model_dump())


@router.post("/CreateFavorite", response_model=REST_API_standard)
async def CreateFavorite(payload: CreateFavoriteRequest, http_request: Request):
    try:
        type_name = _type_value(payload.TypeName)
        category = storage.create_category(
            _owner_user_id(http_request),
            type_name,
            payload.PresentPath,
            payload.FavoriteName,
        )["category"]
        return REST_API_standard(
            code=200,
            message="succeed",
            data=_sqlite_uri(type_name, payload.PresentPath, category),
        )
    except Exception as exc:
        return _error_response(exc)


@router.post("/SaveData", response_model=REST_API_standard)
async def SaveData(payload: SaveDataRequest, http_request: Request):
    try:
        type_name = _type_value(payload.TypeName)
        owner_user_id = _owner_user_id(http_request)
        entry, created = storage.save_entry(
            owner_user_id,
            type_name,
            payload.PresentPath,
            payload.FavoriteName,
            payload.message,
        )
        _sync_entry_to_shared(
            owner_user_id,
            type_name,
            payload.PresentPath,
            payload.FavoriteName,
            payload.message,
        )
        if not created:
            return REST_API_standard(code=200, message="already exist!", data=entry)
        return REST_API_standard(
            code=200,
            message="Save succeed!",
            data=_sqlite_uri(type_name, payload.PresentPath, payload.FavoriteName),
        )
    except Exception as exc:
        return _error_response(exc)


@router.post("/ReadData", response_model=REST_API_standard)
async def ReadData(payload: ReadDataRequest, http_request: Request):
    try:
        rows = storage.read_entries(
            _owner_user_id(http_request),
            _type_value(payload.TypeName),
            payload.PresentPath,
            payload.FavoriteName,
        )
        return REST_API_standard(code=200, message="succeed", data=rows)
    except Exception as exc:
        return _error_response(exc)


@router.post("/DeleteData", response_model=REST_API_standard)
async def DeleteData(payload: DeleteDataRequest, http_request: Request):
    try:
        word = str(payload.message.get("word", "")).strip()
        rows = storage.delete_entry_from_category(
            _owner_user_id(http_request),
            _type_value(payload.TypeName),
            payload.PresentPath,
            payload.FavoriteName,
            word,
        )
        return REST_API_standard(code=200, message="delete succeed!", data=rows)
    except Exception as exc:
        return _error_response(exc)


@router.post("/alterData", response_model=REST_API_standard)
async def alterData(payload: AlterDataRequest, http_request: Request):
    try:
        original_word = str(payload.message.get("word", "")).strip()
        owner_user_id = _owner_user_id(http_request)
        storage.replace_entry(
            owner_user_id,
            _type_value(payload.TypeName),
            payload.PresentPath,
            original_word,
            payload.message,
        )
        _sync_entry_to_shared(
            owner_user_id,
            _type_value(payload.TypeName),
            payload.PresentPath,
            payload.FavoriteName,
            payload.message,
        )
        return REST_API_standard(code=200, message="alter succeed!", data=None)
    except Exception as exc:
        return _error_response(exc)

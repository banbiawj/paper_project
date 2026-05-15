from enum import Enum
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import storage
from app.auth import _current_user
from mylib.Agent import inquire as agent_inquire


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


class InquireRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    InquireContent: str


class CompareRequest(BaseModel):
    TypeName: limit = Field(default=limit.idiom)
    items: list[dict[str, Any]]


def _owner_user_id(request: Request) -> str | None:
    user = _current_user(request)
    if not user:
        return None
    user_id = str(user.get("user_id", "")).strip()
    return user_id or None


def _type_value(value: limit | str) -> str:
    return value.value if isinstance(value, limit) else str(value)


def _compare_error(message: str, status_code: int = 400) -> JSONResponse:
    error = ErrorResponse(code=status_code, message=message)
    return JSONResponse(status_code=status_code, content=error.model_dump())


def _validated_compare_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(items) < 2:
        raise ValueError("compare requires at least two entries")
    validated = []
    for item in items:
        word = str(item.get("word", "")).strip()
        if not word:
            raise ValueError("each compare entry requires word")
        validated.append(dict(item, word=word))
    return validated


@router.post("/query", response_model=REST_API_standard)
async def inquire_idiom(payload: InquireRequest, http_request: Request):
    try:
        query = payload.InquireContent
        type_name = _type_value(payload.TypeName)
        owner_user_id = _owner_user_id(http_request)
        local_result = storage.find_entry_in_type(owner_user_id, type_name, query)
        if local_result is None and owner_user_id is not None:
            local_result = storage.find_entry_in_type(None, type_name, query)
        if local_result is not None:
            analyse_result = local_result
        elif type_name == "idiom":
            analyse_result = agent_inquire.inquire_idiom(query)
        else:
            analyse_result = agent_inquire.inquire_words(query)
        if not isinstance(analyse_result, dict):
            raise ValueError("AI returned no result")

        return REST_API_standard(code=200, message="succeed", data=[analyse_result])
    except Exception as exc:
        error = ErrorResponse(code=500, message=f"analyse failed: {exc}")
        return JSONResponse(status_code=500, content=error.model_dump())


@router.post("/compare", response_model=REST_API_standard)
async def compare_entries(payload: CompareRequest):
    try:
        type_name = _type_value(payload.TypeName)
        items = _validated_compare_items(payload.items)
    except ValueError as exc:
        return _compare_error(str(exc))

    try:
        result = agent_inquire.compare_entries(type_name, items)
        if not isinstance(result, dict):
            raise ValueError("AI returned no comparison")
        return REST_API_standard(code=200, message="succeed", data=result)
    except Exception as exc:
        error = ErrorResponse(code=500, message=f"compare failed: {exc}")
        return JSONResponse(status_code=500, content=error.model_dump())

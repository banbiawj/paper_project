from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import storage
from app.auth import _current_admin, _now_string, _public_user


router = APIRouter()

VALID_TYPES = {"idiom": "成语", "words": "词语"}
SPECIAL_CATEGORIES = {"query.json": 0, "default.json": 1}


class BookRequest(BaseModel):
    type_name: str = Field(default="idiom")
    book: str


class CategoryRequest(BaseModel):
    type_name: str = Field(default="idiom")
    book: str
    category: str


class EntryCreateRequest(BaseModel):
    type_name: str = Field(default="idiom")
    book: str
    category: str
    entry: dict[str, Any]


class EntryUpdateRequest(EntryCreateRequest):
    original_word: str


class EntryDeleteRequest(BaseModel):
    type_name: str = Field(default="idiom")
    book: str
    category: str
    word: str


class UserStatusRequest(BaseModel):
    status: str


def _ok(data: Any, message: str = "succeed") -> dict[str, Any]:
    return {"code": 200, "message": message, "data": data}


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "message": message, "data": None},
    )


def _auth_error(request: Request) -> JSONResponse | None:
    if _current_admin(request):
        return None
    return _error(401, "未登录或登录已过期")


def _validate_type(type_name: str) -> str:
    value = (type_name or "").strip()
    if value not in VALID_TYPES:
        raise ValueError("类型只能是 idiom 或 words")
    return value


def _validate_name(value: str, label: str, *, json_file: bool = False) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{label}不能为空")
    if cleaned in {".", ".."} or ".." in cleaned:
        raise ValueError(f"{label}不能包含非法路径")
    if json_file and not cleaned.endswith(".json"):
        cleaned = f"{cleaned}.json"
    return cleaned


def _entry_matches_keyword(entry: dict[str, Any], keyword: str) -> bool:
    if not keyword:
        return True
    lowered = keyword.lower()
    return any(lowered in str(value).lower() for value in entry.values())


def _handle_exception(exc: Exception) -> JSONResponse:
    if isinstance(exc, ValueError):
        return _error(400, str(exc))
    if isinstance(exc, FileNotFoundError):
        return _error(404, str(exc))
    return _error(500, f"admin api failed: {exc}")


def _book_payload(type_name: str, book: str) -> dict[str, Any]:
    categories = storage.list_categories(None, type_name, book)
    try:
        entry_count = len(storage.read_entries(None, type_name, book, "query.json"))
    except FileNotFoundError:
        entry_count = 0
    return {
        "name": book,
        "categories": categories,
        "entry_count": entry_count,
    }


def _library_payload(type_name: str) -> dict[str, Any]:
    type_name = _validate_type(type_name)
    books = [_book_payload(type_name, book) for book in storage.list_books(None, type_name)]
    return {
        "type_name": type_name,
        "type_label": VALID_TYPES[type_name],
        "books": books,
        "book_count": len(books),
        "category_count": sum(len(book["categories"]) for book in books),
    }


def _summary_payload() -> dict[str, Any]:
    book_count = 0
    category_count = 0
    entry_count = 0
    recent_entries: list[dict[str, Any]] = []

    for type_name in VALID_TYPES:
        for book in storage.list_books(None, type_name):
            book_count += 1
            categories = storage.list_categories(None, type_name, book)
            category_count += len(categories)
            if "query.json" in categories:
                rows = storage.read_entries(None, type_name, book, "query.json")
                entry_count += len(rows)
                source_category = "query.json"
            else:
                rows = []
                source_category = categories[0] if categories else "query.json"
                for category in categories:
                    category_rows = storage.read_entries(None, type_name, book, category)
                    entry_count += len(category_rows)
                    rows.extend(category_rows)
            for entry in reversed(rows[-4:]):
                recent_entries.append(
                    {
                        "word": entry.get("word", ""),
                        "explain": entry.get("explain", ""),
                        "type_name": type_name,
                        "type_label": VALID_TYPES[type_name],
                        "book": book,
                        "category": source_category,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

    return {
        "entry_count": entry_count,
        "book_count": book_count,
        "category_count": category_count,
        "recent_entries": recent_entries[:8],
    }


@router.get("/users")
async def users(request: Request):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        return _ok({"users": [_public_user(user) for user in storage.list_users()]})
    except Exception as exc:
        return _handle_exception(exc)


@router.patch("/users/{user_id}")
async def update_user_status(
    request: Request,
    user_id: str,
    payload: UserStatusRequest,
):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        status = (payload.status or "").strip()
        if status not in {"active", "disabled"}:
            raise ValueError("用户状态只能是 active 或 disabled")
        user = storage.update_user_status(user_id, status, _now_string())
        if not user:
            return _error(404, "用户不存在")
        return _ok({"user": _public_user(user)}, "user updated")
    except Exception as exc:
        return _handle_exception(exc)


@router.delete("/users/{user_id}")
async def delete_user(request: Request, user_id: str):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        user = storage.delete_user(user_id)
        if not user:
            return _error(404, "用户不存在")
        return _ok({"user": _public_user(user)}, "user deleted")
    except Exception as exc:
        return _handle_exception(exc)


@router.get("/summary")
async def summary(request: Request):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        return _ok(_summary_payload())
    except Exception as exc:
        return _handle_exception(exc)


@router.get("/library")
async def library(request: Request, type_name: str = Query(default="idiom")):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        return _ok(_library_payload(type_name))
    except Exception as exc:
        return _handle_exception(exc)


@router.get("/entries")
async def entries(
    request: Request,
    type_name: str = Query(default="idiom"),
    book: str = Query(default="词库"),
    category: str = Query(default="query.json"),
    keyword: str = Query(default=""),
):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        type_name = _validate_type(type_name)
        book = _validate_name(book, "书籍名称")
        category = _validate_name(category, "分类名称", json_file=True)
        rows = [
            entry
            for entry in reversed(storage.read_entries(None, type_name, book, category))
            if _entry_matches_keyword(entry, keyword.strip())
        ]
        return _ok(
            {
                "type_name": type_name,
                "book": book,
                "category": category,
                "entries": rows,
                "count": len(rows),
            }
        )
    except Exception as exc:
        return _handle_exception(exc)


@router.post("/books")
async def create_book(request: Request, payload: BookRequest):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        type_name = _validate_type(payload.type_name)
        book = _validate_name(payload.book, "书籍名称")
        storage.create_book(None, type_name, book)
        return _ok(
            {
                "book": book,
                "categories": storage.list_categories(None, type_name, book),
                "library": _library_payload(type_name),
            },
            "book created",
        )
    except Exception as exc:
        return _handle_exception(exc)


@router.post("/categories")
async def create_category(request: Request, payload: CategoryRequest):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        type_name = _validate_type(payload.type_name)
        book = _validate_name(payload.book, "书籍名称")
        category = _validate_name(payload.category, "分类名称", json_file=True)
        if book not in storage.list_books(None, type_name):
            raise FileNotFoundError(f"书籍不存在: {book}")
        storage.create_category(None, type_name, book, category)
        return _ok(
            {
                "book": book,
                "category": category,
                "categories": storage.list_categories(None, type_name, book),
                "library": _library_payload(type_name),
            },
            "category created",
        )
    except Exception as exc:
        return _handle_exception(exc)


@router.post("/entries")
async def create_entry(request: Request, payload: EntryCreateRequest):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        type_name = _validate_type(payload.type_name)
        book = _validate_name(payload.book, "书籍名称")
        category = _validate_name(payload.category, "分类名称", json_file=True)
        if category not in storage.list_categories(None, type_name, book):
            raise FileNotFoundError(f"分类不存在: {category}")
        entry, created = storage.save_entry(None, type_name, book, category, payload.entry)
        if not created:
            return _error(400, "词条已存在于当前分类")
        return _ok({"entry": entry}, "entry created")
    except Exception as exc:
        return _handle_exception(exc)


@router.put("/entries")
async def update_entry(request: Request, payload: EntryUpdateRequest):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        type_name = _validate_type(payload.type_name)
        book = _validate_name(payload.book, "书籍名称")
        original_word = payload.original_word.strip()
        if not original_word:
            raise ValueError("原词条名称不能为空")
        entry = storage.replace_entry(
            None,
            type_name,
            book,
            original_word,
            payload.entry,
        )
        return _ok({"entry": entry}, "entry updated")
    except Exception as exc:
        return _handle_exception(exc)


@router.delete("/entries")
async def delete_entry(request: Request, payload: EntryDeleteRequest):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        type_name = _validate_type(payload.type_name)
        book = _validate_name(payload.book, "书籍名称")
        category = _validate_name(payload.category, "分类名称", json_file=True)
        word = payload.word.strip()
        if not word:
            raise ValueError("词条名称不能为空")
        if not storage.delete_entry_from_book(None, type_name, book, word):
            return _error(404, "词条不存在")
        remaining = storage.read_entries(None, type_name, book, category)
        return _ok({"entries": remaining, "count": len(remaining)}, "entry deleted")
    except Exception as exc:
        return _handle_exception(exc)

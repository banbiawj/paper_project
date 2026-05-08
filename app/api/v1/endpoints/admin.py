import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import _current_admin, _now_string, _public_user, _read_users, _write_users

router = APIRouter()

VALID_TYPES = {"idiom": "成语", "words": "词语"}
SPECIAL_CATEGORIES = {"query.json": 0, "default.json": 1}
INVALID_NAME_CHARS = set('/\\:*?"<>|\0')


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


def _data_root() -> Path:
    return Path(os.getenv("DS_MEMORY_DATA_ROOT", "static/data"))


def _validate_type(type_name: str) -> str:
    value = (type_name or "").strip()
    if value not in VALID_TYPES:
        raise ValueError("类型只能是 idiom 或 words")
    return value


def _validate_path_part(value: str, label: str, *, json_file: bool = False) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{label}不能为空")
    if cleaned in {".", ".."} or ".." in cleaned:
        raise ValueError(f"{label}不能包含非法路径")
    if any(char in INVALID_NAME_CHARS for char in cleaned):
        raise ValueError(f"{label}包含非法字符")
    if json_file and not cleaned.endswith(".json"):
        cleaned = f"{cleaned}.json"
    if json_file and cleaned == ".json":
        raise ValueError(f"{label}不能为空")
    return cleaned


def _type_dir(type_name: str) -> Path:
    return _data_root() / _validate_type(type_name)


def _book_dir(type_name: str, book: str) -> Path:
    return _type_dir(type_name) / _validate_path_part(book, "书籍名称")


def _category_file(type_name: str, book: str, category: str) -> Path:
    return _book_dir(type_name, book) / _validate_path_part(
        category,
        "分类名称",
        json_file=True,
    )


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path.name}")
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{path.name} 必须是列表 JSON")
    return [item for item in data if isinstance(item, dict)]


def _write_json_list(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


def _ensure_json_file(path: Path) -> None:
    if not path.exists():
        _write_json_list(path, [])


def _list_book_paths(type_name: str) -> list[Path]:
    type_path = _type_dir(type_name)
    if not type_path.exists():
        return []
    return sorted(
        [path for path in type_path.iterdir() if path.is_dir()],
        key=lambda path: path.name.lower(),
    )


def _sort_category_name(name: str) -> tuple[int, str]:
    return (SPECIAL_CATEGORIES.get(name, 10), name.lower())


def _list_category_paths(book_path: Path) -> list[Path]:
    if not book_path.exists():
        return []
    return sorted(
        [
            path
            for path in book_path.iterdir()
            if path.is_file() and path.suffix.lower() == ".json"
        ],
        key=lambda path: _sort_category_name(path.name),
    )


def _read_entries_if_exists(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return _read_json_list(path)


def _find_entry_index(entries: list[dict[str, Any]], word: str) -> int | None:
    for index, entry in enumerate(entries):
        if str(entry.get("word", "")).strip() == word:
            return index
    return None


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    word = str(normalized.get("word", "")).strip()
    if not word:
        raise ValueError("词条名称不能为空")
    normalized["word"] = word
    normalized.setdefault("explain", "")
    normalized.setdefault("note", "")
    return normalized


def _append_entry_if_missing(path: Path, entry: dict[str, Any]) -> bool:
    entries = _read_entries_if_exists(path)
    if _find_entry_index(entries, entry["word"]) is not None:
        return False
    entries.append(entry)
    _write_json_list(path, entries)
    return True


def _remove_word_from_file(path: Path, word: str) -> bool:
    if not path.exists():
        return False
    entries = _read_json_list(path)
    filtered = [
        entry
        for entry in entries
        if str(entry.get("word", "")).strip() != word
    ]
    if len(filtered) == len(entries):
        return False
    _write_json_list(path, filtered)
    return True


def _replace_word_in_file(path: Path, original_word: str, entry: dict[str, Any]) -> bool:
    if not path.exists():
        return False
    entries = _read_json_list(path)
    changed = False
    for index, item in enumerate(entries):
        if str(item.get("word", "")).strip() == original_word:
            entries[index] = entry
            changed = True
    if changed:
        _write_json_list(path, entries)
    return changed


def _category_names(book_path: Path) -> list[str]:
    return [path.name for path in _list_category_paths(book_path)]


def _book_payload(type_name: str, book_path: Path) -> dict[str, Any]:
    categories = _category_names(book_path)
    query_entries = _read_entries_if_exists(book_path / "query.json")
    return {
        "name": book_path.name,
        "categories": categories,
        "entry_count": len(query_entries),
    }


def _library_payload(type_name: str) -> dict[str, Any]:
    books = [_book_payload(type_name, path) for path in _list_book_paths(type_name)]
    return {
        "type_name": type_name,
        "type_label": VALID_TYPES[type_name],
        "books": books,
        "book_count": len(books),
        "category_count": sum(len(book["categories"]) for book in books),
    }


def _entry_matches_keyword(entry: dict[str, Any], keyword: str) -> bool:
    if not keyword:
        return True
    lowered = keyword.lower()
    return any(lowered in str(value).lower() for value in entry.values())


def _format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _recent_entries_for_file(
    type_name: str,
    book_name: str,
    category_path: Path,
    limit: int = 4,
) -> list[dict[str, Any]]:
    entries = _read_entries_if_exists(category_path)
    updated_at = _format_timestamp(category_path.stat().st_mtime)
    rows = []
    for entry in reversed(entries[-limit:]):
        rows.append(
            {
                "word": entry.get("word", ""),
                "explain": entry.get("explain", ""),
                "type_name": type_name,
                "type_label": VALID_TYPES[type_name],
                "book": book_name,
                "category": category_path.name,
                "updated_at": updated_at,
                "timestamp": category_path.stat().st_mtime,
            }
        )
    return rows


def _summary_payload() -> dict[str, Any]:
    book_count = 0
    category_count = 0
    entry_count = 0
    recent_entries: list[dict[str, Any]] = []

    for type_name in VALID_TYPES:
        for book_path in _list_book_paths(type_name):
            book_count += 1
            category_paths = _list_category_paths(book_path)
            category_count += len(category_paths)

            query_path = book_path / "query.json"
            if query_path.exists():
                entry_count += len(_read_json_list(query_path))
                recent_entries.extend(
                    _recent_entries_for_file(type_name, book_path.name, query_path)
                )
            else:
                for category_path in category_paths:
                    entry_count += len(_read_entries_if_exists(category_path))
                    recent_entries.extend(
                        _recent_entries_for_file(
                            type_name,
                            book_path.name,
                            category_path,
                        )
                    )

    recent_entries.sort(key=lambda item: item["timestamp"], reverse=True)
    for item in recent_entries:
        item.pop("timestamp", None)

    return {
        "entry_count": entry_count,
        "book_count": book_count,
        "category_count": category_count,
        "recent_entries": recent_entries[:8],
    }


def _handle_exception(exc: Exception) -> JSONResponse:
    if isinstance(exc, ValueError):
        return _error(400, str(exc))
    if isinstance(exc, FileNotFoundError):
        return _error(404, str(exc))
    return _error(500, f"admin api failed: {exc}")


@router.get("/users")
async def users(request: Request):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        return _ok({"users": [_public_user(user) for user in _read_users()]})
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

        users = _read_users()
        now = _now_string()
        for user in users:
            if str(user.get("id", "")) == user_id:
                user["status"] = status
                user["updated_at"] = now
                _write_users(users)
                return _ok({"user": _public_user(user)}, "user updated")
        return _error(404, "用户不存在")
    except Exception as exc:
        return _handle_exception(exc)


@router.delete("/users/{user_id}")
async def delete_user(request: Request, user_id: str):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        users = _read_users()
        kept_users = []
        deleted_user = None
        for user in users:
            if str(user.get("id", "")) == user_id:
                deleted_user = user
            else:
                kept_users.append(user)

        if not deleted_user:
            return _error(404, "用户不存在")

        _write_users(kept_users)
        return _ok({"user": _public_user(deleted_user)}, "user deleted")
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
        return _ok(_library_payload(_validate_type(type_name)))
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
        path = _category_file(type_name, book, category)
        rows = [
            entry
            for entry in reversed(_read_json_list(path))
            if _entry_matches_keyword(entry, keyword.strip())
        ]
        return _ok(
            {
                "type_name": _validate_type(type_name),
                "book": _validate_path_part(book, "书籍名称"),
                "category": _validate_path_part(category, "分类名称", json_file=True),
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
        book_path = _book_dir(type_name, payload.book)
        book_path.mkdir(parents=True, exist_ok=True)
        _ensure_json_file(book_path / "query.json")
        _ensure_json_file(book_path / "default.json")
        return _ok(
            {
                "book": book_path.name,
                "categories": _category_names(book_path),
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
        book_path = _book_dir(type_name, payload.book)
        if not book_path.exists():
            raise FileNotFoundError(f"书籍不存在: {payload.book}")
        category_path = _category_file(type_name, payload.book, payload.category)
        _ensure_json_file(category_path)
        return _ok(
            {
                "book": book_path.name,
                "category": category_path.name,
                "categories": _category_names(book_path),
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
        book_path = _book_dir(type_name, payload.book)
        if not book_path.exists():
            raise FileNotFoundError(f"书籍不存在: {payload.book}")

        category_path = _category_file(type_name, payload.book, payload.category)
        if not category_path.exists():
            raise FileNotFoundError(f"分类不存在: {payload.category}")

        entry = _normalize_entry(payload.entry)
        selected_entries = _read_json_list(category_path)
        if _find_entry_index(selected_entries, entry["word"]) is not None:
            return _error(400, "词条已存在于当前分类")

        selected_entries.append(entry)
        _write_json_list(category_path, selected_entries)

        query_path = book_path / "query.json"
        default_path = book_path / "default.json"
        _ensure_json_file(query_path)
        _ensure_json_file(default_path)

        if category_path.name != "query.json":
            _append_entry_if_missing(query_path, entry)
        if category_path.name == "query.json":
            _append_entry_if_missing(default_path, entry)
        elif category_path.name not in {"default.json", "query.json"}:
            _remove_word_from_file(default_path, entry["word"])

        return _ok({"entry": entry}, "entry created")
    except Exception as exc:
        return _handle_exception(exc)


@router.put("/entries")
async def update_entry(request: Request, payload: EntryUpdateRequest):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        book_path = _book_dir(payload.type_name, payload.book)
        if not book_path.exists():
            raise FileNotFoundError(f"书籍不存在: {payload.book}")

        original_word = payload.original_word.strip()
        if not original_word:
            raise ValueError("原词条名称不能为空")

        entry = _normalize_entry(payload.entry)
        if entry["word"] != original_word:
            for category_path in _list_category_paths(book_path):
                for item in _read_json_list(category_path):
                    item_word = str(item.get("word", "")).strip()
                    if item_word == entry["word"] and item_word != original_word:
                        return _error(400, "新的词条名称已存在")

        changed = False
        for category_path in _list_category_paths(book_path):
            changed = _replace_word_in_file(category_path, original_word, entry) or changed

        if not changed:
            return _error(404, "词条不存在")

        return _ok({"entry": entry}, "entry updated")
    except Exception as exc:
        return _handle_exception(exc)


@router.delete("/entries")
async def delete_entry(request: Request, payload: EntryDeleteRequest):
    if auth_error := _auth_error(request):
        return auth_error
    try:
        book_path = _book_dir(payload.type_name, payload.book)
        if not book_path.exists():
            raise FileNotFoundError(f"书籍不存在: {payload.book}")

        word = payload.word.strip()
        if not word:
            raise ValueError("词条名称不能为空")

        changed = False
        for category_path in _list_category_paths(book_path):
            changed = _remove_word_from_file(category_path, word) or changed

        if not changed:
            return _error(404, "词条不存在")

        selected_path = _category_file(payload.type_name, payload.book, payload.category)
        remaining = _read_entries_if_exists(selected_path)
        return _ok({"entries": remaining, "count": len(remaining)}, "entry deleted")
    except Exception as exc:
        return _handle_exception(exc)

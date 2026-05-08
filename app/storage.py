import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_TYPES = ("idiom", "words")
SPECIAL_CATEGORIES = {"query.json": 0, "default.json": 1}
DEFAULT_BOOK_NAME = "词库"


def _now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def data_root() -> Path:
    return Path(os.getenv("DS_MEMORY_DATA_ROOT", "static/data"))


def db_path() -> Path:
    configured = os.getenv("DS_MEMORY_DB_PATH")
    if configured:
        return Path(configured)
    return data_root() / "ds_memory.sqlite3"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = MEMORY").close()
    connection.execute("PRAGMA foreign_keys = ON").close()
    return connection


@contextmanager
def connection_scope():
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with connection_scope() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS libraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id TEXT NULL REFERENCES users(id) ON DELETE CASCADE,
                type_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_libraries_shared_type
                ON libraries(type_name)
                WHERE owner_user_id IS NULL;

            CREATE UNIQUE INDEX IF NOT EXISTS idx_libraries_user_type
                ON libraries(owner_user_id, type_name)
                WHERE owner_user_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(library_id, name)
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(book_id, name)
            );

            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                word TEXT NOT NULL,
                explain TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                extra_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(book_id, word)
            );

            CREATE TABLE IF NOT EXISTS category_entries (
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                PRIMARY KEY(category_id, entry_id)
            );
            """
        )


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _normalize_type(type_name: str) -> str:
    value = (type_name or "").strip()
    if value not in VALID_TYPES:
        raise ValueError("type_name must be idiom or words")
    return value


def _normalize_name(value: str, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{label} cannot be empty")
    if cleaned in {".", ".."} or ".." in cleaned:
        raise ValueError(f"{label} cannot contain traversal")
    return cleaned


def _normalize_category(value: str) -> str:
    cleaned = _normalize_name(value, "category")
    if not cleaned.endswith(".json"):
        cleaned = f"{cleaned}.json"
    return cleaned


def _sort_category_key(name: str) -> tuple[int, str]:
    return (SPECIAL_CATEGORIES.get(name, 10), name.lower())


def _entry_to_payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        extra = json.loads(row["extra_json"] or "{}")
    except json.JSONDecodeError:
        extra = {}
    if not isinstance(extra, dict):
        extra = {}
    payload = dict(extra)
    payload["word"] = row["word"]
    payload["explain"] = row["explain"]
    payload["note"] = row["note"]
    return payload


def _normalize_entry(entry: dict[str, Any]) -> tuple[str, str, str, str]:
    if not isinstance(entry, dict):
        raise ValueError("entry must be an object")
    word = str(entry.get("word", "")).strip()
    if not word:
        raise ValueError("entry word cannot be empty")
    explain = str(entry.get("explain", ""))
    note = str(entry.get("note", ""))
    extra = {
        key: value
        for key, value in entry.items()
        if key not in {"word", "explain", "note"}
    }
    return word, explain, note, json.dumps(extra, ensure_ascii=False, sort_keys=True)


def _user_exists(connection: sqlite3.Connection, user_id: str) -> bool:
    return (
        connection.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
        is not None
    )


def _library_id(
    connection: sqlite3.Connection,
    owner_user_id: str | None,
    type_name: str,
) -> int | None:
    type_name = _normalize_type(type_name)
    if owner_user_id is None:
        row = connection.execute(
            "SELECT id FROM libraries WHERE owner_user_id IS NULL AND type_name = ?",
            (type_name,),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT id FROM libraries WHERE owner_user_id = ? AND type_name = ?",
            (owner_user_id, type_name),
        ).fetchone()
    return None if row is None else int(row["id"])


def _ensure_library(
    connection: sqlite3.Connection,
    owner_user_id: str | None,
    type_name: str,
    counts: dict[str, Any] | None = None,
) -> int:
    existing = _library_id(connection, owner_user_id, type_name)
    if existing is not None:
        return existing
    if owner_user_id is not None and not _user_exists(connection, owner_user_id):
        raise FileNotFoundError(f"user does not exist: {owner_user_id}")
    now = _now_string()
    cursor = connection.execute(
        """
        INSERT INTO libraries (owner_user_id, type_name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (owner_user_id, _normalize_type(type_name), now, now),
    )
    return int(cursor.lastrowid)


def _book_id(connection: sqlite3.Connection, library_id: int, book: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM books WHERE library_id = ? AND name = ?",
        (library_id, _normalize_name(book, "book")),
    ).fetchone()
    return None if row is None else int(row["id"])


def _ensure_book(
    connection: sqlite3.Connection,
    library_id: int,
    book: str,
    counts: dict[str, Any] | None = None,
) -> int:
    name = _normalize_name(book, "book")
    existing = _book_id(connection, library_id, name)
    if existing is not None:
        return existing
    now = _now_string()
    cursor = connection.execute(
        """
        INSERT INTO books (library_id, name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (library_id, name, now, now),
    )
    if counts is not None:
        counts["books"] += 1
    return int(cursor.lastrowid)


def _category_id(connection: sqlite3.Connection, book_id: int, category: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM categories WHERE book_id = ? AND name = ?",
        (book_id, _normalize_category(category)),
    ).fetchone()
    return None if row is None else int(row["id"])


def _ensure_category(
    connection: sqlite3.Connection,
    book_id: int,
    category: str,
    counts: dict[str, Any] | None = None,
) -> int:
    name = _normalize_category(category)
    existing = _category_id(connection, book_id, name)
    if existing is not None:
        return existing
    now = _now_string()
    cursor = connection.execute(
        """
        INSERT INTO categories (book_id, name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (book_id, name, now, now),
    )
    if counts is not None:
        counts["categories"] += 1
    return int(cursor.lastrowid)


def _entry_id(connection: sqlite3.Connection, book_id: int, word: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM entries WHERE book_id = ? AND word = ?",
        (book_id, word),
    ).fetchone()
    return None if row is None else int(row["id"])


def _upsert_entry(
    connection: sqlite3.Connection,
    book_id: int,
    entry: dict[str, Any],
    counts: dict[str, Any] | None = None,
) -> int:
    word, explain, note, extra_json = _normalize_entry(entry)
    existing = _entry_id(connection, book_id, word)
    now = _now_string()
    if existing is not None:
        connection.execute(
            """
            UPDATE entries
            SET explain = ?, note = ?, extra_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (explain, note, extra_json, now, existing),
        )
        return existing
    cursor = connection.execute(
        """
        INSERT INTO entries (book_id, word, explain, note, extra_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (book_id, word, explain, note, extra_json, now, now),
    )
    if counts is not None:
        counts["entries"] += 1
    return int(cursor.lastrowid)


def _next_position(connection: sqlite3.Connection, category_id: int) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 AS next_position FROM category_entries WHERE category_id = ?",
        (category_id,),
    ).fetchone()
    return int(row["next_position"])


def _link_entry(
    connection: sqlite3.Connection,
    category_id: int,
    entry_id: int,
    position: int | None = None,
    counts: dict[str, Any] | None = None,
) -> bool:
    existing = connection.execute(
        """
        SELECT 1 FROM category_entries
        WHERE category_id = ? AND entry_id = ?
        """,
        (category_id, entry_id),
    ).fetchone()
    if existing is not None:
        if position is not None:
            connection.execute(
                """
                UPDATE category_entries
                SET position = ?
                WHERE category_id = ? AND entry_id = ?
                """,
                (position, category_id, entry_id),
            )
        return False
    now = _now_string()
    connection.execute(
        """
        INSERT INTO category_entries (category_id, entry_id, position, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            category_id,
            entry_id,
            _next_position(connection, category_id) if position is None else position,
            now,
        ),
    )
    if counts is not None:
        counts["category_links"] += 1
    return True


def _read_json(path: Path, counts: dict[str, Any]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        counts["warnings"].append(f"{path}: {exc}")
        return None


def _upsert_user(connection: sqlite3.Connection, user: dict[str, Any]) -> bool:
    user_id = str(user.get("id", "")).strip()
    username = str(user.get("username", "")).strip()
    email = str(user.get("email", "")).strip().lower()
    password_hash = str(user.get("password_hash", ""))
    if not user_id or not username or not email or not password_hash:
        raise ValueError("user requires id, username, email, and password_hash")

    existing = _user_exists(connection, user_id)
    now = _now_string()
    values = {
        "id": user_id,
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "role": str(user.get("role", "user") or "user"),
        "status": str(user.get("status", "active") or "active"),
        "created_at": str(user.get("created_at", "") or now),
        "updated_at": str(user.get("updated_at", "") or now),
        "last_login_at": str(user.get("last_login_at", "") or ""),
    }
    connection.execute(
        """
        INSERT INTO users (
            id, username, email, password_hash, role, status,
            created_at, updated_at, last_login_at
        )
        VALUES (
            :id, :username, :email, :password_hash, :role, :status,
            :created_at, :updated_at, :last_login_at
        )
        ON CONFLICT(id) DO UPDATE SET
            username = excluded.username,
            email = excluded.email,
            password_hash = excluded.password_hash,
            role = excluded.role,
            status = excluded.status,
            created_at = excluded.created_at,
            updated_at = excluded.updated_at,
            last_login_at = excluded.last_login_at
        """,
        values,
    )
    return not existing


def _import_users(connection: sqlite3.Connection, root: Path, counts: dict[str, Any]) -> None:
    path = root / "users.json"
    if not path.exists():
        return
    users = _read_json(path, counts)
    if not isinstance(users, list):
        counts["warnings"].append(f"{path}: expected a JSON list")
        return
    for user in users:
        if not isinstance(user, dict):
            counts["warnings"].append(f"{path}: skipped non-object user")
            continue
        try:
            if _upsert_user(connection, user):
                counts["users"] += 1
        except (sqlite3.IntegrityError, ValueError) as exc:
            counts["warnings"].append(f"{path}: skipped user {user!r}: {exc}")


def _import_category_file(
    connection: sqlite3.Connection,
    book_id: int,
    category_path: Path,
    counts: dict[str, Any],
) -> None:
    category_id = _ensure_category(connection, book_id, category_path.name, counts)
    entries = _read_json(category_path, counts)
    if entries is None:
        return
    if not isinstance(entries, list):
        counts["warnings"].append(f"{category_path}: expected a JSON list")
        return
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            counts["warnings"].append(f"{category_path}: skipped non-object entry")
            continue
        try:
            entry_id = _upsert_entry(connection, book_id, entry, counts)
            _link_entry(connection, category_id, entry_id, position, counts)
        except ValueError as exc:
            counts["warnings"].append(f"{category_path}: skipped entry {entry!r}: {exc}")


def _import_library_dir(
    connection: sqlite3.Connection,
    owner_user_id: str | None,
    type_name: str,
    root: Path,
    counts: dict[str, Any],
) -> None:
    if not root.exists():
        return
    library_id = _ensure_library(connection, owner_user_id, type_name)
    for book_path in sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.name.lower()):
        book_id = _ensure_book(connection, library_id, book_path.name, counts)
        category_paths = [
            path
            for path in book_path.iterdir()
            if path.is_file() and path.suffix.lower() == ".json"
        ]
        for category_path in sorted(category_paths, key=lambda path: _sort_category_key(path.name)):
            _import_category_file(connection, book_id, category_path, counts)


def migrate_json_to_sqlite(root: Path | None = None) -> dict[str, Any]:
    init_db()
    source_root = Path(root) if root is not None else data_root()
    counts: dict[str, Any] = {
        "users": 0,
        "books": 0,
        "categories": 0,
        "entries": 0,
        "category_links": 0,
        "warnings": [],
    }
    with connection_scope() as connection:
        _import_users(connection, source_root, counts)
        for type_name in VALID_TYPES:
            _import_library_dir(connection, None, type_name, source_root / type_name, counts)

        user_data_root = source_root / "user_data"
        if user_data_root.exists():
            for user_root in sorted([path for path in user_data_root.iterdir() if path.is_dir()], key=lambda path: path.name):
                if not _user_exists(connection, user_root.name):
                    counts["warnings"].append(f"{user_root}: skipped private data for missing user")
                    continue
                for type_name in VALID_TYPES:
                    _import_library_dir(
                        connection,
                        user_root.name,
                        type_name,
                        user_root / type_name,
                        counts,
                    )
    return counts


def list_users() -> list[dict[str, Any]]:
    init_db()
    with connection_scope() as connection:
        rows = connection.execute(
            """
            SELECT id, username, email, password_hash, role, status,
                   created_at, updated_at, last_login_at
            FROM users
            ORDER BY created_at, username
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    init_db()
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT id, username, email, password_hash, role, status,
                   created_at, updated_at, last_login_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return _row_to_dict(row)


def get_user_by_login(login: str) -> dict[str, Any] | None:
    value = (login or "").strip()
    if not value:
        return None
    init_db()
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT id, username, email, password_hash, role, status,
                   created_at, updated_at, last_login_at
            FROM users
            WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
            """,
            (value, value.lower()),
        ).fetchone()
    return _row_to_dict(row)


def save_user(user: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with connection_scope() as connection:
        _upsert_user(connection, user)
    saved = get_user_by_id(str(user.get("id", "")))
    if saved is None:
        raise FileNotFoundError("user was not saved")
    return saved


def replace_users(users: list[dict[str, Any]]) -> None:
    init_db()
    incoming_ids = {str(user.get("id", "")).strip() for user in users if isinstance(user, dict)}
    incoming_ids.discard("")
    with connection_scope() as connection:
        if incoming_ids:
            placeholders = ",".join("?" for _ in incoming_ids)
            connection.execute(
                f"DELETE FROM users WHERE id NOT IN ({placeholders})",
                tuple(incoming_ids),
            )
        else:
            connection.execute("DELETE FROM users")
        for user in users:
            if isinstance(user, dict):
                _upsert_user(connection, user)


def update_user_login(user_id: str, timestamp: str) -> None:
    init_db()
    with connection_scope() as connection:
        connection.execute(
            """
            UPDATE users
            SET last_login_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, user_id),
        )


def update_user_status(user_id: str, status: str, timestamp: str) -> dict[str, Any] | None:
    init_db()
    with connection_scope() as connection:
        connection.execute(
            """
            UPDATE users
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, timestamp, user_id),
        )
    return get_user_by_id(user_id)


def delete_user(user_id: str) -> dict[str, Any] | None:
    init_db()
    user = get_user_by_id(user_id)
    if not user:
        return None
    with connection_scope() as connection:
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return user


def _prepare_owner(owner_user_id: str | None) -> None:
    if owner_user_id:
        ensure_user_libraries(owner_user_id)


def _get_library_id_required(
    connection: sqlite3.Connection,
    owner_user_id: str | None,
    type_name: str,
) -> int:
    library_id = _library_id(connection, owner_user_id, type_name)
    if library_id is None:
        raise FileNotFoundError(f"library does not exist: {type_name}")
    return library_id


def _get_book_id_required(connection: sqlite3.Connection, library_id: int, book: str) -> int:
    book_id = _book_id(connection, library_id, book)
    if book_id is None:
        raise FileNotFoundError(f"book does not exist: {book}")
    return book_id


def _get_category_id_required(
    connection: sqlite3.Connection,
    book_id: int,
    category: str,
) -> int:
    category_id = _category_id(connection, book_id, category)
    if category_id is None:
        raise FileNotFoundError(f"category does not exist: {category}")
    return category_id


def list_books(owner_user_id: str | None, type_name: str) -> list[str]:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _library_id(connection, owner_user_id, type_name)
        if library_id is None:
            return []
        rows = connection.execute(
            "SELECT name FROM books WHERE library_id = ? ORDER BY LOWER(name)",
            (library_id,),
        ).fetchall()
    return [str(row["name"]) for row in rows]


def list_categories(owner_user_id: str | None, type_name: str, book: str) -> list[str]:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _library_id(connection, owner_user_id, type_name)
        if library_id is None:
            return []
        book_id = _book_id(connection, library_id, book)
        if book_id is None:
            return []
        rows = connection.execute(
            "SELECT name FROM categories WHERE book_id = ?",
            (book_id,),
        ).fetchall()
    return sorted([str(row["name"]) for row in rows], key=_sort_category_key)


def read_entries(
    owner_user_id: str | None,
    type_name: str,
    book: str,
    category: str,
) -> list[dict[str, Any]]:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _get_library_id_required(connection, owner_user_id, type_name)
        book_id = _get_book_id_required(connection, library_id, book)
        category_id = _get_category_id_required(connection, book_id, category)
        rows = connection.execute(
            """
            SELECT e.word, e.explain, e.note, e.extra_json
            FROM category_entries ce
            JOIN entries e ON e.id = ce.entry_id
            WHERE ce.category_id = ?
            ORDER BY ce.position, e.id
            """,
            (category_id,),
        ).fetchall()
    return [_entry_to_payload(row) for row in rows]


def _copy_shared_library(
    connection: sqlite3.Connection,
    user_id: str,
    type_name: str,
) -> None:
    private_id = _ensure_library(connection, user_id, type_name)
    shared_id = _library_id(connection, None, type_name)
    if shared_id is None:
        return

    shared_books = connection.execute(
        "SELECT id, name FROM books WHERE library_id = ? ORDER BY id",
        (shared_id,),
    ).fetchall()
    for shared_book in shared_books:
        private_book_id = _ensure_book(connection, private_id, shared_book["name"])
        shared_categories = connection.execute(
            "SELECT id, name FROM categories WHERE book_id = ? ORDER BY id",
            (shared_book["id"],),
        ).fetchall()
        category_map: dict[int, int] = {}
        for shared_category in shared_categories:
            category_map[int(shared_category["id"])] = _ensure_category(
                connection,
                private_book_id,
                shared_category["name"],
            )

        rows = connection.execute(
            """
            SELECT ce.category_id, ce.position, e.word, e.explain, e.note, e.extra_json
            FROM category_entries ce
            JOIN entries e ON e.id = ce.entry_id
            WHERE e.book_id = ?
            ORDER BY ce.category_id, ce.position, e.id
            """,
            (shared_book["id"],),
        ).fetchall()
        for row in rows:
            payload = _entry_to_payload(row)
            entry_id = _upsert_entry(connection, private_book_id, payload)
            _link_entry(
                connection,
                category_map[int(row["category_id"])],
                entry_id,
                int(row["position"]),
            )


def ensure_user_libraries(user_id: str) -> None:
    init_db()
    with connection_scope() as connection:
        if not _user_exists(connection, user_id):
            raise FileNotFoundError(f"user does not exist: {user_id}")
        for type_name in VALID_TYPES:
            if _library_id(connection, user_id, type_name) is None:
                library_id = _ensure_library(connection, user_id, type_name)
                book_id = _ensure_book(connection, library_id, DEFAULT_BOOK_NAME)
                _ensure_category(connection, book_id, "query.json")
                _ensure_category(connection, book_id, "default.json")


def create_book(owner_user_id: str | None, type_name: str, book: str) -> dict[str, Any]:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _ensure_library(connection, owner_user_id, type_name)
        book_id = _ensure_book(connection, library_id, book)
        _ensure_category(connection, book_id, "query.json")
        _ensure_category(connection, book_id, "default.json")
    return {"book": _normalize_name(book, "book")}


def create_category(
    owner_user_id: str | None,
    type_name: str,
    book: str,
    category: str,
) -> dict[str, Any]:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _get_library_id_required(connection, owner_user_id, type_name)
        book_id = _get_book_id_required(connection, library_id, book)
        _ensure_category(connection, book_id, category)
    return {"book": _normalize_name(book, "book"), "category": _normalize_category(category)}


def save_entry(
    owner_user_id: str | None,
    type_name: str,
    book: str,
    category: str,
    entry: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    _prepare_owner(owner_user_id)
    init_db()
    category_name = _normalize_category(category)
    with connection_scope() as connection:
        library_id = _get_library_id_required(connection, owner_user_id, type_name)
        book_id = _get_book_id_required(connection, library_id, book)
        category_id = _ensure_category(connection, book_id, category_name)
        query_id = _ensure_category(connection, book_id, "query.json")
        default_id = _ensure_category(connection, book_id, "default.json")
        entry_id = _upsert_entry(connection, book_id, entry)

        created = _link_entry(connection, category_id, entry_id)
        if category_name == "query.json":
            _link_entry(connection, default_id, entry_id)
        elif category_name == "default.json":
            _link_entry(connection, query_id, entry_id)
        else:
            connection.execute(
                """
                DELETE FROM category_entries
                WHERE category_id = ? AND entry_id = ?
                """,
                (default_id, entry_id),
            )
            _link_entry(connection, query_id, entry_id)

        row = connection.execute(
            "SELECT word, explain, note, extra_json FROM entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
    return _entry_to_payload(row), created


def delete_entry_from_category(
    owner_user_id: str | None,
    type_name: str,
    book: str,
    category: str,
    word: str,
) -> list[dict[str, Any]]:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _get_library_id_required(connection, owner_user_id, type_name)
        book_id = _get_book_id_required(connection, library_id, book)
        category_id = _get_category_id_required(connection, book_id, category)
        entry_id = _entry_id(connection, book_id, (word or "").strip())
        if entry_id is not None:
            connection.execute(
                """
                DELETE FROM category_entries
                WHERE category_id = ? AND entry_id = ?
                """,
                (category_id, entry_id),
            )
    return read_entries(owner_user_id, type_name, book, category)


def delete_entry_from_book(
    owner_user_id: str | None,
    type_name: str,
    book: str,
    word: str,
) -> bool:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _get_library_id_required(connection, owner_user_id, type_name)
        book_id = _get_book_id_required(connection, library_id, book)
        entry_id = _entry_id(connection, book_id, (word or "").strip())
        if entry_id is None:
            return False
        connection.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    return True


def replace_entry(
    owner_user_id: str | None,
    type_name: str,
    book: str,
    original_word: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    _prepare_owner(owner_user_id)
    init_db()
    original = (original_word or "").strip()
    if not original:
        raise ValueError("original word cannot be empty")
    word, explain, note, extra_json = _normalize_entry(entry)
    with connection_scope() as connection:
        library_id = _get_library_id_required(connection, owner_user_id, type_name)
        book_id = _get_book_id_required(connection, library_id, book)
        entry_id = _entry_id(connection, book_id, original)
        if entry_id is None:
            raise FileNotFoundError(f"entry does not exist: {original}")
        if word != original and _entry_id(connection, book_id, word) is not None:
            raise ValueError("entry already exists")
        now = _now_string()
        connection.execute(
            """
            UPDATE entries
            SET word = ?, explain = ?, note = ?, extra_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (word, explain, note, extra_json, now, entry_id),
        )
        row = connection.execute(
            "SELECT word, explain, note, extra_json FROM entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
    return _entry_to_payload(row)


def find_entry(
    owner_user_id: str | None,
    type_name: str,
    book: str,
    word: str,
) -> dict[str, Any] | None:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _library_id(connection, owner_user_id, type_name)
        if library_id is None:
            return None
        book_id = _book_id(connection, library_id, book)
        if book_id is None:
            return None
        row = connection.execute(
            """
            SELECT word, explain, note, extra_json
            FROM entries
            WHERE book_id = ? AND word = ?
            """,
            (book_id, (word or "").strip()),
        ).fetchone()
    return _entry_to_payload(row) if row else None


def find_entry_in_type(
    owner_user_id: str | None,
    type_name: str,
    word: str,
) -> dict[str, Any] | None:
    _prepare_owner(owner_user_id)
    init_db()
    with connection_scope() as connection:
        library_id = _library_id(connection, owner_user_id, type_name)
        if library_id is None:
            return None
        row = connection.execute(
            """
            SELECT e.word, e.explain, e.note, e.extra_json
            FROM entries e
            JOIN books b ON b.id = e.book_id
            WHERE b.library_id = ? AND e.word = ?
            ORDER BY b.id, e.id
            LIMIT 1
            """,
            (library_id, (word or "").strip()),
        ).fetchone()
    return _entry_to_payload(row) if row else None

# SQLite Storage Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace JSON runtime persistence with a SQLite-backed storage service while preserving the current HTTP API behavior.

**Architecture:** Add `app/storage.py` as the single persistence boundary using Python `sqlite3`. Auth, normal data APIs, inquiry lookup, and admin APIs call storage helpers instead of JSON helpers. Existing JSON files remain as migration input and backup.

**Tech Stack:** FastAPI, Python standard-library `sqlite3`, `unittest`, FastAPI `TestClient`.

---

## File Structure

- Create `app/storage.py`: connection handling, schema initialization, JSON migration, user CRUD, library/category/entry CRUD, user-private library initialization.
- Create `tests/test_storage.py`: focused storage-layer tests against temporary SQLite files and JSON fixture roots.
- Modify `app/auth.py`: replace JSON user helper internals with storage service calls; keep session and password helpers stable.
- Modify `app/api/v1/endpoints/DataOperate.py`: replace runtime JSON file operations with storage service calls for normal save/read/delete/update behavior.
- Modify `app/api/v1/endpoints/DisplayContent.py`: list books and categories from storage.
- Modify `app/api/v1/endpoints/inquire.py`: perform local lookup through storage.
- Modify `app/api/v1/endpoints/admin.py`: replace JSON-backed admin summary, library CRUD, entry CRUD, and user management with storage calls.
- Modify `.gitignore`: ignore SQLite runtime database files under `static/data`.

## Task 1: Storage Schema And Migration

**Files:**
- Create: `tests/test_storage.py`
- Create: `app/storage.py`

- [ ] **Step 1: Write failing storage migration tests**

Add tests that set `DS_MEMORY_DB_PATH` and `DS_MEMORY_DATA_ROOT` to temporary paths, create `users.json`, shared JSON libraries, and user-private JSON libraries, then assert:

```python
from app import storage

result = storage.migrate_json_to_sqlite(self.data_root)
self.assertEqual(result["users"], 1)
self.assertEqual(storage.list_users()[0]["username"], "alice")
self.assertEqual(storage.list_books(None, "words"), ["词库"])
self.assertEqual(storage.read_entries(None, "words", "词库", "query.json")[0]["word"], "alpha")
self.assertEqual(storage.read_entries("u1", "words", "词库", "query.json")[0]["word"], "private")
```

Add an idempotency assertion that running `migrate_json_to_sqlite` twice does not duplicate entries.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_storage -v`

Expected: import or attribute failure because `app.storage` does not exist yet.

- [ ] **Step 3: Implement storage schema and migration**

Create `app/storage.py` with:

```python
def db_path() -> Path: ...
def connect() -> sqlite3.Connection: ...
def init_db() -> None: ...
def migrate_json_to_sqlite(data_root: Path | None = None) -> dict: ...
def list_users() -> list[dict]: ...
def list_books(owner_user_id: str | None, type_name: str) -> list[str]: ...
def list_categories(owner_user_id: str | None, type_name: str, book: str) -> list[str]: ...
def read_entries(owner_user_id: str | None, type_name: str, book: str, category: str) -> list[dict]: ...
```

Use partial unique indexes for shared/user libraries, `(library_id, name)` for books, `(book_id, name)` for categories, `(book_id, word)` for entries, and `(category_id, entry_id)` for links.

- [ ] **Step 4: Run storage tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_storage -v`

Expected: all storage tests pass.

## Task 2: SQLite User Persistence

**Files:**
- Modify: `tests/test_auth.py`
- Modify: `app/auth.py`
- Modify: `app/api/v1/endpoints/admin.py`

- [ ] **Step 1: Write failing auth persistence test**

Update auth tests to set `DS_MEMORY_DB_PATH` to a temporary SQLite file and assert registration creates a SQLite user, not `users.json`:

```python
from app import storage

users = storage.list_users()
self.assertEqual(users[0]["username"], "alice")
self.assertFalse((self.data_root / "users.json").exists())
```

- [ ] **Step 2: Run focused auth test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest.test_register_creates_user_and_redirects_to_index -v`

Expected: failure because auth still writes JSON.

- [ ] **Step 3: Move auth helper internals to storage**

Keep the public helper names in `app/auth.py` stable: `_read_users`, `_write_users`, `_find_user_by_login`, `_find_user_by_id`, `_create_user`, `_authenticate_user`, `_update_user_login`. Implement them using `app.storage` helpers.

- [ ] **Step 4: Run auth and admin user tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest -v
.\.venv\Scripts\python.exe -m unittest tests.test_admin_api.AdminApiTest.test_admin_can_list_users_without_password_hash tests.test_admin_api.AdminApiTest.test_admin_can_disable_enable_and_delete_user -v
```

Expected: targeted tests pass.

## Task 3: Normal Library API Runtime Storage

**Files:**
- Modify: `tests/test_auth.py`
- Modify: `tests/test_storage.py`
- Modify: `app/api/v1/endpoints/DataOperate.py`
- Modify: `app/api/v1/endpoints/DisplayContent.py`
- Modify: `app/api/v1/endpoints/inquire.py`

- [ ] **Step 1: Write failing normal API tests**

Add or update tests that migrate shared fixture JSON into SQLite, register two users, save a word through `/api/v1/DataOperate/SaveData` as user A, and assert user B cannot read it through `/api/v1/DataOperate/ReadData`.

Add inquiry tests that assert ordinary user lookup checks the private library first, then the shared library, then AI. Add save/delete tests that assert ordinary user saves are also upserted into the shared library, while ordinary user deletes do not remove the shared entry.

Also assert `BookshelfList` and `FavoriteList` return names from SQLite.

- [ ] **Step 2: Run focused tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest.test_user_word_data_is_isolated_between_accounts -v
.\.venv\Scripts\python.exe -m unittest tests.test_storage.StorageTest.test_new_user_library_starts_empty_instead_of_copying_shared_entries -v
```

Expected: failures because normal endpoints still depend on JSON paths.

- [ ] **Step 3: Add storage helpers for normal API operations**

Add helpers:

```python
def ensure_user_libraries(user_id: str) -> None: ...
def create_book(owner_user_id, type_name, book) -> dict: ...
def create_category(owner_user_id, type_name, book, category) -> dict: ...
def save_entry(owner_user_id, type_name, book, category, entry) -> tuple[dict, bool]: ...
def delete_entry_from_category(owner_user_id, type_name, book, category, word) -> list[dict]: ...
def replace_entry(owner_user_id, type_name, book, category, original_word, entry) -> dict: ...
def find_entry(owner_user_id, type_name, book, word) -> dict | None: ...
```

Implement current category rules: `query.json` is all entries, `default.json` is uncategorized, and custom category saves remove the word from `default.json`.

- [ ] **Step 4: Wire normal endpoints to storage**

Replace runtime calls to `JsonOperate` in `DataOperate`, `DisplayContent`, and `inquire` with storage calls. Preserve request models and response shapes.

- [ ] **Step 5: Run focused normal API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest.test_user_word_data_is_isolated_between_accounts -v
.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest -v
```

Expected: tests pass.

## Task 4: Admin Library API Runtime Storage

**Files:**
- Modify: `tests/test_admin_api.py`
- Modify: `app/api/v1/endpoints/admin.py`

- [ ] **Step 1: Write failing admin storage tests**

Update `AdminApiTest` setup to migrate fixture JSON into SQLite and assert summary, create category, create entry, search, update, and delete all work through SQLite.

- [ ] **Step 2: Run admin tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_admin_api.AdminApiTest -v`

Expected: failure because admin content APIs still inspect JSON files.

- [ ] **Step 3: Wire admin content APIs to storage**

Use shared owner `None` for all admin library operations. Replace path scanning, JSON reads, and JSON writes with storage helpers.

- [ ] **Step 4: Run admin tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_admin_api.AdminApiTest -v`

Expected: tests pass.

## Task 5: Verification And Runtime Hygiene

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Ignore runtime SQLite artifacts**

Add:

```gitignore
static/data/*.sqlite3
static/data/*.sqlite3-*
```

- [ ] **Step 2: Run full test suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover -v`

Expected: all tests pass.

- [ ] **Step 3: Start dev server**

Run: `.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8003`

Expected: server starts without import/schema errors.

- [ ] **Step 4: Inspect working tree**

Run: `git status --short`

Expected: SQLite source changes and tests are visible; no generated database file is tracked.

# SQLite Storage Layer Design

## Scope

Replace the runtime JSON-file storage with SQLite through a dedicated storage
service layer. The current HTTP routes and frontend request/response contracts
should remain stable wherever practical.

This migration covers:

- Ordinary users currently stored in `static/data/users.json`.
- Shared idiom and word libraries currently stored under `static/data/idiom`
  and `static/data/words`.
- Ordinary-user private libraries currently stored under
  `static/data/user_data/<user_id>`.
- Admin library management, ordinary user management, normal vocabulary
  reading/writing, and local lookup in the inquiry endpoint.
- One-time migration from existing JSON files into SQLite.

This migration does not cover:

- Moving the environment-configured administrator account into the database.
- Changing the public API payload shape for the current frontend.
- Deleting the existing JSON files automatically after migration.
- Adding password reset, audit logs, or multi-role user permissions.

## Current Context

The app is a FastAPI project using Jinja templates and local Vue scripts. Data
is currently persisted as JSON files:

- `static/data/users.json` stores ordinary users.
- `static/data/{idiom|words}/<book>/<category>.json` stores shared library
  entries.
- `static/data/user_data/<user_id>/{idiom|words}/...` is the planned/user-facing
  isolated data root for ordinary users.

Relevant code paths:

- `app/auth.py` owns user auth and JSON user helpers.
- `mylib/File/JsonOperate.py` owns generic JSON file operations.
- `app/api/v1/endpoints/DataOperate.py` reads and writes entries for the normal
  app UI.
- `app/api/v1/endpoints/DisplayContent.py` lists books and categories.
- `app/api/v1/endpoints/inquire.py` performs local lookup before external
  inquiry.
- `app/api/v1/endpoints/admin.py` manages shared libraries and ordinary users.

There are current uncommitted changes in auth and API files, including work
around ordinary users and user data isolation. The SQLite work must build on
that direction instead of reverting it.

## Recommended Architecture

Add a storage service layer, implemented with Python standard-library
`sqlite3`. The route modules should call this layer instead of reading/writing
JSON directly.

Suggested modules:

- `app/storage.py`: connection management, schema initialization, migrations,
  and high-level CRUD helpers.
- Optional `app/storage_models.py` only if small typed return helpers become
  useful. Avoid adding it unless it removes real duplication.

Configuration:

- Default database path: `static/data/ds_memory.sqlite3`.
- Override with `DS_MEMORY_DB_PATH`.
- Keep `DS_MEMORY_DATA_ROOT` as the JSON migration source and fallback fixture
  root for tests.

Initialization:

- Ensure schema on first storage access.
- Use `PRAGMA foreign_keys = ON`.
- Use row dictionaries for clear call sites.
- Keep each write operation inside an explicit transaction.

Routes keep their current public behavior, but their persistence calls move to
the storage service. `mylib/File/JsonOperate.py` can remain for migration and
legacy utility code during the transition, but it should no longer be used by
runtime API handlers after the migration is complete.

## Data Model

### users

Stores ordinary users only. The administrator remains environment-configured.

Columns:

- `id TEXT PRIMARY KEY`
- `username TEXT NOT NULL UNIQUE COLLATE NOCASE`
- `email TEXT NOT NULL UNIQUE COLLATE NOCASE`
- `password_hash TEXT NOT NULL`
- `role TEXT NOT NULL DEFAULT 'user'`
- `status TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `last_login_at TEXT NOT NULL DEFAULT ''`

### libraries

Represents an owner/type namespace. This keeps shared and user-private data in
one structure.

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `owner_user_id TEXT NULL REFERENCES users(id) ON DELETE CASCADE`
- `type_name TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Rules:

- `owner_user_id IS NULL` means the shared/admin library.
- `type_name` is `idiom` or `words`.
- Shared-library uniqueness should use a partial unique index on `type_name`
  where `owner_user_id IS NULL`.
- User-library uniqueness should use a partial unique index on
  `(owner_user_id, type_name)` where `owner_user_id IS NOT NULL`.

### books

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE`
- `name TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Unique key: `(library_id, name)`.

### categories

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE`
- `name TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Rules:

- Store names with `.json` suffix for compatibility with existing API payloads.
- `query.json` and `default.json` are special categories.
- Unique key: `(book_id, name)`.

### entries

Columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE`
- `word TEXT NOT NULL`
- `explain TEXT NOT NULL DEFAULT ''`
- `note TEXT NOT NULL DEFAULT ''`
- `extra_json TEXT NOT NULL DEFAULT '{}'`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Rules:

- `extra_json` preserves any fields beyond `word`, `explain`, and `note`.
- Unique key: `(book_id, word)`.
- If a word appears in multiple categories inside one book, it is one entry
  linked to multiple categories.

### category_entries

Columns:

- `category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE`
- `entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE`
- `position INTEGER NOT NULL DEFAULT 0`
- `created_at TEXT NOT NULL`
- `PRIMARY KEY (category_id, entry_id)`

This table preserves category membership and stable-ish ordering.

## Data Flow

### Authentication

`app/auth.py` should call storage helpers for:

- Reading users.
- Creating users.
- Finding users by username/email.
- Updating `last_login_at`.
- Updating status.
- Deleting users.

Session payloads can keep the current signed-cookie shape. Disabled or deleted
ordinary users should lose access on the next request because session validation
rechecks SQLite.

### Normal User APIs

`DataOperate`, `DisplayContent`, and `inquire` should resolve the active library
context from the request:

- Ordinary user session: `owner_user_id=<current user id>`.
- Admin session or no ordinary user: shared library, `owner_user_id=NULL`.

When an ordinary user first needs a library, the storage service should create
empty private `idiom` and `words` libraries for that user. Each private library
gets a default `词库` book with empty `query.json` and `default.json`
categories. System/shared entries are not copied into new users' private
libraries.

Inquiry lookup for an ordinary user uses this order:

1. The user's private library.
2. The system/shared library.
3. The external AI inquiry helper.

Normal user save and update operations write to the user's private library and
also upsert the same entry into the system/shared library. Normal user delete
operations delete only from the user's private library and never remove entries
from the system/shared library.

### Admin APIs

Admin endpoints should operate on the shared library only:

- Summary counts read from shared `idiom` and `words`.
- Book/category/entry CRUD modifies shared libraries.
- User management reads/writes the `users` table.

Admin changes do not automatically overwrite existing users' private libraries.
New ordinary users start with empty private libraries. System/shared entries
remain system-owned, but normal user contributions are also stored in the
system/shared library so other users can find them through inquiry fallback.

## JSON Migration

Add a migration helper in the storage layer:

- `migrate_json_to_sqlite(data_root: Path | None = None) -> dict`

Behavior:

1. Initialize the SQLite schema.
2. Import `users.json` if present.
3. Import shared libraries from `data_root/idiom` and `data_root/words`.
4. Import private libraries from `data_root/user_data/<user_id>`.
5. Skip invalid JSON files with a recorded warning rather than aborting the
   entire migration.
6. Avoid duplicate rows by upserting logical keys.
7. Return counts for imported users, books, categories, entries, category links,
   and warnings.

Migration should be safe to rerun. Re-running should not create duplicate users,
books, categories, entries, or category links.

The existing JSON files remain in place after migration. This gives a rollback
source and avoids accidental data loss.

## Compatibility Rules

The existing API contracts should stay stable:

- `ReadData` still returns a list of entry dictionaries.
- `SaveData` still returns the saved path-like value or compatible success data.
- `FavoriteList` still returns category filenames.
- `BookshelfList` still returns idiom and words book names.
- Admin entry APIs still use `type_name`, `book`, `category`, and entry dicts.

Where old endpoints returned filesystem paths, the SQLite implementation may
return a compatibility string such as `sqlite://<type>/<book>/<category>`. The
frontend should not depend on physical paths for behavior, but tests should
capture the current practical expectation.

## Error Handling

Storage helpers should raise `ValueError` for validation problems and
`FileNotFoundError` for missing logical books/categories where existing API
behavior expects a 404 or 500 wrapper.

Route modules should keep their current response shapes:

- Normal API: `{"code": ..., "message": ..., "data": ...}`
- Admin API: existing `_ok` and `_error` helpers.

All path-like user input must continue to be validated before becoming logical
book/category names. SQLite removes filesystem traversal risk from runtime
storage, but validation is still needed for compatibility and predictable data.

## Testing

Use TDD for implementation. Focus tests on observable behavior:

- Migration imports users from JSON.
- Migration imports shared books, categories, and entries from JSON.
- Migration is idempotent.
- Register/login reads and writes ordinary users through SQLite.
- Disabled users cannot log in.
- Admin can list, disable, enable, and delete ordinary users from SQLite.
- Normal user writes are isolated from another normal user.
- Normal user inquiry falls back from private library to system/shared library
  before AI lookup.
- Normal user saves and updates are upserted into the system/shared library.
- Normal user deletes do not delete from the system/shared library.
- New ordinary users start with empty private libraries instead of copied system data.
- Admin shared library changes do not mutate an existing user's private library.
- `BookshelfList`, `FavoriteList`, `ReadData`, `SaveData`, `DeleteData`, and
  `alterData` continue returning compatible response shapes.
- Admin summary and entry CRUD work against SQLite.

Tests should set `DS_MEMORY_DB_PATH` to a temporary file and `DS_MEMORY_DATA_ROOT`
to a temporary JSON fixture root. Tests must not write to the real
`static/data/ds_memory.sqlite3` or real JSON data.

## Rollout

1. Add the storage layer and schema initialization behind tests.
2. Add JSON-to-SQLite migration tests and implementation.
3. Move auth user persistence from JSON to SQLite.
4. Move normal user-facing data endpoints from JSON to SQLite.
5. Move admin APIs from JSON to SQLite.
6. Run full tests.
7. Start the dev server and manually verify login, registration, normal word
   save/read, and admin management.

## Open Decisions

- Whether to run JSON migration automatically on app startup when the database
  is empty, or expose it as an explicit script/function invoked by tests and a
  one-time command.

Recommendation: automatically initialize schema, but run data migration
explicitly through a script or command during development. This avoids hidden
startup surprises while still making the storage layer easy to test.

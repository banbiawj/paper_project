# JSON User Auth Management Design

## Scope

Add ordinary user registration, ordinary user login, and real user management in
the admin console while keeping the current JSON-based storage style.

This implementation covers:

- A persistent ordinary-user store at `static/data/users.json`.
- A `/register` page and registration POST handler.
- Login handling for both the existing environment-configured administrator and
  JSON-backed ordinary users.
- User sessions that distinguish `admin` and `user` roles.
- Admin-only user management APIs and UI controls for listing, disabling,
  enabling, and deleting ordinary users.
- Access to `/` for either an administrator or an active ordinary user.
- Continued admin-only access for `/admin` and `/api/v1/admin/*`.

This implementation does not cover:

- Moving the administrator account into JSON storage.
- Password reset email flows.
- Multi-role ordinary users.
- Replacing JSON storage with a database.

## Current Context

The project uses FastAPI, Jinja templates, Vue 2 in the admin page, and JSON
files for application data. Authentication currently has one administrator
configured by `ADMIN_USERNAME` and `ADMIN_PASSWORD` from environment variables.
The signed session payload always uses `role=admin`, so ordinary users cannot
exist in the current session model.

`templates/login.html` contains a registration link, but it points to `#`.
`templates/admin.html` has a "用户管理" menu item, but that view only displays
the current administrator account. The previous admin-page design intentionally
left persistent user management out of scope because no user store existed.

## Recommended Architecture

Keep the administrator account environment-based for compatibility. Add a
separate ordinary-user JSON store under `static/data/users.json`. The auth
module becomes responsible for:

- Loading and saving ordinary users.
- Hashing and verifying ordinary-user passwords.
- Creating signed session tokens for both roles.
- Reading the current session as either an administrator or an ordinary user.
- Enforcing admin-only checks where needed.

The route layer in `main.py` handles page flows:

- `/login` renders and processes a shared login form.
- `/register` renders and processes the registration form.
- `/` allows either an administrator or an active ordinary user.
- `/admin` requires an administrator.
- `/logout` clears the shared session cookie.

The existing admin API router keeps its current content-management endpoints and
adds user-management endpoints under the same `/api/v1/admin` prefix.

## Data Model

Store ordinary users as a JSON list at `static/data/users.json`.

Each user object contains:

- `id`: stable UUID string.
- `username`: unique username after trimming whitespace.
- `email`: unique email after trimming whitespace and lowercasing.
- `password_hash`: PBKDF2 password hash string with algorithm, iterations, salt,
  and digest.
- `role`: always `user`.
- `status`: `active` or `disabled`.
- `created_at`: ISO-like local timestamp string.
- `updated_at`: ISO-like local timestamp string.
- `last_login_at`: ISO-like local timestamp string or empty string.

Example:

```json
[
    {
        "id": "c56843b4e1ac4e078f579ab6a14b42c9",
        "username": "alice",
        "email": "alice@example.com",
        "password_hash": "pbkdf2_sha256$260000$...",
        "role": "user",
        "status": "active",
        "created_at": "2026-05-08 18:30:00",
        "updated_at": "2026-05-08 18:30:00",
        "last_login_at": ""
    }
]
```

Passwords are never stored in plaintext. Use Python standard-library
`hashlib.pbkdf2_hmac` and `secrets` for password hashing.

## Session Model

Use the existing `ds_memory_admin_session` cookie name for compatibility, but
treat it as the application session cookie rather than admin-only state.

Session payload:

```json
{
    "username": "alice",
    "role": "user",
    "exp": 1778236200
}
```

For administrators, `role` is `admin`. For ordinary users, `role` is `user`.

Session readers:

- `_current_session(request)`: returns a valid session payload for either role.
- `_current_admin(request)`: returns only a valid admin payload.
- `_current_user(request)`: returns only a valid ordinary-user payload whose
  JSON account still exists and is `active`.

Disabled or deleted ordinary users lose access on the next request because the
session reader rechecks the JSON user store.

## Page Flow

### Registration

`GET /register` renders `templates/register.html`.

`POST /register` validates:

- Username is not empty.
- Email is not empty and contains a basic `@`.
- Password is not empty.
- Confirmation password matches.
- Username is not already used by another ordinary user.
- Email is not already used by another ordinary user.
- Username does not equal `ADMIN_USERNAME`.

On success, create an active ordinary user, set a `user` session cookie, and
redirect to `/`.

On failure, re-render the form with a clear error message and the safe submitted
username/email values.

### Login

`POST /login` checks credentials in this order:

1. If username and password match `ADMIN_USERNAME` and `ADMIN_PASSWORD`, create
   an admin session and redirect to a safe `next` URL, defaulting to `/admin`.
2. Otherwise, look up an ordinary user by username or email, verify the password,
   require `status=active`, update `last_login_at`, create a user session, and
   redirect to a safe `next` URL, defaulting to `/`.
3. If both checks fail, return the login page with `账号或密码错误`.

If an ordinary user tries to log in while disabled, return `账号已被禁用`.

`GET /login` redirects an already-authenticated administrator to `/admin` by
default and an already-authenticated ordinary user to `/` by default.

### Access Control

`/` requires `_current_session(request)`. If absent, redirect to
`/login?next=/`.

`/admin` requires `_current_admin(request)`. Ordinary users are redirected to
`/login?next=/admin` or shown the login page after their non-admin session is
ignored by the admin check.

All `/api/v1/admin/*` endpoints continue requiring `_current_admin(request)`.

## Admin User Management API

Add these endpoints to `app/api/v1/endpoints/admin.py`:

- `GET /api/v1/admin/users`
  Returns ordinary users without `password_hash`.
- `PATCH /api/v1/admin/users/{user_id}`
  Accepts `{"status": "active"}` or `{"status": "disabled"}` and updates one
  ordinary user.
- `DELETE /api/v1/admin/users/{user_id}`
  Deletes one ordinary user.

Response shape stays consistent with the existing admin API:

```json
{
    "code": 200,
    "message": "succeed",
    "data": {}
}
```

Deleting or disabling an ordinary user should not affect the environment-based
administrator account.

## Admin Frontend

Replace the current read-only user section in `templates/admin.html` with a real
Vue-driven ordinary-user table.

The user view contains:

- Username.
- Email.
- Status badge.
- Created time.
- Last login time.
- Actions: enable, disable, delete.

When switching to the user-management view or refreshing the page, call
`GET /api/v1/admin/users`. Actions call the corresponding admin API and then
reload the user list. API `401` behavior continues redirecting to
`/login?next=/admin`.

The dashboard administrator count can remain `1`, because the administrator is
still environment-configured. A separate ordinary-user count may be added if the
admin summary endpoint includes it.

## Templates

Modify `templates/login.html`:

- Change the registration link from `#` to `/register`.
- Keep the existing username/password form.
- Keep `remember` behavior for both roles.

Create `templates/register.html` by following the login page's visual structure
and form style, with username, email, password, confirm password, submit button,
error display, and a link back to `/login`.

## Error Handling

Backend validation errors should be clear enough for the UI to display directly:

- `用户名不能为空`
- `邮箱不能为空`
- `邮箱格式不正确`
- `密码不能为空`
- `两次输入的密码不一致`
- `用户名已存在`
- `邮箱已存在`
- `账号已被禁用`
- `用户不存在`

JSON file errors should return the same admin API error shape used by existing
admin endpoints. If `users.json` does not exist, it is treated as an empty list
and created when the first ordinary user registers.

## Testing

Add focused tests around the new auth and user-management behavior:

- Registering creates a JSON-backed ordinary user and redirects to `/`.
- Duplicate username or email registration is rejected.
- Ordinary users can log in and access `/`.
- Ordinary users cannot access `/admin`.
- Disabled users cannot log in.
- Admin can list ordinary users through `/api/v1/admin/users`.
- Admin can disable, enable, and delete ordinary users.
- User-management API never returns `password_hash`.
- Existing admin login, admin page, logout, and admin content API tests continue
  to pass.

Tests should use a temporary `DS_MEMORY_DATA_ROOT` so they do not modify the
real `static/data/users.json`.

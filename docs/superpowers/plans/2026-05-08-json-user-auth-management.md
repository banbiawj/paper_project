# JSON User Auth Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JSON-backed ordinary user registration, login, and admin user management while keeping the environment-configured administrator.

**Architecture:** Extend `app/auth.py` with JSON user-store helpers, PBKDF2 password hashing, role-aware signed sessions, and current-session readers. Update `main.py` page routes for registration and mixed admin/user login. Extend the existing `/api/v1/admin` router and Vue admin page with ordinary-user management.

**Tech Stack:** FastAPI, Jinja2 templates, Vue 2, Python standard-library JSON/PBKDF2 helpers, `unittest` with FastAPI `TestClient`.

---

## File Structure

- Modify `app/auth.py`: ordinary-user JSON storage, password hashing, role-aware sessions, admin/user/current-session helpers.
- Modify `main.py`: register routes, mixed login flow, `/` access for admin or active user.
- Modify `app/api/v1/endpoints/admin.py`: admin-only user list/status/delete endpoints.
- Modify `templates/login.html`: real `/register` link.
- Create `templates/register.html`: registration form matching the login page style.
- Modify `templates/admin.html`: Vue data/methods and real user-management table.
- Modify `tests/test_auth.py`: registration and ordinary-user login/access tests.
- Modify `tests/test_admin_api.py`: admin user-management API tests.

## Execution Notes

- Use `.venv\Scripts\python.exe -m unittest discover -v` for the full test suite and targeted `unittest` module paths for red-green checks.
- Tests must set `DS_MEMORY_DATA_ROOT` to a temporary directory so `static/data/users.json` is not changed.
- The repository `.git` directory is currently not writable from this session, so commit steps may fail with `index.lock` permission errors. Continue implementation and report that limitation.

### Task 1: Auth Route Tests

**Files:**
- Modify: `tests/test_auth.py`
- Later modify: `app/auth.py`, `main.py`, `templates/login.html`, `templates/register.html`

- [ ] **Step 1: Write failing registration and user-login tests**

Add temp data root setup helpers to `tests/test_auth.py`:

```python
import json
import shutil
import uuid
from pathlib import Path
```

```python
    def setUp(self):
        self.workspace_tmp = Path.cwd() / ".test-tmp"
        self.workspace_tmp.mkdir(exist_ok=True)
        self.data_root = self.workspace_tmp / f"auth-data-{uuid.uuid4().hex}"
        self.data_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(self.data_root)
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("DS_MEMORY_DATA_ROOT", None)
        shutil.rmtree(self.data_root, ignore_errors=True)
        try:
            self.workspace_tmp.rmdir()
        except OSError:
            pass

    def _users_file(self):
        return self.data_root / "users.json"
```

Add tests:

```python
    def test_register_creates_user_and_redirects_to_index(self):
        response = self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/")
        users = json.loads(self._users_file().read_text(encoding="utf-8"))
        self.assertEqual(users[0]["username"], "alice")
        self.assertEqual(users[0]["email"], "alice@example.com")
        self.assertEqual(users[0]["role"], "user")
        self.assertEqual(users[0]["status"], "active")
        self.assertNotEqual(users[0]["password_hash"], "secret123")

        index_response = self.client.get("/")
        self.assertEqual(index_response.status_code, 200)
        self.assertIn('id="app"', index_response.text)

    def test_register_rejects_duplicate_username_and_email(self):
        first = {
            "username": "alice",
            "email": "alice@example.com",
            "password": "secret123",
            "confirm_password": "secret123",
        }
        self.client.post("/register", data=first)

        duplicate_username = self.client.post(
            "/register",
            data={**first, "email": "alice2@example.com"},
        )
        duplicate_email = self.client.post(
            "/register",
            data={**first, "username": "alice2"},
        )

        self.assertEqual(duplicate_username.status_code, 400)
        self.assertIn("用户名已存在", duplicate_username.text)
        self.assertEqual(duplicate_email.status_code, 400)
        self.assertIn("邮箱已存在", duplicate_email.text)

    def test_user_can_login_and_access_index_but_not_admin(self):
        self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        self.client.post("/logout")

        login_response = self.client.post(
            "/login",
            data={"username": "alice", "password": "secret123"},
            follow_redirects=False,
        )

        self.assertEqual(login_response.status_code, 303)
        self.assertEqual(login_response.headers["location"], "/")
        self.assertEqual(self.client.get("/").status_code, 200)

        admin_response = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(admin_response.status_code, 303)
        self.assertEqual(admin_response.headers["location"], "/login?next=%2Fadmin")

    def test_disabled_user_cannot_login(self):
        self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        self.client.post("/logout")
        users = json.loads(self._users_file().read_text(encoding="utf-8"))
        users[0]["status"] = "disabled"
        self._users_file().write_text(
            json.dumps(users, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

        response = self.client.post(
            "/login",
            data={"username": "alice", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("账号已被禁用", response.text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest -v
```

Expected: failures/errors for missing `/register` route and ordinary-user login behavior.

- [ ] **Step 3: Implement auth helpers and routes**

In `app/auth.py`, add:

```python
import secrets
import uuid
from pathlib import Path
```

Implement helpers with these exact names and responsibilities:

```python
def _data_root() -> Path:
    # Return Path(os.getenv("DS_MEMORY_DATA_ROOT", "static/data")).

def _users_file() -> Path:
    # Return _data_root() / "users.json".

def _now_string() -> str:
    # Return the current local time formatted as "%Y-%m-%d %H:%M:%S".

def _read_users() -> list[dict]:
    # Return [] when users.json does not exist; otherwise load a JSON list.

def _write_users(users: list[dict]) -> None:
    # Create the parent directory and write the list as UTF-8 JSON.

def _public_user(user: dict) -> dict:
    # Return a shallow copy without password_hash.

def _hash_password(password: str) -> str:
    # Return "pbkdf2_sha256$260000$<salt>$<digest>".

def _verify_password(password: str, password_hash: str) -> bool:
    # Verify PBKDF2 hashes with hmac.compare_digest.

def _find_user_by_login(login: str) -> dict | None:
    # Match trimmed username or lowercased email.

def _find_user_by_id(user_id: str) -> dict | None:
    # Return the first user whose id matches user_id.

def _create_user(username: str, email: str, password: str) -> dict:
    # Validate uniqueness, append a user dict, write users.json, and return it.

def _authenticate_user(login: str, password: str) -> tuple[dict | None, str | None]:
    # Return (user, None) on success or (None, error_message) on failure.

def _update_user_login(user_id: str) -> None:
    # Set last_login_at and updated_at for the matching user.
```

Change `_create_session_token` to accept role:

```python
def _create_session_token(username: str, role: str = "admin") -> str:
    payload = {
        "username": username,
        "role": role,
        "exp": int(time.time()) + SESSION_MAX_AGE,
    }
```

Change `_read_session_token` to validate admin sessions by environment username and user sessions by JSON user status. Add:

`_current_session(request)` reads the shared cookie and returns any valid admin
or active-user payload. `_current_admin(request)` returns only admin payloads.
`_current_user(request)` returns only active ordinary-user payloads.

In `main.py`, import the new helpers and add:

```python
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return _no_store(
        templates.TemplateResponse(
            request,
            "register.html",
            {"error": None, "username": "", "email": ""},
        )
    )

@app.post("/register", response_class=HTMLResponse)
async def register(request: Request):
    form_data = await _read_urlencoded_form(request)
    # Validate form fields, call _create_user, set a user session cookie,
    # and redirect to "/". On validation errors, re-render register.html.
```

Update `/` to require `_current_session(request)`. Update `/login` GET and POST to support admin and ordinary users.

Create `templates/register.html` with a matching form and error display.

Change `templates/login.html` registration link to:

```html
<a href="/register">立即免费注册</a>
```

- [ ] **Step 4: Run auth tests to verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth.AuthRoutesTest -v
```

Expected: all auth route tests pass.

### Task 2: Admin User API Tests

**Files:**
- Modify: `tests/test_admin_api.py`
- Later modify: `app/api/v1/endpoints/admin.py`, `app/auth.py`

- [ ] **Step 1: Write failing admin user API tests**

In `tests/test_admin_api.py`, import:

```python
from app.auth import _create_user
```

Add tests:

```python
    def test_admin_can_list_users_without_password_hash(self):
        created = _create_user("alice", "alice@example.com", "secret123")
        self._login()

        response = self.client.get("/api/v1/admin/users")

        self.assertEqual(response.status_code, 200)
        users = response.json()["data"]["users"]
        self.assertEqual(users[0]["id"], created["id"])
        self.assertEqual(users[0]["username"], "alice")
        self.assertNotIn("password_hash", users[0])

    def test_admin_can_disable_enable_and_delete_user(self):
        created = _create_user("alice", "alice@example.com", "secret123")
        self._login()

        disabled = self.client.patch(
            f"/api/v1/admin/users/{created['id']}",
            json={"status": "disabled"},
        )
        enabled = self.client.patch(
            f"/api/v1/admin/users/{created['id']}",
            json={"status": "active"},
        )
        deleted = self.client.delete(f"/api/v1/admin/users/{created['id']}")
        listed = self.client.get("/api/v1/admin/users")

        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.json()["data"]["user"]["status"], "disabled")
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(enabled.json()["data"]["user"]["status"], "active")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(listed.json()["data"]["users"], [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_admin_api.AdminApiTest -v
```

Expected: failures/errors for missing `/api/v1/admin/users` endpoints.

- [ ] **Step 3: Implement admin user API**

In `app/api/v1/endpoints/admin.py`, import:

```python
from app.auth import _public_user, _read_users, _write_users
```

Add:

```python
class UserStatusRequest(BaseModel):
    status: str
```

Add routes:

```python
@router.get("/users")
async def users(request: Request):
    if auth_error := _auth_error(request):
        return auth_error
    return _ok({"users": [_public_user(user) for user in _read_users()]})

@router.patch("/users/{user_id}")
async def update_user_status(request: Request, user_id: str, payload: UserStatusRequest):
    # Require payload.status in {"active", "disabled"}, update the matching
    # user timestamps, write users.json, and return the public user.

@router.delete("/users/{user_id}")
async def delete_user(request: Request, user_id: str):
    # Remove the matching user from users.json and return the deleted public user.
```

Validate status is `active` or `disabled`, return `404` for missing users, and never include `password_hash`.

- [ ] **Step 4: Run admin API tests to verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_admin_api.AdminApiTest -v
```

Expected: all admin API tests pass.

### Task 3: Admin Template User Management

**Files:**
- Modify: `templates/admin.html`
- Modify: `tests/test_admin_api.py`

- [ ] **Step 1: Add failing template assertions**

Extend `test_admin_page_renders_logout_form` in `tests/test_admin_api.py`:

```python
self.assertIn("/api/v1/admin/users", response.text)
self.assertIn("普通用户", response.text)
self.assertIn("toggleUserStatus", response.text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_admin_api.AdminApiTest.test_admin_page_renders_logout_form -v
```

Expected: failure because the admin page still has a read-only administrator table.

- [ ] **Step 3: Update admin Vue template**

Replace the `view === 'users'` section with a table that renders:

```html
<div class="panel-title">普通用户</div>
<tbody>
    <tr v-for="user in users" :key="user.id">
        <td class="entry-word">[[ user.username ]]</td>
        <td>[[ user.email ]]</td>
        <td><span class="badge" :class="{disabled: user.status === 'disabled'}">[[ user.status === 'active' ? '启用' : '禁用' ]]</span></td>
        <td>[[ user.created_at || '-' ]]</td>
        <td>[[ user.last_login_at || '-' ]]</td>
        <td>
            <span class="table-actions">
                <button class="btn btn-icon" type="button" title="切换状态" @click="toggleUserStatus(user)">
                    <i class="bi" :class="user.status === 'active' ? 'bi-person-slash' : 'bi-person-check'"></i>
                </button>
                <button class="btn btn-danger btn-icon" type="button" title="删除" @click="deleteUser(user)">
                    <i class="bi bi-trash"></i>
                </button>
            </span>
        </td>
    </tr>
</tbody>
```

Add `users: []` to Vue data, load users in `refreshAll`, and add methods:

```javascript
async loadUsers() {
    const data = await this.apiRequest('/users');
    this.users = data.users;
},
async toggleUserStatus(user) {
    const nextStatus = user.status === 'active' ? 'disabled' : 'active';
    await this.apiRequest(`/users/${encodeURIComponent(user.id)}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus })
    });
    await this.loadUsers();
},
async deleteUser(user) {
    if (!window.confirm(`删除用户“${user.username}”？`)) {
        return;
    }
    await this.apiRequest(`/users/${encodeURIComponent(user.id)}`, {
        method: 'DELETE'
    });
    await this.loadUsers();
}
```

- [ ] **Step 4: Run template assertion test to verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_admin_api.AdminApiTest.test_admin_page_renders_logout_form -v
```

Expected: the template assertion passes.

### Task 4: Full Verification

**Files:**
- Verify all touched files.

- [ ] **Step 1: Run full test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

Expected: all tests pass.

- [ ] **Step 2: Check working tree status**

Run:

```powershell
git status --short
```

Expected: changed files show the spec, plan, tests, auth module, main route file, register template, login template, admin API, and admin template.

- [ ] **Step 3: Attempt commit if Git permissions allow**

Run:

```powershell
git add docs/superpowers/specs/2026-05-08-json-user-auth-management-design.md docs/superpowers/plans/2026-05-08-json-user-auth-management.md tests/test_auth.py tests/test_admin_api.py app/auth.py main.py app/api/v1/endpoints/admin.py templates/login.html templates/register.html templates/admin.html
git commit -m "feat: add json user auth management"
```

Expected: commit succeeds. If it fails with `.git/index.lock` permission errors, report the implemented files and verification results without claiming commit success.

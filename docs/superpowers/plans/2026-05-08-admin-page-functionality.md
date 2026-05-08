# Admin Page Functionality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real admin console with authenticated admin APIs, dashboard statistics, book/category management, entry search and CRUD, and logout.

**Architecture:** Add a shared auth module so `main.py` and the admin API can validate the same signed session cookie without a circular import. Add a dedicated `/api/v1/admin` router that reads and writes the existing JSON storage. Replace the static admin template body with a Vue 2 state-driven console that only calls the admin API.

**Tech Stack:** FastAPI, Pydantic v2, Jinja2, Vue 2 from `static/JavaScript/vue.js`, Python `unittest` with FastAPI `TestClient`.

---

## File Structure

- Create `app/auth.py`: shared admin session helpers, cookie names, redirects, and no-store headers.
- Create `app/api/v1/endpoints/admin.py`: authenticated admin JSON API and JSON-storage helpers.
- Modify `main.py`: import shared auth helpers, keep compatibility names used by tests, and remove duplicated session helper definitions.
- Modify `app/api/v1/__init__.py`: include the new admin router at `/api/v1/admin`.
- Modify `templates/admin.html`: implement the interactive admin console.
- Create `tests/test_admin_api.py`: admin API and admin template behavior tests.

## Task 1: Add Failing Admin API Tests

**Files:**
- Create: `tests/test_admin_api.py`

- [ ] **Step 1: Write the failing tests**

```python
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from main import _create_session_token, app


class AdminApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_root = Path(self.temp_dir.name)
        os.environ["DS_MEMORY_DATA_ROOT"] = str(self.data_root)
        self._seed_data()
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("DS_MEMORY_DATA_ROOT", None)
        self.temp_dir.cleanup()

    def _write_json(self, relative_path, data):
        path = self.data_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

    def _seed_data(self):
        self._write_json(
            Path("idiom") / "词库" / "query.json",
            [
                {"word": "凌空蹈虚", "explain": "谓无史实根据的虚构。", "note": "示例"},
                {"word": "虚有其表", "explain": "空有好看的外表。", "note": ""},
            ],
        )
        self._write_json(Path("idiom") / "词库" / "default.json", [])
        self._write_json(
            Path("idiom") / "辨析分类" / "query.json",
            [{"word": "一马当先", "explain": "形容领先。", "note": ""}],
        )
        self._write_json(Path("idiom") / "辨析分类" / "default.json", [])
        self._write_json(
            Path("words") / "词库" / "query.json",
            [{"word": "徜徉", "explain": "闲游。", "note": ""}],
        )
        self._write_json(Path("words") / "词库" / "default.json", [])

    def _login(self):
        self.client.cookies.set("ds_memory_admin_session", _create_session_token("admin"))

    def test_admin_api_requires_login(self):
        response = self.client.get("/api/v1/admin/summary")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], 401)

    def test_summary_returns_real_counts_when_logged_in(self):
        self._login()

        response = self.client.get("/api/v1/admin/summary")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["entry_count"], 4)
        self.assertEqual(data["book_count"], 3)
        self.assertGreaterEqual(data["category_count"], 6)
        self.assertGreaterEqual(len(data["recent_entries"]), 1)

    def test_entry_search_create_edit_and_delete(self):
        self._login()

        create_book = self.client.post(
            "/api/v1/admin/books",
            json={"type_name": "idiom", "book": "测试书籍"},
        )
        self.assertEqual(create_book.status_code, 200)

        create_category = self.client.post(
            "/api/v1/admin/categories",
            json={"type_name": "idiom", "book": "测试书籍", "category": "专项"},
        )
        self.assertEqual(create_category.status_code, 200)
        self.assertIn("专项.json", create_category.json()["data"]["categories"])

        create_entry = self.client.post(
            "/api/v1/admin/entries",
            json={
                "type_name": "idiom",
                "book": "测试书籍",
                "category": "专项.json",
                "entry": {"word": "测试词", "explain": "说明", "note": ""},
            },
        )
        self.assertEqual(create_entry.status_code, 200)

        search = self.client.get(
            "/api/v1/admin/entries",
            params={
                "type_name": "idiom",
                "book": "测试书籍",
                "category": "query.json",
                "keyword": "测试词",
            },
        )
        self.assertEqual([item["word"] for item in search.json()["data"]["entries"]], ["测试词"])

        update_entry = self.client.put(
            "/api/v1/admin/entries",
            json={
                "type_name": "idiom",
                "book": "测试书籍",
                "category": "专项.json",
                "original_word": "测试词",
                "entry": {"word": "测试词改", "explain": "新的说明", "note": ""},
            },
        )
        self.assertEqual(update_entry.status_code, 200)

        updated = self.client.get(
            "/api/v1/admin/entries",
            params={"type_name": "idiom", "book": "测试书籍", "category": "query.json", "keyword": "测试词改"},
        )
        self.assertEqual(updated.json()["data"]["entries"][0]["explain"], "新的说明")

        delete_entry = self.client.request(
            "DELETE",
            "/api/v1/admin/entries",
            json={"type_name": "idiom", "book": "测试书籍", "category": "专项.json", "word": "测试词改"},
        )
        self.assertEqual(delete_entry.status_code, 200)

        deleted = self.client.get(
            "/api/v1/admin/entries",
            params={"type_name": "idiom", "book": "测试书籍", "category": "query.json", "keyword": "测试词改"},
        )
        self.assertEqual(deleted.json()["data"]["entries"], [])

    def test_admin_page_renders_logout_form(self):
        self._login()

        response = self.client.get("/admin")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="adminApp"', response.text)
        self.assertIn('action="/logout"', response.text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_admin_api -v`

Expected: FAIL because `/api/v1/admin/*` does not exist and `templates/admin.html` does not contain `id="adminApp"`.

## Task 2: Implement Shared Auth and Admin API

**Files:**
- Create: `app/auth.py`
- Create: `app/api/v1/endpoints/admin.py`
- Modify: `main.py`
- Modify: `app/api/v1/__init__.py`

- [ ] **Step 1: Create `app/auth.py`**

Move session token creation, session reading, current admin lookup, no-store headers, safe next URL handling, and login redirects into this module. Export compatibility names for `main.py`.

- [ ] **Step 2: Modify `main.py`**

Import these names from `app.auth`: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `APP_SECRET_KEY`, `SESSION_COOKIE_NAME`, `LEGACY_SESSION_COOKIE_NAMES`, `SESSION_MAX_AGE`, `_create_session_token`, `_current_admin`, `_no_store`, `_redirect_to_login`, `_safe_next_url`.

Remove the duplicated local definitions of those helpers and constants from `main.py`.

- [ ] **Step 3: Create the admin router**

Implement `/summary`, `/library`, `/entries` GET, `/books` POST, `/categories` POST, `/entries` POST, `/entries` PUT, and `/entries` DELETE in `app/api/v1/endpoints/admin.py`. Every endpoint first checks `_current_admin(request)` and returns:

```python
JSONResponse(status_code=401, content={"code": 401, "message": "未登录或登录已过期", "data": None})
```

when there is no valid admin session.

- [ ] **Step 4: Wire the router**

Add `admin` to `app/api/v1/__init__.py` imports and include it:

```python
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
```

- [ ] **Step 5: Run tests**

Run: `python -m unittest tests.test_admin_api -v`

Expected: PASS for admin API tests.

## Task 3: Rebuild the Admin Template

**Files:**
- Modify: `templates/admin.html`

- [ ] **Step 1: Preserve the visual layout**

Keep the existing sidebar/top-header/content layout and responsive behavior, but wrap the page in:

```html
<div id="adminApp" class="admin-layout">
```

- [ ] **Step 2: Replace fake data with Vue state**

Load Vue 2 with:

```html
<script src="/static/JavaScript/vue.js"></script>
```

Initialize state for `summary`, `library`, `entries`, `typeName`, `selectedBook`, `selectedCategory`, `keyword`, `entryForm`, `editingWord`, `message`, `error`, and loading flags.

- [ ] **Step 3: Implement admin API calls**

Add methods `apiRequest`, `loadSummary`, `loadLibrary`, `loadEntries`, `createBook`, `createCategory`, `openCreateEntry`, `openEditEntry`, `saveEntry`, `deleteEntry`, `selectType`, `selectBook`, `selectCategory`, and `switchView`.

- [ ] **Step 4: Add forms and tables**

Render:

- Summary cards with real values.
- Recent entries table from `summary.recent_entries`.
- Book/category management lists with create forms.
- Entry management selectors, search field, create/edit form, and delete buttons.
- Read-only users/settings sections.
- Logout form posting to `/logout`.

- [ ] **Step 5: Run auth and admin tests**

Run: `python -m unittest tests.test_auth tests.test_admin_api -v`

Expected: PASS.

## Task 4: Full Verification

**Files:**
- No code changes unless verification finds a defect.

- [ ] **Step 1: Run all tests**

Run: `python -m unittest discover -v`

Expected: PASS.

- [ ] **Step 2: Check working tree**

Run: `git status --short`

Expected: modified implementation files plus the existing uncommitted `templates/admin.html` and new docs/tests. If `.git/index.lock` permissions still block staging, report that commits were not created.

## Self-Review

Spec coverage:

- Dashboard statistics: Task 2 `/summary`, Task 3 summary cards.
- Books/category management: Task 2 `/library`, `/books`, `/categories`; Task 3 management UI.
- Entry search/create/edit/delete: Task 2 entry endpoints; Task 3 entry UI.
- Logout: Task 3 logout form, existing `/logout`.
- Admin API auth: Task 2 auth check, Task 1 test.

Placeholder scan: no unresolved placeholders remain in this plan.

Type consistency: the plan consistently uses `type_name`, `book`, `category`, `entry`, `original_word`, and `word` across tests, API, and frontend.

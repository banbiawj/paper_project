import os
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["APP_SECRET_KEY"] = "test-secret"

from app.api.v1.endpoints import DataOperate, DisplayContent, inquire  # noqa: E402
from main import _create_session_token, app  # noqa: E402


class AuthRoutesTest(unittest.TestCase):
    def setUp(self):
        self.workspace_tmp = Path.cwd() / ".test-tmp"
        self.workspace_tmp.mkdir(exist_ok=True)
        self.data_root = self.workspace_tmp / f"auth-data-{uuid.uuid4().hex}"
        self.data_root.mkdir()
        self.db_path = Path(tempfile.gettempdir()) / f"ds-memory-auth-{uuid.uuid4().hex}.sqlite3"
        os.environ["DS_MEMORY_DATA_ROOT"] = str(self.data_root)
        os.environ["DS_MEMORY_DB_PATH"] = str(self.db_path)
        self._original_api_paths = {
            DataOperate: (DataOperate.IDIOM_PATH, DataOperate.WORDS_PATH),
            DisplayContent: (DisplayContent.IDIOM_PATH, DisplayContent.WORDS_PATH),
            inquire: (inquire.IDIOM_PATH, inquire.WORDS_PATH),
        }
        for module in self._original_api_paths:
            module.IDIOM_PATH = str(self.data_root / "idiom")
            module.WORDS_PATH = str(self.data_root / "words")
        self._seed_word_data()
        self.client = TestClient(app)

    def tearDown(self):
        for module, (idiom_path, words_path) in self._original_api_paths.items():
            module.IDIOM_PATH = idiom_path
            module.WORDS_PATH = words_path
        os.environ.pop("DS_MEMORY_DATA_ROOT", None)
        os.environ.pop("DS_MEMORY_DB_PATH", None)
        shutil.rmtree(self.data_root, ignore_errors=True)
        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except PermissionError:
                pass
        try:
            self.workspace_tmp.rmdir()
        except OSError:
            pass

    def _users_file(self):
        return self.data_root / "users.json"

    def _write_json(self, relative_path, data):
        path = self.data_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

    def _seed_word_data(self):
        self._write_json(Path("words") / "词库" / "query.json", [])
        self._write_json(Path("words") / "词库" / "default.json", [])
        self._write_json(Path("idiom") / "词库" / "query.json", [])
        self._write_json(Path("idiom") / "词库" / "default.json", [])

    def test_admin_requires_login(self):
        response = self.client.get("/admin", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login?next=%2Fadmin")

    def test_index_requires_login(self):
        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login?next=%2F")

    def test_invalid_login_returns_login_page(self):
        response = self.client.post(
            "/login",
            data={"username": "admin", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn('id="username"', response.text)
        self.assertIn("login-error", response.text)

    def test_admin_can_login_and_view_admin_page(self):
        login_response = self.client.post(
            "/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False,
        )

        self.assertEqual(login_response.status_code, 303)
        self.assertEqual(login_response.headers["location"], "/admin")

        admin_response = self.client.get("/admin")

        self.assertEqual(admin_response.status_code, 200)
        self.assertIn("admin-layout", admin_response.text)

    def test_admin_login_ignores_index_next_and_opens_admin(self):
        login_page = self.client.get("/login?next=/")

        self.assertEqual(login_page.status_code, 200)
        self.assertIn('name="next"', login_page.text)

        login_response = self.client.post(
            "/login",
            data={"username": "admin", "password": "admin123", "next": "/"},
            follow_redirects=False,
        )

        self.assertEqual(login_response.status_code, 303)
        self.assertEqual(login_response.headers["location"], "/admin")

        admin_response = self.client.get("/admin")

        self.assertEqual(admin_response.status_code, 200)
        self.assertIn("admin-layout", admin_response.text)

    def test_logged_in_admin_login_page_redirects_to_admin(self):
        self.client.post(
            "/login",
            data={"username": "admin", "password": "admin123"},
        )

        response = self.client.get("/login?next=/", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/admin")

    def test_legacy_cookie_does_not_grant_access(self):
        self.client.cookies.set("admin_session", _create_session_token("admin"))

        response = self.client.get("/admin", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login?next=%2Fadmin")

    def test_protected_pages_are_not_cached(self):
        self.client.post(
            "/login",
            data={"username": "admin", "password": "admin123", "next": "/"},
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")

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
        from app import storage

        users = storage.list_users()
        self.assertEqual(users[0]["username"], "alice")
        self.assertEqual(users[0]["email"], "alice@example.com")
        self.assertEqual(users[0]["role"], "user")
        self.assertEqual(users[0]["status"], "active")
        self.assertNotEqual(users[0]["password_hash"], "secret123")
        self.assertFalse(self._users_file().exists())

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
        from app import storage

        users = storage.list_users()
        storage.update_user_status(users[0]["id"], "disabled", "2026-05-08 10:00:00")

        response = self.client.post(
            "/login",
            data={"username": "alice", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("账号已被禁用", response.text)

    def test_user_word_data_is_isolated_between_accounts(self):
        from app import storage

        storage.migrate_json_to_sqlite(self.data_root)
        runtime_root = self.data_root / "empty-runtime"
        runtime_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(runtime_root)

        self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        save_response = self.client.post(
            "/api/v1/DataOperate/SaveData",
            json={
                "TypeName": "words",
                "FavoriteName": "query.json",
                "PresentPath": "词库",
                "message": {
                    "word": "用户A词条",
                    "explain": "只属于 alice",
                    "note": "",
                },
            },
        )
        self.assertEqual(save_response.status_code, 200)
        self.client.post("/logout")

        self.client.post(
            "/register",
            data={
                "username": "bob",
                "email": "bob@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        read_response = self.client.post(
            "/api/v1/DataOperate/ReadData",
            json={
                "TypeName": "words",
                "FavoriteName": "query.json",
                "PresentPath": "词库",
            },
        )

        self.assertEqual(read_response.status_code, 200)
        words = [item["word"] for item in read_response.json()["data"]]
        self.assertNotIn("用户A词条", words)


    def test_read_data_uses_sqlite_after_json_source_removed(self):
        from app import storage

        self._write_json(
            Path("words") / "book" / "query.json",
            [{"word": "sqlite-only", "explain": "from sqlite", "note": ""}],
        )
        self._write_json(Path("words") / "book" / "default.json", [])
        storage.migrate_json_to_sqlite(self.data_root)
        runtime_root = self.data_root / "empty-runtime"
        runtime_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(runtime_root)

        response = self.client.post(
            "/api/v1/DataOperate/ReadData",
            json={
                "TypeName": "words",
                "FavoriteName": "query.json",
                "PresentPath": "book",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["word"], "sqlite-only")

    def test_display_lists_use_sqlite_after_json_source_removed(self):
        from app import storage

        self._write_json(Path("words") / "book" / "query.json", [])
        self._write_json(Path("words") / "book" / "default.json", [])
        storage.migrate_json_to_sqlite(self.data_root)
        runtime_root = self.data_root / "empty-runtime"
        runtime_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(runtime_root)

        books = self.client.post("/api/v1/DisplayContent/BookshelfList")
        favorites = self.client.post(
            "/api/v1/DisplayContent/FavoriteList",
            json={"TypeName": "words", "BookName": "book"},
        )

        self.assertEqual(books.status_code, 200)
        self.assertIn("book", books.json()["data"]["words_BookshelfList_list"])
        self.assertEqual(favorites.status_code, 200)
        self.assertEqual(
            favorites.json()["data"]["FavoriteList_list"],
            ["query.json", "default.json"],
        )

    def test_inquire_uses_sqlite_local_lookup_after_json_source_removed(self):
        from app import storage

        self._write_json(
            Path("words") / "book" / "query.json",
            [{"word": "lookup", "explain": "local sqlite", "note": ""}],
        )
        self._write_json(Path("words") / "book" / "default.json", [])
        storage.migrate_json_to_sqlite(self.data_root)
        runtime_root = self.data_root / "empty-runtime"
        runtime_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(runtime_root)

        response = self.client.post(
            "/api/v1/inquire/query",
            json={"TypeName": "words", "InquireContent": "lookup"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["explain"], "local sqlite")

    def test_inquire_rejects_empty_ai_result(self):
        from app import storage

        storage.migrate_json_to_sqlite(self.data_root)
        runtime_root = self.data_root / "empty-runtime"
        runtime_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(runtime_root)

        with patch(
            "app.api.v1.endpoints.inquire.agent_inquire.inquire_idiom",
            return_value=None,
        ):
            response = self.client.post(
                "/api/v1/inquire/query",
                json={"TypeName": "idiom", "InquireContent": "new-term"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertIn("AI returned no result", response.json()["message"])

    def test_user_inquire_falls_back_to_shared_library_before_ai(self):
        from app import storage

        self._write_json(
            Path("words") / "system" / "query.json",
            [{"word": "shared-term", "explain": "system shared", "note": ""}],
        )
        self._write_json(Path("words") / "system" / "default.json", [])
        storage.migrate_json_to_sqlite(self.data_root)
        runtime_root = self.data_root / "empty-runtime"
        runtime_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(runtime_root)
        self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )

        with patch(
            "app.api.v1.endpoints.inquire.agent_inquire.inquire_words",
            side_effect=AssertionError("AI should not be called when shared library has the entry"),
        ):
            response = self.client.post(
                "/api/v1/inquire/query",
                json={"TypeName": "words", "InquireContent": "shared-term"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["explain"], "system shared")

    def test_user_saved_entry_is_available_to_other_users_through_shared_library(self):
        from app import storage

        storage.migrate_json_to_sqlite(self.data_root)
        runtime_root = self.data_root / "empty-runtime"
        runtime_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(runtime_root)
        self.client.post(
            "/register",
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        save_response = self.client.post(
            "/api/v1/DataOperate/SaveData",
            json={
                "TypeName": "words",
                "FavoriteName": "query.json",
                "PresentPath": "词库",
                "message": {
                    "word": "community-term",
                    "explain": "from alice",
                    "note": "",
                },
            },
        )
        self.assertEqual(save_response.status_code, 200)
        self.client.post("/logout")
        self.client.post(
            "/register",
            data={
                "username": "bob",
                "email": "bob@example.com",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )

        with patch(
            "app.api.v1.endpoints.inquire.agent_inquire.inquire_words",
            side_effect=AssertionError("AI should not be called when shared library has the entry"),
        ):
            response = self.client.post(
                "/api/v1/inquire/query",
                json={"TypeName": "words", "InquireContent": "community-term"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["explain"], "from alice")

        delete_response = self.client.post(
            "/api/v1/DataOperate/DeleteData",
            json={
                "TypeName": "words",
                "FavoriteName": "query.json",
                "PresentPath": "词库",
                "message": {"word": "community-term"},
            },
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(
            storage.find_entry_in_type(None, "words", "community-term")["explain"],
            "from alice",
        )


if __name__ == "__main__":
    unittest.main()

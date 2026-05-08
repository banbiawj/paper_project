import os
import json
import shutil
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["APP_SECRET_KEY"] = "test-secret"

from main import _create_session_token, app  # noqa: E402


class AuthRoutesTest(unittest.TestCase):
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
        self.assertTrue(self._users_file().exists(), "register should create users.json")
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


if __name__ == "__main__":
    unittest.main()

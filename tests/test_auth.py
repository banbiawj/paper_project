import os
import unittest

from fastapi.testclient import TestClient

os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["APP_SECRET_KEY"] = "test-secret"

from main import _create_session_token, app  # noqa: E402


class AuthRoutesTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

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

    def test_login_redirects_back_to_requested_index(self):
        login_page = self.client.get("/login?next=/")

        self.assertEqual(login_page.status_code, 200)
        self.assertIn('name="next"', login_page.text)

        login_response = self.client.post(
            "/login",
            data={"username": "admin", "password": "admin123", "next": "/"},
            follow_redirects=False,
        )

        self.assertEqual(login_response.status_code, 303)
        self.assertEqual(login_response.headers["location"], "/")

        index_response = self.client.get("/")

        self.assertEqual(index_response.status_code, 200)
        self.assertIn('id="app"', index_response.text)

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


if __name__ == "__main__":
    unittest.main()

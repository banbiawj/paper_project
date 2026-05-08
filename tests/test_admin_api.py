import json
import os
import shutil
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from main import _create_session_token, app


class AdminApiTest(unittest.TestCase):
    def setUp(self):
        self.workspace_tmp = Path.cwd() / ".test-tmp"
        self.workspace_tmp.mkdir(exist_ok=True)
        self.data_root = self.workspace_tmp / f"data-{uuid.uuid4().hex}"
        self.data_root.mkdir()
        os.environ["DS_MEMORY_DATA_ROOT"] = str(self.data_root)
        self._seed_data()
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("DS_MEMORY_DATA_ROOT", None)
        shutil.rmtree(self.data_root, ignore_errors=True)
        try:
            self.workspace_tmp.rmdir()
        except OSError:
            pass

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
        self.assertEqual(
            [item["word"] for item in search.json()["data"]["entries"]],
            ["测试词"],
        )

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
            params={
                "type_name": "idiom",
                "book": "测试书籍",
                "category": "query.json",
                "keyword": "测试词改",
            },
        )
        self.assertEqual(updated.json()["data"]["entries"][0]["explain"], "新的说明")

        delete_entry = self.client.request(
            "DELETE",
            "/api/v1/admin/entries",
            json={
                "type_name": "idiom",
                "book": "测试书籍",
                "category": "专项.json",
                "word": "测试词改",
            },
        )
        self.assertEqual(delete_entry.status_code, 200)

        deleted = self.client.get(
            "/api/v1/admin/entries",
            params={
                "type_name": "idiom",
                "book": "测试书籍",
                "category": "query.json",
                "keyword": "测试词改",
            },
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

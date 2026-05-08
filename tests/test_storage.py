import json
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.workspace_tmp = Path.cwd() / ".test-tmp"
        self.workspace_tmp.mkdir(exist_ok=True)
        self.data_root = self.workspace_tmp / f"storage-data-{uuid.uuid4().hex}"
        self.data_root.mkdir()
        self.db_path = Path(tempfile.gettempdir()) / f"ds-memory-storage-{uuid.uuid4().hex}.sqlite3"
        os.environ["DS_MEMORY_DATA_ROOT"] = str(self.data_root)
        os.environ["DS_MEMORY_DB_PATH"] = str(self.db_path)

    def tearDown(self):
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

    def _write_json(self, relative_path, data):
        path = self.data_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

    def _seed_json_data(self):
        self._write_json(
            "users.json",
            [
                {
                    "id": "u1",
                    "username": "alice",
                    "email": "alice@example.com",
                    "password_hash": "hash",
                    "role": "user",
                    "status": "active",
                    "created_at": "2026-05-08 10:00:00",
                    "updated_at": "2026-05-08 10:00:00",
                    "last_login_at": "",
                }
            ],
        )
        self._write_json(
            Path("words") / "词库" / "query.json",
            [{"word": "alpha", "explain": "shared", "note": "", "source": "fixture"}],
        )
        self._write_json(Path("words") / "词库" / "default.json", [])
        self._write_json(
            Path("idiom") / "词库" / "query.json",
            [{"word": "成语", "explain": "shared idiom", "note": ""}],
        )
        self._write_json(Path("idiom") / "词库" / "default.json", [])
        self._write_json(
            Path("user_data") / "u1" / "words" / "词库" / "query.json",
            [{"word": "private", "explain": "user only", "note": ""}],
        )
        self._write_json(Path("user_data") / "u1" / "words" / "词库" / "default.json", [])

    def test_migrate_json_to_sqlite_imports_users_and_libraries(self):
        from app import storage

        self._seed_json_data()

        result = storage.migrate_json_to_sqlite(self.data_root)

        self.assertEqual(result["users"], 1)
        self.assertEqual(result["books"], 3)
        self.assertEqual(storage.list_users()[0]["username"], "alice")
        self.assertEqual(storage.list_books(None, "words"), ["词库"])
        self.assertEqual(storage.list_categories(None, "words", "词库"), ["query.json", "default.json"])
        shared_entries = storage.read_entries(None, "words", "词库", "query.json")
        private_entries = storage.read_entries("u1", "words", "词库", "query.json")
        self.assertEqual(shared_entries[0]["word"], "alpha")
        self.assertEqual(shared_entries[0]["source"], "fixture")
        self.assertEqual(private_entries[0]["word"], "private")

    def test_migration_is_idempotent(self):
        from app import storage

        self._seed_json_data()

        storage.migrate_json_to_sqlite(self.data_root)
        storage.migrate_json_to_sqlite(self.data_root)

        self.assertEqual(len(storage.list_users()), 1)
        self.assertEqual(len(storage.read_entries(None, "words", "词库", "query.json")), 1)
        self.assertEqual(len(storage.read_entries("u1", "words", "词库", "query.json")), 1)

    def test_new_user_library_starts_empty_instead_of_copying_shared_entries(self):
        from app import storage

        self._seed_json_data()
        users_path = self.data_root / "users.json"
        users = json.loads(users_path.read_text(encoding="utf-8"))
        users.append(
            {
                "id": "u2",
                "username": "bob",
                "email": "bob@example.com",
                "password_hash": "hash",
                "role": "user",
                "status": "active",
                "created_at": "2026-05-08 10:00:00",
                "updated_at": "2026-05-08 10:00:00",
                "last_login_at": "",
            }
        )
        users_path.write_text(json.dumps(users, ensure_ascii=False, indent=4), encoding="utf-8")
        storage.migrate_json_to_sqlite(self.data_root)

        storage.ensure_user_libraries("u2")

        self.assertEqual(storage.list_books("u2", "words"), ["词库"])
        self.assertEqual(storage.list_categories("u2", "words", "词库"), ["query.json", "default.json"])
        self.assertEqual(storage.read_entries("u2", "words", "词库", "query.json"), [])
        self.assertEqual(storage.read_entries("u2", "idiom", "词库", "query.json"), [])


if __name__ == "__main__":
    unittest.main()

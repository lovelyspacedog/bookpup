import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path

import lib.accounts as accounts
import lib.core as core
from lib import file_digest, kosync


class KosyncAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps({"username": "book", "password": "secret123", "port": 18478})
        )
        accounts.reload_accounts()

    def tearDown(self) -> None:
        accounts._cache = None
        self.tmp.cleanup()

    def test_auth_md5_password(self):
        cfg = {"username": "book", "password": "secret123"}
        key = hashlib.md5(b"secret123").hexdigest()
        headers = {"X-Auth-User": "book", "X-Auth-Key": key}
        self.assertEqual(kosync.auth_user(headers, cfg), "book")
        self.assertIsNone(kosync.auth_user({**headers, "X-Auth-Key": "bad"}, cfg))

    def test_kosync_create_user_accounts_json(self) -> None:
        accounts.create_user("bob", "secret456")
        cfg = {"username": "book", "password": "secret123"}
        key = hashlib.md5(b"secret456").hexdigest()
        code, data = kosync.create_user({"username": "bob", "password": key}, cfg)
        self.assertEqual(code, 201)
        self.assertEqual(data.get("username"), "bob")


class KosyncPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        from lib import user_paths

        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        kosync.KOSYNC_STATE = core.CONFIG_DIR / "kosync.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps({"username": "book", "password": "secret123", "port": 18478})
        )
        accounts.reload_accounts()
        user_paths.set_user("book")

    def tearDown(self) -> None:
        from lib import user_paths

        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()

    def _put(self, document: str) -> tuple[int, dict]:
        return kosync.put_progress(
            {
                "document": document,
                "progress": "12",
                "percentage": 0.5,
                "device": "kobo",
            }
        )

    def test_concurrent_put_preserves_json(self) -> None:
        from lib import user_paths

        docs = [f"{i:032x}" for i in range(40)]

        def worker(doc: str) -> None:
            user_paths.set_user("book")
            code, _ = self._put(doc)
            self.assertEqual(code, 200)

        threads = [threading.Thread(target=worker, args=(d,)) for d in docs]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        payload = json.loads(kosync.KOSYNC_STATE.read_text())
        self.assertEqual(len(payload.get("documents") or {}), len(docs))

    def test_document_cap_rejects_new_keys(self) -> None:
        orig = kosync.MAX_DOCUMENTS
        kosync.MAX_DOCUMENTS = 3
        try:
            for i in range(3):
                code, _ = self._put(f"{i:032x}")
                self.assertEqual(code, 200)
            code, body = self._put("f" * 32)
            self.assertEqual(code, 507)
            self.assertEqual(body.get("code"), 2005)
            code, _ = self._put(f"{0:032x}")
            self.assertEqual(code, 200)
        finally:
            kosync.MAX_DOCUMENTS = orig

    def test_invalid_document_rejected(self) -> None:
        code, body = self._put("not-a-valid-document-id")
        self.assertEqual(code, 400)
        self.assertEqual(body.get("code"), 2002)


class PartialMd5Test(unittest.TestCase):
    def test_partial_md5_stable(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"x" * 5000)
            path = Path(tmp.name)
        try:
            a = file_digest.partial_md5(path)
            b = file_digest.partial_md5(path)
            self.assertEqual(a, b)
            self.assertEqual(len(a), 32)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
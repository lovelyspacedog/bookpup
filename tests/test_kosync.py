import hashlib
import json
import tempfile
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
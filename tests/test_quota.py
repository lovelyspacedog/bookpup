import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.quota as quota
import lib.user_paths as user_paths


class QuotaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        core._config = {
            "username": "book",
            "password": "test",
            "port": 18478,
            "library_quota_bytes": 1000,
        }
        core.ensure_dirs()
        core.CONFIG_FILE.write_text('{"username":"book","password":"test","port":18478,"library_quota_bytes":1000}\n')
        accounts.reload_accounts()
        user_paths.set_user("book")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_under_quota(self) -> None:
        f = user_paths.library_dir("book") / "a.epub"
        f.write_bytes(b"x" * 100)
        usage = quota.library_usage()
        self.assertEqual(usage["used_bytes"], 100)
        quota.assert_can_store(500)

    def test_over_quota(self) -> None:
        f = user_paths.library_dir("book") / "a.epub"
        f.write_bytes(b"x" * 900)
        with self.assertRaises(ValueError):
            quota.assert_can_store(200)

    def test_quota_includes_derived(self) -> None:
        d = user_paths.derived_dir("book")
        d.mkdir(parents=True, exist_ok=True)
        (d / "cache.epub").write_bytes(b"x" * 300)
        f = user_paths.library_dir("book") / "a.epub"
        f.write_bytes(b"x" * 100)
        usage = quota.library_usage()
        self.assertEqual(usage["used_bytes"], 400)


if __name__ == "__main__":
    unittest.main()
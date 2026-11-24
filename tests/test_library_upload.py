import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.library as library
import lib.user_paths as user_paths


class LibraryUploadTests(unittest.TestCase):
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
            "library_quota_bytes": 50 * 1024 * 1024,
        }
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            '{"username":"book","password":"test","port":18478,"library_quota_bytes":52428800}\n'
        )
        accounts.reload_accounts()
        user_paths.set_user("book")
        user_paths.ensure_user_dirs("book")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_add_upload_txt(self) -> None:
        data = b"hello bookpup upload test\n"
        item = library.add_upload(data, "my-sample.txt", title_hint="My Sample")
        self.assertEqual(item["source"], "download")
        self.assertEqual(item["format"], "txt")
        self.assertEqual(item["title"], "My Sample")


if __name__ == "__main__":
    unittest.main()
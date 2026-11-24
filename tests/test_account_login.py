import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.user_paths as user_paths


class AccountLoginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps({"username": "alice", "password": "old", "port": 18478})
        )
        accounts.reload_accounts()
        accounts.create_user("bob", "bobpw", quota_bytes=1_000_000)
        user_paths.ensure_user_dirs("alice")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_change_own_password(self) -> None:
        out = accounts.change_own_login("alice", current_password="old", new_password="new")
        self.assertEqual(out, "alice")
        self.assertTrue(accounts.verify_password("alice", "new"))

    def test_rename_user_moves_dir(self) -> None:
        mark = user_paths.user_root("alice") / "library" / "x.epub"
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_bytes(b"z")
        accounts.rename_user("alice", "alicia")
        self.assertIsNone(accounts.get_user("alice"))
        self.assertTrue(accounts.get_user("alicia"))
        self.assertTrue(user_paths.user_root("alicia").is_dir())
        self.assertFalse(user_paths.user_root("alice").exists())


if __name__ == "__main__":
    unittest.main()
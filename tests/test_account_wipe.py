import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.jobs as jobs
import lib.library as library
import lib.user_paths as user_paths
import lib.user_wipe as user_wipe


class AccountWipeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps({"username": "alice", "password": "secret", "port": 18478})
        )
        accounts.reload_accounts()
        user_paths.set_user("alice")
        user_paths.ensure_user_dirs("alice")
        library.add_bytes("Test", b"epub-bytes", "epub", source="calibre_import")
        jobs.create_job("search", owner="alice", query="test")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_wipe_clears_data_keeps_login(self) -> None:
        prev = user_wipe.wipe_preview("alice", "alice")
        phrase = prev["phrase"]
        self.assertEqual(len(phrase.split()), 12)
        user_wipe.wipe_account("alice", current_password="secret", phrase=phrase, target="alice")
        user_paths.set_user("alice")
        self.assertEqual(library.list_items(), [])
        self.assertTrue(accounts.verify_password("alice", "secret"))
        owner_jobs = [j for j in jobs.list_jobs() if j.get("owner") == "alice"]
        self.assertEqual(owner_jobs, [])

    def test_wrong_phrase_rejected(self) -> None:
        with self.assertRaises(ValueError):
            user_wipe.wipe_account(
                "alice", current_password="secret", phrase="wrong words", target="alice"
            )

    def test_admin_wipes_other_pup(self) -> None:
        accounts.create_user("bob", "bobpw", quota_bytes=1_000_000)
        user_paths.ensure_user_dirs("bob")
        user_paths.set_user("bob")
        library.add_bytes("Bob book", b"data", "epub", source="calibre_import")
        user_paths.set_user("alice")
        accounts.update_user("alice", {"admin": True})
        prev = user_wipe.wipe_preview("alice", "bob")
        user_wipe.wipe_account(
            "alice",
            current_password="secret",
            phrase=prev["phrase"],
            target="bob",
        )
        user_paths.set_user("bob")
        self.assertEqual(library.list_items(), [])
        self.assertTrue(accounts.verify_password("bob", "bobpw"))


if __name__ == "__main__":
    unittest.main()
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
import lib.transfer as transfer
import lib.user_paths as user_paths
from lib.staging import create_staging


class TransferTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(
            json.dumps(
                {
                    "username": "alice",
                    "password": "pw",
                    "port": 18478,
                    "library_quota_bytes": 10_000_000,
                }
            )
        )
        accounts.reload_accounts()
        accounts.create_user("bob", "pw2", quota_bytes=10_000_000)
        user_paths.set_user("alice")
        library.add_bytes("Test book", b"x" * 500, "epub", source="registered")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_send_library_copy(self) -> None:
        item = library.list_items()[0]
        out = transfer.send_library_item("alice", "bob", item["id"])
        self.assertNotEqual(out["id"], item["id"])
        user_paths.set_user("alice")
        self.assertEqual(len(library.list_items()), 1)
        user_paths.set_user("bob")
        self.assertEqual(len(library.list_items()), 1)
        self.assertEqual(library.list_items()[0]["title"], "Test book")

    def test_send_to_self(self) -> None:
        item = library.list_items()[0]
        with self.assertRaises(ValueError):
            transfer.send_library_item("alice", "alice", item["id"])

    def test_send_staging(self) -> None:
        job = jobs.create_job("download", owner="alice", title="IRC book")
        sid = job["id"]
        create_staging(sid)
        raw = core.STAGING_DIR / sid / "raw.epub"
        raw.write_bytes(b"y" * 300)
        jobs.save_job({**job, "staging_id": sid, "state": "done"})
        item = transfer.send_staging("alice", "bob", sid, title_hint="IRC book")
        user_paths.set_user("bob")
        self.assertEqual(item["title"], "IRC book")
        self.assertEqual(len(library.list_items()), 1)


if __name__ == "__main__":
    unittest.main()
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.accounts as accounts
import lib.core as core
import lib.admin_digest as admin_digest
import lib.jobs as jobs


class AdminDigestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        accounts.ACCOUNTS_FILE = core.CONFIG_DIR / "accounts.json"
        core._config = {"username": "book", "password": "x", "library_quota_bytes": 1_000_000}
        core.ensure_dirs()
        accounts.ACCOUNTS_FILE.write_text(
            '{"version":1,"users":[{"username":"book","password":"x","admin":true,"enabled":true,"quota_bytes":1000000}]}\n'
        )
        accounts.reload_accounts()

    def tearDown(self) -> None:
        accounts._cache = None
        self.tmp.cleanup()
        core._config = None

    def test_digest_shape(self) -> None:
        d = admin_digest.build_digest()
        self.assertIn("pups", d)
        self.assertIn("irc", d)
        self.assertTrue(d["pups"])
        self.assertIn("walk_trail", d)
        wt = d["walk_trail"]
        self.assertIn("incomplete_usernames", wt)
        self.assertIn("walk_trail_complete", d["pups"][0])
        self.assertFalse(d["pups"][0].get("walk_trail_complete"))


if __name__ == "__main__":
    unittest.main()
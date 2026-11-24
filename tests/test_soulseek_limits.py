import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import lib.accounts as accounts
import lib.core as core
import lib.soulseek_limits as soulseek_limits
from lib.soulseek_limits import SoulseekLimitError


class SoulseekLimitsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self._tmpdir.name)
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core._config = None
        core.ensure_dirs()
        accounts._cache = None
        accounts._cache_mtime = None
        core.CONFIG_FILE.write_text(
            '{"username":"admin","password":"x","soulseek_limits":{"searches_per_hour":2,"downloads_per_day":1,"concurrent_downloads":3}}\n'
        )
        (core.CONFIG_DIR / "accounts.json").write_text(
            '{"version":1,"users":[{"username":"admin","password":"x","admin":true,"enabled":true,"quota_bytes":1000},{"username":"pup","password":"x","admin":false,"enabled":true,"quota_bytes":1000}]}\n'
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_search_cap_non_admin(self) -> None:
        soulseek_limits.record_search("pup")
        soulseek_limits.record_search("pup")
        with self.assertRaises(SoulseekLimitError):
            soulseek_limits.assert_search_allowed("pup")

    def test_admin_exempt_search(self) -> None:
        for _ in range(5):
            soulseek_limits.record_search("admin")
        soulseek_limits.assert_search_allowed("admin")

    def test_limits_snapshot(self) -> None:
        lim = soulseek_limits.limits_for_user("pup")
        self.assertEqual(lim["searches_per_hour"], 2)
        self.assertIn("searches_remaining", lim)


if __name__ == "__main__":
    unittest.main()
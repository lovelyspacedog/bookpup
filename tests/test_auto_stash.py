import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
import lib.jobs as jobs
import lib.library as library
import lib.user_paths as user_paths
from lib.staging import create_staging


class AutoStashTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.CONFIG_FILE = core.CONFIG_DIR / "config.json"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        core.ensure_dirs()
        core.CONFIG_FILE.write_text(json.dumps({"username": "tony", "password": "pw", "port": 18478}))
        user_paths.set_user("tony")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        self.tmp.cleanup()
        core._config = None

    def test_auto_stash_from_job_idempotent(self) -> None:
        job = jobs.create_job("download", owner="tony", title="Penny the Basset")
        sid = job["id"]
        create_staging(sid)
        (core.STAGING_DIR / sid / "raw.epub").write_bytes(b"epub-bytes" * 20)
        job = {**job, "staging_id": sid, "raw_bytes": 240, "state": "running"}
        first = library.auto_stash_from_job(job)
        self.assertIsNotNone(first)
        self.assertEqual(first["title"], "Penny the Basset")
        self.assertEqual(first["staging_id"], sid)
        second = library.auto_stash_from_job(job)
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(len(library.list_items()), 1)


if __name__ == "__main__":
    unittest.main()
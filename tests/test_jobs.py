import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
import lib.jobs as jobs


class JobsCancelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.ensure_dirs()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_complete_search_no_matches(self) -> None:
        job = jobs.create_job("search", query="The Skyrim Library", channel="ebooks")
        touched = jobs.complete_search_no_matches(
            "The Skyrim Library", 'no matches for "The Skyrim Library"'
        )
        self.assertIn(job["id"], touched)
        again = jobs.load_job(job["id"])
        self.assertEqual(again["state"], "done")
        self.assertEqual(again["result_count"], 0)

    def test_dismiss_error(self) -> None:
        job = jobs.create_job("search", query="x", channel="ebooks")
        job["state"] = "error"
        job["error"] = "DCC timed out"
        jobs.save_job(job)
        jobs.dismiss_job(job["id"])
        with self.assertRaises(KeyError):
            jobs.load_job(job["id"])

    def test_cancel_queued(self) -> None:
        job = jobs.create_job("search", query="test", channel="ebooks")
        out = jobs.cancel_job(job["id"])
        self.assertEqual(out["state"], "cancelled")

    def test_recent_done_download_scoped_to_viewer(self) -> None:
        import time

        bob = jobs.create_job(
            "download",
            owner="bob",
            state="done",
            raw_bytes=100,
            title="Bob book",
        )
        bob["updated_at"] = time.time()
        jobs.save_job(bob)
        alice = jobs.create_job(
            "download",
            owner="alice",
            state="done",
            raw_bytes=200,
            title="Alice book",
        )
        alice["updated_at"] = time.time() + 1
        jobs.save_job(alice)
        admin_view = jobs.recent_done_download(owner="admin", admin=True)
        self.assertIsNone(admin_view)
        self.assertEqual(jobs.recent_done_download(owner="alice")["id"], alice["id"])
        self.assertEqual(jobs.recent_done_download(owner="bob")["id"], bob["id"])


if __name__ == "__main__":
    unittest.main()
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


if __name__ == "__main__":
    unittest.main()
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
import lib.jobs as jobs
from lib.irc_worker import IrcWorker


class IrcIdleQueueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core._config = {"username": "book", "password": "x", "port": 1}
        core.ensure_dirs()
        self.worker = IrcWorker()

    def tearDown(self) -> None:
        self.tmp.cleanup()
        core._config = None

    def test_active_when_queued_job_on_disk(self) -> None:
        jobs.create_job("search", query="test")
        self.assertTrue(self.worker._has_active_queue_work())

    def test_idle_when_only_done_jobs(self) -> None:
        job = jobs.create_job("search", query="done")
        job["state"] = "done"
        jobs.save_job(job)
        self.assertFalse(jobs.queue_has_active_work())
        self.assertFalse(self.worker._has_active_queue_work())


if __name__ == "__main__":
    unittest.main()
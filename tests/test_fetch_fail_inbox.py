import tempfile
import unittest
from pathlib import Path

from lib import core, fetch_fail_inbox, irc_feed, jobs


class FetchFailInboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.ensure_dirs()
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        fetch_fail_inbox.INBOX_FILE = core.CONFIG_DIR / "fetch_fail_inbox.json"
        with fetch_fail_inbox._lock:
            fetch_fail_inbox._loaded = False
            fetch_fail_inbox._entries.clear()
            fetch_fail_inbox._next_id = 1
        with irc_feed._lock:
            irc_feed._events.clear()
            irc_feed._seq = 0

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_record_and_markdown(self) -> None:
        irc_feed.append_out("#ebooks", "!get 123")
        irc_feed.append_session("Download refused: no slot")
        job = jobs.create_job(
            "download",
            owner="alice",
            title="Test Book",
            command="!get 1",
            channel="irchighway:ebooks",
            feed_seq_start=0,
        )
        job["state"] = "error"
        job["error"] = "Bot refused"
        jobs.save_job(job)
        eid = fetch_fail_inbox.record_failed_download(job)
        self.assertEqual(eid, 1)
        inbox = fetch_fail_inbox.list_inbox()
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["from"], "alice")
        md = fetch_fail_inbox.get_markdown(1)
        self.assertIn("Test Book", md)
        self.assertIn("Bot refused", md)
        self.assertIn("Den chatter", md)
        self.assertIn("!get 123", md)

    def test_fail_download_job_hook(self) -> None:
        job = jobs.create_job("download", owner="bob", error="nope")
        job["state"] = "error"
        jobs.save_job(job)
        jobs.fail_download_job(job, notify=False)
        self.assertEqual(len(fetch_fail_inbox.list_inbox()), 1)

    def test_dismiss(self) -> None:
        job = jobs.create_job("download", owner="bob", error="fail")
        job["state"] = "error"
        fetch_fail_inbox.record_failed_download(job)
        fetch_fail_inbox.dismiss_entry(1)
        self.assertEqual(fetch_fail_inbox.list_inbox(), [])
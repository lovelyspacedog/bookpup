import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
import lib.user_paths as user_paths
from lib import search_workspace
from lib.sniff_fingerprint import fingerprint_row


def _row(title: str = "Book", **extra) -> dict:
    base = {
        "server": "Bsk",
        "title": title,
        "command": "!Bsk " + title + ".epub",
        "display": "!Bsk " + title + ".epub",
    }
    base.update(extra)
    return base


class SniffFingerprintTest(unittest.TestCase):
    def test_irc_row_key(self) -> None:
        r = _row("The Hobbit")
        k1 = fingerprint_row(r)
        k2 = fingerprint_row(_row("The Hobbit"))
        self.assertEqual(k1, k2)
        self.assertIn("hobbit", k1.lower())

    def test_xdcc_row_key(self) -> None:
        r = _row(
            "Pack",
            download_kind="xdcc",
            network="irc",
            xdcc={"botname": "Bot", "slot": 3},
            command="",
        )
        k = fingerprint_row(r)
        self.assertIn("Bot|3", k)


class ScheduleDiffTest(unittest.TestCase):
    def test_diff_new_rows(self) -> None:
        rows = [_row("A"), _row("B")]
        keys = [fingerprint_row(rows[0])]
        new_rows, new_keys = search_workspace.diff_new_rows(rows, keys)
        self.assertEqual(len(new_rows), 1)
        self.assertEqual(new_rows[0]["title"], "B")
        self.assertEqual(len(new_keys), 1)


class ScheduledSniffRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core._config = {"username": "book", "password": "x", "port": 1}
        core.ensure_dirs()
        user_paths.set_user("pup")
        user_paths.ensure_user_dirs("pup")
        acc = core.CONFIG_DIR / "accounts.json"
        acc.write_text(
            json.dumps(
                {
                    "version": 1,
                    "users": [{"username": "pup", "password": "x", "admin": False, "enabled": True}],
                }
            )
        )

    def tearDown(self) -> None:
        user_paths.set_user(None)
        self.tmp.cleanup()
        core._config = None

    def test_enable_schedule_baselines_seen_keys(self) -> None:
        rows = [_row("Alpha"), _row("Beta")]
        search_workspace.update_draft(
            {"query": "alpha", "channel": "irchighway:ebooks", "results": rows}
        )
        out = search_workspace.save_draft_as("Watch Alpha")
        saved_id = out["id"]
        ws = search_workspace.update_saved_schedule(saved_id, {"enabled": True, "interval_hours": 24})
        item = next(x for x in ws["saved"] if x["id"] == saved_id)
        self.assertTrue(item["schedule"]["enabled"])
        data = search_workspace._load_raw()  # noqa: SLF001
        raw = next(x for x in data["saved"] if x["id"] == saved_id)
        self.assertEqual(len(raw["schedule"]["seen_keys"]), 2)

    @mock.patch("lib.search_workspace.accounts.list_users", return_value=[{"username": "pup"}])
    @mock.patch("lib.scheduled_sniff.search_run.run_search_job_for_user")
    @mock.patch("lib.scheduled_sniff.notify.sniff_watch_pm")
    def test_runner_notifies_on_new_row(self, mock_pm, mock_run, _mock_users) -> None:
        from lib import jobs
        from lib.scheduled_sniff import ScheduleRunner

        rows = [_row("Old")]
        search_workspace.update_draft(
            {"query": "q", "channel": "irchighway:ebooks", "results": rows}
        )
        out = search_workspace.save_draft_as("Notify test")
        saved_id = out["id"]
        search_workspace.update_saved_schedule(saved_id, {"enabled": True, "interval_hours": 6})
        data = search_workspace._load_raw()  # noqa: SLF001
        item = next(x for x in data["saved"] if x["id"] == saved_id)
        item["schedule"]["last_run_at"] = 0
        search_workspace._write(data)  # noqa: SLF001

        job = jobs.create_job(
            "search",
            query="q",
            channel="irchighway:ebooks",
            owner="pup",
            state="done",
            results=[_row("Old"), _row("Fresh")],
            result_count=2,
        )
        mock_run.return_value = job

        runner = ScheduleRunner()
        due = search_workspace.list_due_watches(now=9999999999)
        self.assertTrue(due)
        runner._run_watch(due[0])
        mock_pm.assert_called_once()
        self.assertEqual(mock_pm.call_args.kwargs.get("owner"), "pup")

    @mock.patch("lib.search_workspace.accounts.list_users", return_value=[{"username": "pup"}])
    @mock.patch("lib.scheduled_sniff.search_run.run_search_job_for_user")
    @mock.patch("lib.scheduled_sniff.notify.sniff_watch_digest_pm")
    @mock.patch("lib.scheduled_sniff.notify.sniff_watch_pm")
    def test_runner_digest_batches_watches(
        self, mock_pm, mock_digest, mock_run, _mock_users
    ) -> None:
        from lib import jobs
        from lib.scheduled_sniff import ScheduleRunner

        core._config = {
            "username": "book",
            "password": "x",
            "port": 1,
            "sniff_schedule_digest": True,
        }
        for name, title in (("Watch A", "Fresh A"), ("Watch B", "Fresh B")):
            search_workspace.update_draft(
                {"query": "q", "channel": "irchighway:ebooks", "results": [_row("Old")]}
            )
            out = search_workspace.save_draft_as(name)
            saved_id = out["id"]
            search_workspace.update_saved_schedule(saved_id, {"enabled": True, "interval_hours": 6})
            data = search_workspace._load_raw()  # noqa: SLF001
            item = next(x for x in data["saved"] if x["id"] == saved_id)
            item["schedule"]["last_run_at"] = 0
            search_workspace._write(data)  # noqa: SLF001

        def _job(_user: str, _q: str, _ch: str, *, wait: bool = False) -> dict:
            return jobs.create_job(
                "search",
                query="q",
                channel="irchighway:ebooks",
                owner="pup",
                state="done",
                results=[_row("Old"), _row("Fresh A"), _row("Fresh B")],
                result_count=3,
            )

        mock_run.side_effect = _job

        runner = ScheduleRunner()
        with mock.patch.object(runner, "_lock") as mock_lock:
            mock_lock.acquire.return_value = True
            runner._tick_once()

        mock_pm.assert_not_called()
        mock_digest.assert_called_once()
        entries = mock_digest.call_args.kwargs.get("entries") or []
        self.assertEqual(len(entries), 2)


if __name__ == "__main__":
    unittest.main()
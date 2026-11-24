import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
import lib.jobs as jobs
import lib.user_paths as user_paths
from lib import search_workspace


def _row(title: str = "Book") -> dict:
    return {
        "server": "Bsk",
        "title": title,
        "command": "!Bsk " + title + ".epub",
        "display": "!Bsk " + title + ".epub",
    }


class SearchWorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        core.CONFIG_DIR = base / "cfg"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core._config = {"username": "book", "password": "x", "port": 1}
        core.ensure_dirs()
        user_paths.set_user("pup")
        user_paths.ensure_user_dirs("pup")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        self.tmp.cleanup()
        core._config = None

    def test_draft_save_load_reorder_delete(self) -> None:
        rows = [_row("A"), _row("B")]
        search_workspace.update_draft(
            {"query": "glen", "channel": "all", "results": rows, "filter": "bsk"}
        )
        ws = search_workspace.get_workspace()
        self.assertEqual(ws["draft"]["result_count"], 2)
        self.assertEqual(ws["draft"]["filter"], "bsk")
        out = search_workspace.save_draft_as("My glen search")
        self.assertEqual(out["name"], "My glen search")
        saved_id = out["id"]
        self.assertEqual(len(out["workspace"]["saved"]), 1)
        draft = search_workspace.load_saved(saved_id)
        self.assertEqual(draft["query"], "glen")
        self.assertEqual(len(draft["results"]), 2)
        self.assertTrue(draft.get("job_id"))
        jobs.load_job(draft["job_id"])
        search_workspace.update_draft({"query": "other", "results": [_row("X")]})
        search_workspace.load_saved(saved_id)
        ws = search_workspace.get_workspace()
        self.assertEqual(ws["draft"]["query"], "glen")
        order = [saved_id]
        search_workspace.reorder_saved(order)
        search_workspace.delete_saved(saved_id)
        self.assertEqual(search_workspace.get_workspace()["saved"], [])

    def test_schedule_fields_in_workspace(self) -> None:
        rows = [_row()]
        search_workspace.update_draft({"query": "q", "channel": "irchighway:ebooks", "results": rows})
        out = search_workspace.save_draft_as("sched")
        ws = search_workspace.update_saved_schedule(out["id"], {"enabled": True, "interval_hours": 12})
        item = ws["saved"][0]
        self.assertTrue(item["schedule"]["enabled"])
        self.assertEqual(item["schedule"]["interval_hours"], 12)

    def test_max_saved(self) -> None:
        rows = [_row()]
        search_workspace.update_draft({"query": "q", "channel": "irchighway:ebooks", "results": rows})
        for i in range(search_workspace.MAX_SAVED):
            search_workspace.save_draft_as(f"s{i}")
        with self.assertRaises(ValueError):
            search_workspace.save_draft_as("one too many")
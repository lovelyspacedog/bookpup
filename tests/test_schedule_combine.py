import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
import lib.user_paths as user_paths
from lib import search_workspace


def _row(title: str = "Book") -> dict:
    return {
        "server": "Bsk",
        "title": title,
        "command": "!Bsk " + title + ".epub",
        "display": "!Bsk " + title + ".epub",
    }


class ScheduleCombineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core._config = {"username": "book", "password": "x", "port": 1}
        core.ensure_dirs()
        user_paths.set_user("pup")
        user_paths.ensure_user_dirs("pup")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        self.tmp.cleanup()
        core._config = None

    def _two_bookmarks(self) -> tuple[str, str]:
        search_workspace.update_draft(
            {"query": "a", "channel": "irchighway:ebooks", "results": [_row("A0")]}
        )
        a = search_workspace.save_draft_as("A")["id"]
        search_workspace.update_draft(
            {"query": "b", "channel": "irchighway:ebooks", "results": [_row("B0")]}
        )
        b = search_workspace.save_draft_as("B")["id"]
        return a, b

    def test_and_rule_blocks_partial_hits(self) -> None:
        a, b = self._two_bookmarks()
        search_workspace.update_schedule_combine_rules(
            [{"mode": "and", "saved_ids": [a, b], "name": "both"}]
        )
        entries = [
            {
                "saved_id": a,
                "owner": "pup",
                "watch_name": "A",
                "query": "a",
                "new_rows": [_row("Anew")],
            }
        ]
        out = search_workspace.filter_notify_entries("pup", entries, {a, b})
        self.assertEqual(out, [])

    def test_and_rule_passes_when_all_hit(self) -> None:
        a, b = self._two_bookmarks()
        search_workspace.update_schedule_combine_rules(
            [{"mode": "and", "saved_ids": [a, b]}]
        )
        entries = [
            {"saved_id": a, "new_rows": [_row("Anew")]},
            {"saved_id": b, "new_rows": [_row("Bnew")]},
        ]
        out = search_workspace.filter_notify_entries("pup", entries, {a, b})
        self.assertEqual(len(out), 2)

    def test_or_rule_keeps_any_hit(self) -> None:
        a, b = self._two_bookmarks()
        search_workspace.update_schedule_combine_rules(
            [{"mode": "or", "saved_ids": [a, b]}]
        )
        entries = [{"saved_id": a, "new_rows": [_row("Anew")]}]
        out = search_workspace.filter_notify_entries("pup", entries, {a, b})
        self.assertEqual(len(out), 1)

    def test_delete_saved_prunes_rules(self) -> None:
        a, b = self._two_bookmarks()
        search_workspace.update_schedule_combine_rules(
            [{"mode": "and", "saved_ids": [a, b]}]
        )
        search_workspace.delete_saved(a)
        ws = search_workspace.get_workspace()
        self.assertEqual(ws.get("schedule_combine_rules") or [], [])


if __name__ == "__main__":
    unittest.main()
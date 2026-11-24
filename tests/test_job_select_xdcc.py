import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import lib.core as core
import lib.jobs as jobs
from lib import irc_targets, job_select


class JobSelectXdccTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self._tmpdir.name)
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        core.ensure_dirs()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_create_xdcc_download(self) -> None:
        parent = jobs.create_job(
            "search",
            query="batman",
            channel=irc_targets.XDCC_INDEX_ID,
            owner="book",
        )
        parent["results"] = [
            {
                "download_kind": "xdcc",
                "title": "Batman.cbz",
                "command": "!xdcc #7",
                "irc_target": "xdcc:rizon",
                "xdcc": {
                    "botname": "Bot",
                    "slot": 7,
                    "channel": "#elitewarez",
                    "network": "rizon",
                    "server": "irc.rizon.net",
                    "port": 6667,
                    "use_tls": False,
                    "bot_id": "x",
                },
            }
        ]
        jobs.save_job(parent)

        def validated(cid: str) -> str:
            return core_handler_validated(cid)

        with mock.patch.object(job_select.worker, "enqueue"):
            dl = job_select.create_download_from_search(
                parent,
                command="!xdcc #7",
                title="Batman.cbz",
                irc_target="xdcc:rizon",
                owner="book",
                validated_channel=validated,
                row=parent["results"][0],
            )
        self.assertEqual(dl["download_kind"], "xdcc")
        self.assertEqual(dl["channel"], "xdcc:rizon")
        self.assertEqual(dl["xdcc"]["botname"], "Bot")


def core_handler_validated(cid: str) -> str:
    c = irc_targets.normalize_channel_id(cid)
    if c in (irc_targets.SEARCH_ALL_ID, irc_targets.XDCC_INDEX_ID):
        return c
    if irc_targets.is_xdcc_row_target(c):
        return c
    return irc_targets.resolve_target(c).id


if __name__ == "__main__":
    unittest.main()
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import lib.core as core
import lib.jobs as jobs
from lib import irc_targets, job_select


class JobSelectSoulseekTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self._tmpdir.name)
        core.JOBS_DIR = core.CONFIG_DIR / "jobs"
        core.STAGING_DIR = core.CONFIG_DIR / "staging"
        core.ensure_dirs()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_create_soulseek_download(self) -> None:
        parent = jobs.create_job(
            "search",
            query="title",
            channel=irc_targets.SOULSEEK_INDEX_ID,
            owner="pup",
        )
        parent["results"] = [
            {
                "download_kind": "soulseek",
                "title": "Title.epub",
                "command": "soulseek",
                "irc_target": irc_targets.SOULSEEK_INDEX_ID,
                "soulseek": {
                    "username": "peerone",
                    "filename": "Books/Title.epub",
                    "size": 1024,
                    "search_id": "abc",
                },
            }
        ]
        jobs.save_job(parent)

        def validated(cid: str) -> str:
            return cid

        with mock.patch.object(job_select.soulseek_limits, "assert_download_allowed"), mock.patch.object(
            job_select.soulseek_limits, "record_download"
        ), mock.patch.object(job_select.worker, "enqueue"):
            dl = job_select.create_download_from_search(
                parent,
                command="soulseek",
                title="Title.epub",
                irc_target=irc_targets.SOULSEEK_INDEX_ID,
                owner="pup",
                validated_channel=validated,
                row=parent["results"][0],
            )
        self.assertEqual(dl["download_kind"], "soulseek")
        self.assertEqual(dl["channel"], irc_targets.SOULSEEK_INDEX_ID)
        self.assertEqual(dl["soulseek"]["username"], "peerone")


if __name__ == "__main__":
    unittest.main()
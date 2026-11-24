import os
import tempfile
import unittest
from pathlib import Path

import lib.core as core
import lib.slskd_client as slskd_client
import lib.soulseek_search as soulseek_search


class SoulseekSearchTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._mock = os.environ.get("BOOKPUP_SLSKD_MOCK")
        os.environ["BOOKPUP_SLSKD_MOCK"] = "1"
        slskd_client.SLSKD_MOCK = True

    def tearDown(self) -> None:
        if self._mock is None:
            os.environ.pop("BOOKPUP_SLSKD_MOCK", None)
        else:
            os.environ["BOOKPUP_SLSKD_MOCK"] = self._mock
        self._tmpdir.cleanup()

    def test_search_mock_maps_bookish_rows(self) -> None:
        rows = soulseek_search.search_remote("rothfuss epub")
        self.assertGreaterEqual(len(rows), 2)
        kinds = {r["download_kind"] for r in rows}
        self.assertEqual(kinds, {"soulseek"})
        titles = {r["title"] for r in rows}
        self.assertIn("Title.epub", titles)
        self.assertIn("Another Book.mobi", titles)
        self.assertNotIn("album.flac", titles)

    def test_dedupe(self) -> None:
        payload = {
            "responses": [
                {
                    "username": "a",
                    "files": [
                        {"filename": "x/book.epub", "size": 1},
                        {"filename": "x/book.epub", "size": 1},
                    ],
                }
            ]
        }
        files = slskd_client.flatten_search(payload, search_id="id")
        rows = [soulseek_search._map_file(f) for f in files]
        rows = soulseek_search._dedupe(rows)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
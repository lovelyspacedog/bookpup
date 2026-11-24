import json
import os
import unittest
from pathlib import Path
from unittest import mock

import lib.xdcc_search as xdcc_search


class XdccSearchTest(unittest.TestCase):
    def setUp(self) -> None:
        self._mock = os.environ.get("BOOKPUP_XDCC_MOCK")
        os.environ["BOOKPUP_XDCC_MOCK"] = "1"
        xdcc_search.XDCC_MOCK = True
        xdcc_search.clear_bot_cache()

    def tearDown(self) -> None:
        if self._mock is None:
            os.environ.pop("BOOKPUP_XDCC_MOCK", None)
        else:
            os.environ["BOOKPUP_XDCC_MOCK"] = self._mock
        xdcc_search.clear_bot_cache()

    def test_search_mock_fixture(self) -> None:
        rows = xdcc_search.search("batman cbz")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["download_kind"], "xdcc")
        self.assertEqual(rows[0]["irc_target"], "xdcc:rizon")
        self.assertEqual(rows[0]["xdcc"]["slot"], 42)
        self.assertEqual(rows[0]["server"], "[EW]TestBot")
        self.assertEqual(rows[0]["command"], "!xdcc #42")

    def test_format_size(self) -> None:
        self.assertEqual(xdcc_search._format_size(512), "512 B")
        self.assertIn("MB", xdcc_search._format_size(52428800) or "")

    def test_map_http_payload(self) -> None:
        fixture = (
            Path(__file__).resolve().parent / "fixtures" / "xdcc_search_sample.json"
        )
        payload = json.loads(fixture.read_text())
        cache: dict[str, str] = {}
        with mock.patch.object(xdcc_search, "resolve_bot_server", return_value="irc.rizon.net"):
            row = xdcc_search._map_item(payload["data"][0], cache=cache)
        self.assertEqual(row["xdcc"]["server"], "irc.rizon.net")
        self.assertFalse(row["xdcc"]["use_tls"])


if __name__ == "__main__":
    unittest.main()
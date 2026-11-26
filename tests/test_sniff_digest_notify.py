import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import notify


class SniffDigestNotifyTest(unittest.TestCase):
    def test_digest_text_lists_bookmarks(self) -> None:
        text = notify._format_sniff_digest_alert(  # noqa: SLF001
            owner="pup",
            entries=[
                {
                    "watch_name": "Alpha",
                    "query": "hobbit",
                    "new_rows": [{"title": "The Hobbit"}],
                },
                {
                    "watch_name": "Beta",
                    "query": "lotr",
                    "new_rows": [{"title": "Fellowship"}],
                },
            ],
        )
        self.assertIn("digest", text.lower())
        self.assertIn("Alpha", text)
        self.assertIn("Beta", text)
        self.assertIn("Hobbit", text)


if __name__ == "__main__":
    unittest.main()
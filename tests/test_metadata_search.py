import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.metadata_search import _norm_isbn, _google_query, _dedupe_key


class MetadataSearchTest(unittest.TestCase):
    def test_isbn_norm(self) -> None:
        self.assertEqual(_norm_isbn("978-0-306-40615-7"), "9780306406157")

    def test_google_query_isbn_priority(self) -> None:
        q = _google_query("Title", "Author", "9780306406157")
        self.assertEqual(q, "isbn:9780306406157")

    def test_dedupe(self) -> None:
        a = {"isbn": "9780306406157", "title": "A", "authors": "B"}
        b = {"isbn": "9780306406157", "title": "Other", "authors": "C"}
        self.assertEqual(_dedupe_key(a), _dedupe_key(b))


if __name__ == "__main__":
    unittest.main()
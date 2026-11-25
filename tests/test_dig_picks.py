import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import dig_picks


class DigPicksCatalogTest(unittest.TestCase):
    def test_catalog_empty_warning(self) -> None:
        items, warnings = dig_picks.catalog_picks([])
        self.assertEqual(items, [])
        self.assertIn("catalog_empty", warnings)

    def test_catalog_author_pick(self) -> None:
        rows = [
            {"title": "Book A", "authors": "Alice Author", "tags": "", "series": ""},
            {"title": "Book B", "authors": "Alice Author", "tags": "", "series": ""},
        ]
        items, _ = dig_picks.catalog_picks(rows)
        self.assertTrue(any("Alice Author" in i["sniff_query"] for i in items))

    def test_in_kennel(self) -> None:
        self.assertTrue(dig_picks.in_kennel("The Hobbit", ["The Hobbit"]))


class DigBestsellersTest(unittest.TestCase):
    def test_bestseller_load_shape(self) -> None:
        items, meta = dig_picks.bestseller_picks([])
        self.assertGreaterEqual(len(items), 1)
        self.assertIn("updated", meta)
        self.assertEqual(items[0]["source"], "bestseller")


class DigOpenLibraryTest(unittest.TestCase):
    def test_ol_mock_and_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dig_picks.CACHE_DIR = Path(tmp)
            registered = [
                {"title": "Owned", "authors": "Test Writer", "tags": "", "series": ""},
            ]

            def fake_search(_t, author, _i):
                if author == "Test Writer":
                    return [
                        {
                            "title": "Brand New Title",
                            "authors": "Test Writer",
                            "cover_url": "",
                        }
                    ]
                return []

            items1, _ = dig_picks.openlibrary_picks(
                registered, ["Owned"], "pup1", search_fn=fake_search
            )
            self.assertEqual(len(items1), 1)
            self.assertEqual(items1[0]["title"], "Brand New Title")

            calls = {"n": 0}

            def counting_search(_t, _a, _i):
                calls["n"] += 1
                return []

            items2, _ = dig_picks.openlibrary_picks(
                registered, ["Owned"], "pup1", search_fn=counting_search
            )
            self.assertEqual(len(items2), 1)
            self.assertEqual(calls["n"], 0)


if __name__ == "__main__":
    unittest.main()
"""Catalog reading summaries for Kennel."""

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import lib.core as core
from lib import reading
from lib import user_paths


class ReadingCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        core.CONFIG_DIR = Path(self.tmp.name) / "cfg"
        core.ensure_dirs()
        user_paths.set_user("reader")

    def tearDown(self) -> None:
        user_paths.set_user(None)
        self.tmp.cleanup()

    def _write_reading(self, items: dict) -> None:
        path = user_paths.reading_state("reader")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"items": items}))

    def test_empty_location_omitted(self) -> None:
        self._write_reading({"book1": {"bookmarks": []}})
        out = reading.catalog_summaries("reader", ["book1"])
        self.assertEqual(out, {})

    def test_epub_in_progress_and_finished(self) -> None:
        self._write_reading(
            {
                "a": {
                    "location": {"type": "epub", "percentage": 0.5},
                    "updated_at": 100.0,
                },
                "b": {
                    "location": {"type": "epub", "percentage": 0.99},
                    "updated_at": 200.0,
                },
            }
        )
        out = reading.catalog_summaries("reader", ["a", "b"])
        self.assertTrue(out["a"]["in_progress"])
        self.assertEqual(out["a"]["progress_pct"], 50)
        self.assertFalse(out["b"]["in_progress"])
        self.assertEqual(out["b"]["progress_label"], "99%")

    def test_shared_catalog_key(self) -> None:
        self._write_reading(
            {
                "share:owner1:item99": {
                    "location": {"type": "epub", "percentage": 0.2},
                    "updated_at": 50.0,
                }
            }
        )
        out = reading.catalog_summaries(
            "reader", ["item99"], shared_catalog_owner="owner1"
        )
        self.assertEqual(len(out), 1)
        self.assertTrue(out["item99"]["in_progress"])

    def test_started_without_fraction(self) -> None:
        self._write_reading(
            {
                "x": {
                    "location": {"type": "epub", "cfi": "epubcfi(/6/4)"},
                    "updated_at": 1.0,
                }
            }
        )
        out = reading.catalog_summaries("reader", ["x"])
        self.assertEqual(out["x"]["progress_label"], "Started")
        self.assertTrue(out["x"]["in_progress"])


if __name__ == "__main__":
    unittest.main()
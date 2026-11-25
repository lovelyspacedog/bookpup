import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import dig_bestsellers_refresh


class DigBestsellersValidateTest(unittest.TestCase):
    def test_validate_ok(self) -> None:
        data = dig_bestsellers_refresh.validate_bestsellers_payload(
            {
                "updated": "2026-11-25",
                "attribution": "test",
                "items": [{"title": "A Book", "authors": "Ann"}],
            }
        )
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["title"], "A Book")

    def test_validate_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            dig_bestsellers_refresh.validate_bestsellers_payload({"items": []})

    def test_refresh_disabled_without_url(self) -> None:
        cfg = {"dig_bestsellers_url": "", "dig_bestsellers_refresh_enabled": True}
        self.assertFalse(dig_bestsellers_refresh.refresh_enabled(cfg))


if __name__ == "__main__":
    unittest.main()
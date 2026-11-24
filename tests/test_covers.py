import unittest

from lib.covers import COVER_MAX_BYTES, detect_format
from lib.cover_search import build_image_query


class CoversTest(unittest.TestCase):
    def test_detect_jpeg(self):
        data = b"\xff\xd8\xff" + b"\x00" * 100
        self.assertEqual(detect_format(data), "jpg")

    def test_detect_png(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        self.assertEqual(detect_format(data), "png")

    def test_reject_too_large(self):
        data = b"\xff\xd8\xff" + b"\x00" * (COVER_MAX_BYTES + 1)
        with self.assertRaises(ValueError):
            detect_format(data)

    def test_build_image_query_isbn(self):
        q = build_image_query(title="Foo", isbn="9780123456789")
        self.assertIn("9780123456789", q)
        self.assertIn("book cover", q)


if __name__ == "__main__":
    unittest.main()
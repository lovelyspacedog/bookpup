import unittest

from lib.wttr import normalize_us_zip


class WttrZipTests(unittest.TestCase):
    def test_valid_zip(self) -> None:
        self.assertEqual(normalize_us_zip("90210"), "90210")
        self.assertEqual(normalize_us_zip(" 10001 "), "10001")
        self.assertEqual(normalize_us_zip("10001-1234"), "10001")

    def test_invalid_zip(self) -> None:
        self.assertIsNone(normalize_us_zip(""))
        self.assertIsNone(normalize_us_zip("1234"))
        self.assertIsNone(normalize_us_zip("abcde"))
        self.assertIsNone(normalize_us_zip("123456"))


if __name__ == "__main__":
    unittest.main()
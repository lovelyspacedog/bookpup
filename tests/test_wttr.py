import unittest

from lib.wttr import forecast_from_j1, format_forecast_line, line_from_j1, normalize_us_zip


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

    def test_line_from_j1_city(self) -> None:
        payload = {
            "nearest_area": [{"areaName": [{"value": "Ocoee"}]}],
            "current_condition": [{"weatherCode": "176", "temp_F": "66", "temp_C": "19"}],
        }
        data = forecast_from_j1(payload)
        self.assertEqual(data["city"], "Ocoee")
        self.assertEqual(data["temp_f"], "66")
        self.assertEqual(data["temp_c"], "19")
        city, line = line_from_j1(payload)
        self.assertEqual(city, "Ocoee")
        self.assertIn("+66°F", line)
        self.assertEqual(format_forecast_line("Ocoee", "🌦️", "19", "C"), "Ocoee: 🌦️  +19°C")


if __name__ == "__main__":
    unittest.main()
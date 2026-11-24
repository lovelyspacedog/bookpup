import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lib import convert as convert_mod


class ConvertFormatsTests(unittest.TestCase):
    def test_prepare_view_native_md(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "book.md"
            src.write_text("# Hi\n", encoding="utf-8")
            with (
                mock.patch.object(convert_mod, "item_format", return_value="md"),
                mock.patch.object(convert_mod, "item_path", return_value=src),
            ):
                meta = convert_mod.prepare_view("abc")
                self.assertEqual(meta["format"], "md")
                self.assertFalse(meta["converted"])

    def test_prepare_view_calibre_fb2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            derived = root / "derived"
            derived.mkdir()
            src = root / "fb.fb2"
            src.write_bytes(b"<FictionBook/>")
            with (
                mock.patch.object(convert_mod, "item_format", return_value="fb2"),
                mock.patch.object(convert_mod, "item_path", return_value=src),
                mock.patch.object(convert_mod, "_derived_dir", return_value=derived),
                mock.patch.object(convert_mod, "_find_ebook_convert", return_value="/fake/ebook-convert"),
                mock.patch.object(convert_mod, "calibre_to_epub") as cal,
            ):
                cal.side_effect = lambda exe, s, dest: dest.write_bytes(b"PK\x03\x04 epub")
                meta = convert_mod.prepare_view("fb")
                self.assertEqual(meta["format"], "epub")
                self.assertTrue(meta["converted"])
                self.assertEqual(meta["source_format"], "fb2")
                self.assertTrue((derived / "fb.epub").is_file())


if __name__ == "__main__":
    unittest.main()
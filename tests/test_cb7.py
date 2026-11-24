import unittest
from pathlib import Path
from unittest import mock

from lib import cb7 as cb7_mod


class Cb7Tests(unittest.TestCase):
    def test_filter_images_skips_non_images(self) -> None:
        names = cb7_mod._filter_images(["02-b.png", "01-a.jpg", ".hidden", "readme.txt"])
        self.assertEqual(names, ["01-a.jpg", "02-b.png"])

    def test_page_count_and_bytes_via_7z(self) -> None:
        path = Path("/fake/book.cb7")

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["7z", "l", "-ba"]:
                out = b"2026-01-01 12:00:00 .....           10           10  01-a.jpg\n"
                return mock.Mock(returncode=0, stdout=out, stderr=b"")
            if cmd[:3] == ["7z", "e", "-so"]:
                return mock.Mock(returncode=0, stdout=b"jpegbytes", stderr=b"")
            raise AssertionError(f"unexpected cmd {cmd}")

        with (
            mock.patch.object(cb7_mod.shutil, "which", return_value="/usr/bin/7z"),
            mock.patch.object(cb7_mod.subprocess, "run", side_effect=fake_run),
        ):
            self.assertEqual(cb7_mod.page_count(path), 1)
            data, mime = cb7_mod.page_bytes(path, 0)
            self.assertEqual(data, b"jpegbytes")
            self.assertEqual(mime, "image/jpeg")
            meta = cb7_mod.comic_meta(path)
            self.assertEqual(meta, {"format": "cb7", "pages": 1})


if __name__ == "__main__":
    unittest.main()
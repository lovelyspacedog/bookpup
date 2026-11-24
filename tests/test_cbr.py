import unittest
from pathlib import Path
from unittest import mock

from lib import cbr as cbr_mod
from lib.comic_errors import ComicReadError


class CbrTests(unittest.TestCase):
    def test_filter_images_sorts(self) -> None:
        names = cbr_mod._filter_images(["02-b.png", "01-a.jpg", ".hidden", "readme.txt"])
        self.assertEqual(names, ["01-a.jpg", "02-b.png"])

    def test_comic_meta_via_7z(self) -> None:
        path = Path("/fake/book.cbr")

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["7z", "l", "-ba"]:
                out = b"2026-01-01 12:00:00 .....           10           10  01-a.jpg\n"
                return mock.Mock(returncode=0, stdout=out, stderr=b"")
            if cmd[:3] == ["7z", "e", "-so"]:
                return mock.Mock(returncode=0, stdout=b"jpegbytes", stderr=b"")
            raise AssertionError(f"unexpected cmd {cmd}")

        with (
            mock.patch.object(cbr_mod.shutil, "which", return_value="/usr/bin/7z"),
            mock.patch.object(cbr_mod.subprocess, "run", side_effect=fake_run),
            mock.patch.object(Path, "stat", return_value=mock.Mock(st_size=100)),
        ):
            self.assertEqual(cbr_mod.page_count(path), 1)
            data, mime = cbr_mod.page_bytes(path, 0)
            self.assertEqual(data, b"jpegbytes")
            self.assertEqual(mime, "image/jpeg")
            meta = cbr_mod.comic_meta(path)
            self.assertEqual(meta, {"format": "cbr", "pages": 1})

    def test_falls_back_to_unrar(self) -> None:
        path = Path("/fake/book.cbr")

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["7z", "l", "-ba"]:
                return mock.Mock(returncode=1, stdout=b"", stderr=b"7z failed\n")
            if cmd[:2] == ["unrar", "lb"]:
                return mock.Mock(returncode=0, stdout=b"page.jpg\n", stderr=b"")
            if cmd[:3] == ["7z", "e", "-so"]:
                return mock.Mock(returncode=1, stdout=b"", stderr=b"")
            if cmd[:2] == ["unrar", "p"]:
                return mock.Mock(returncode=0, stdout=b"img", stderr=b"")
            raise AssertionError(f"unexpected cmd {cmd}")

        def which(bin_name: str) -> str | None:
            return f"/usr/bin/{bin_name}"

        with (
            mock.patch.object(cbr_mod.shutil, "which", side_effect=which),
            mock.patch.object(cbr_mod.subprocess, "run", side_effect=fake_run),
        ):
            self.assertEqual(cbr_mod.page_count(path), 1)

    def test_raises_comic_error_with_debug(self) -> None:
        path = Path("/fake/bad.cbr")

        def fake_run(cmd, *args, **kwargs):
            return mock.Mock(returncode=1, stdout=b"", stderr=b"tool err\n")

        with (
            mock.patch.object(cbr_mod.shutil, "which", return_value="/usr/bin/7z"),
            mock.patch.object(cbr_mod.subprocess, "run", side_effect=fake_run),
        ):
            with self.assertRaises(ComicReadError) as ctx:
                cbr_mod.page_count(path)
            self.assertIn("7z", ctx.exception.debug_stderr)
            self.assertIn("unrar", ctx.exception.debug_stderr)


if __name__ == "__main__":
    unittest.main()
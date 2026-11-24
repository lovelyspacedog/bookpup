import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

from lib.gutenberg_fetch import (
    _attempt_gutenberg_fallback,
    _looks_like_html_error,
    resolve_gutenberg_id,
)
from lib import gutenberg_fetch


class GutenbergFetchTest(unittest.TestCase):
    def test_resolve_from_url(self) -> None:
        self.assertEqual(
            resolve_gutenberg_id(
                "Source: https://www.gutenberg.org/ebooks/10991",
            ),
            10991,
        )

    def test_resolve_from_get(self) -> None:
        self.assertEqual(resolve_gutenberg_id("!get 1059831"), 1059831)

    def test_attempt_for_get_refusal(self) -> None:
        self.assertTrue(
            _attempt_gutenberg_fallback(
                "!get 10991",
                "This work has no EPUB available.",
                "Dogs and All About Them",
            )
        )

    def test_skip_bsk_without_pg_hint(self) -> None:
        self.assertFalse(
            _attempt_gutenberg_fallback(
                "!Bsk Author - Title.epub",
                "No DCC from bald within 120s",
                "Author - Title.epub",
            )
        )

    def test_html_maintenance_detected(self) -> None:
        html = b"<!DOCTYPE html><html><title>Temporarily Down for Maintenance"
        self.assertTrue(_looks_like_html_error(html))
        self.assertFalse(_looks_like_html_error(b"PK\x03\x04" + b"x" * 200))

    def test_legacy_files_url_included(self) -> None:
        urls = [u for u, _ in gutenberg_fetch._candidate_urls(10991)]
        self.assertIn(
            "https://www.gutenberg.org/files/109/10991/10991-0.txt",
            urls,
        )

    def test_download_epub_first(self) -> None:
        import urllib.error
        import tempfile

        body = b"PK\x03\x04" + b"epub-bytes" * 20

        class Resp:
            status = 200

            def __init__(self, data: bytes) -> None:
                self._buf = BytesIO(data)

            def read(self, n: int = -1) -> bytes:
                return self._buf.read(n)

            def __enter__(self) -> "Resp":
                return self

            def __exit__(self, *args: object) -> None:
                pass

        def fake_open(req, timeout=0):
            url = req.full_url
            if url.endswith(".epub.noimages"):
                return Resp(body)
            raise urllib.error.HTTPError(url, 404, "", {}, None)

        dest = Path(tempfile.mkdtemp()) / "raw"
        with mock.patch("urllib.request.urlopen", side_effect=fake_open):
            url, ext, size = gutenberg_fetch._try_candidates(42, dest)
        self.assertEqual(ext, ".epub")
        self.assertIn(".epub.noimages", url)
        self.assertGreater(size, 100)
        self.assertTrue(dest.is_file())


if __name__ == "__main__":
    unittest.main()
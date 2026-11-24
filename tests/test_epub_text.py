import io
import unittest
import zipfile
from pathlib import Path

from lib import epub_text


def _minimal_epub(chapters: list[tuple[str, str]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        manifest = ""
        spine = ""
        for i, (cid, _title) in enumerate(chapters):
            manifest += f'<item id="{cid}" href="{cid}.xhtml" media-type="application/xhtml+xml"/>'
            spine += f'<itemref idref="{cid}"/>'
        zf.writestr(
            "content.opf",
            f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <manifest>{manifest}</manifest>
  <spine>{spine}</spine>
</package>""",
        )
        for cid, title in chapters:
            zf.writestr(
                f"{cid}.xhtml",
                f"<html><body><p>{title}</p><p>{'Word ' * 40}</p></body></html>",
            )
    return buf.getvalue()


class EpubTextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(__file__).resolve().parent / "_epub_test.epub"
        self.tmp.write_bytes(_minimal_epub([("ch1", "Alpha chapter"), ("ch2", "Beta chapter")]))

    def tearDown(self) -> None:
        self.tmp.unlink(missing_ok=True)

    def test_spine_zero(self) -> None:
        key, text, n = epub_text.extract_epub_chapter(self.tmp, spine_index=0)
        self.assertTrue(key.startswith("epub:"))
        self.assertIn("Alpha", text)
        self.assertGreaterEqual(n, epub_text.MIN_EXCERPT_CHARS)

    def test_spine_one(self) -> None:
        _key, text, _n = epub_text.extract_epub_chapter(self.tmp, spine_index=1)
        self.assertIn("Beta", text)

    def test_txt_window(self) -> None:
        p = self.tmp.with_suffix(".txt")
        body = "A" * 5000 + "MARKER" + "B" * 5000
        p.write_text(body, encoding="utf-8")
        try:
            _key, text, _n = epub_text.extract_txt_window(p, offset=5004, max_chars=8000)
            self.assertIn("MARKER", text)
        finally:
            p.unlink(missing_ok=True)
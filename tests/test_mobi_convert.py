import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.mobi_convert import _collapse_spaced_title, _sanitize_mobi7_nav


class MobiConvertTest(unittest.TestCase):
    def test_collapse_spaced_nav_title(self) -> None:
        self.assertEqual(_collapse_spaced_title("D ISCOVERY"), "DISCOVERY")
        self.assertEqual(_collapse_spaced_title("P ALANCARVALLEY"), "PALANCARVALLEY")
        self.assertEqual(_collapse_spaced_title("Chapter One"), "Chapter One")

    def test_sanitize_ncx_navlabel(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ncx = root / "toc.ncx"
            ncx.write_text(
                '<?xml version="1.0"?><ncx><navPoint><navLabel><text>D ISCOVERY</text>'
                "</navLabel></navPoint></ncx>\n",
                encoding="utf-8",
            )
            _sanitize_mobi7_nav(root)
            self.assertIn("<text>DISCOVERY</text>", ncx.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
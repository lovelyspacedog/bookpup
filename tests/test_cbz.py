import io
import unittest
import zipfile
from pathlib import Path
import tempfile

from lib import cbz as cbz_mod


class CbzTests(unittest.TestCase):
    def test_pages(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("01-a.jpg", b"fakejpeg")
            zf.writestr("02-b.png", b"fakepng")
        with tempfile.NamedTemporaryFile(suffix=".cbz", delete=False) as tmp:
            tmp.write(buf.getvalue())
            path = Path(tmp.name)
        try:
            self.assertEqual(cbz_mod.page_count(path), 2)
            data, mime = cbz_mod.page_bytes(path, 0)
            self.assertEqual(data, b"fakejpeg")
            self.assertEqual(mime, "image/jpeg")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
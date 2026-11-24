import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lib import soulseek_fetch


class SoulseekFetchResolveTest(unittest.TestCase):
    def test_remote_parent_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            parent = base / "Eragon (754)"
            parent.mkdir()
            book = parent / "Eragon - Christopher Paolini.epub"
            book.write_bytes(b"x" * 100)
            remote = r"books\Christopher Paolini\Eragon (754)\Eragon - Christopher Paolini.epub"
            transfer = {"size": 100}
            with mock.patch.object(soulseek_fetch.slskd_client, "download_root", return_value=str(base)):
                got = soulseek_fetch._resolve_local_file(transfer, remote)
            self.assertEqual(got, book)

    def test_find_under_root_by_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            deep = base / "misc" / "nested"
            deep.mkdir(parents=True)
            book = deep / "title.epub"
            book.write_bytes(b"y" * 42)
            found = soulseek_fetch._find_under_root(base, "title.epub", size_hint=42)
            self.assertEqual(found, book)


if __name__ == "__main__":
    unittest.main()
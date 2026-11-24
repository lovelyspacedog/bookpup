import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lib import core, library, user_paths


class LibraryGhostTest(unittest.TestCase):
    def test_prune_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp)
            core.CONFIG_DIR = cfg
            core.ensure_dirs()
            user_paths.set_user("ghosttest")
            user_paths.ensure_user_dirs("ghosttest")
            idx = user_paths.library_index()
            idx.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "gone123",
                                "title": "Ghost Book",
                                "filename": "gone123.epub",
                                "format": "epub",
                                "saved_at": 1,
                            }
                        ]
                    }
                )
            )
            with mock.patch.object(library, "prune_ghost_items", wraps=library.prune_ghost_items):
                n = library.prune_ghost_items()
            self.assertEqual(n, 1)
            self.assertEqual(library.list_items(prune=False), [])


if __name__ == "__main__":
    unittest.main()
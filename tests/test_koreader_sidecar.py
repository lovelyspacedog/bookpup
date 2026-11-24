import unittest

from lib.koreader_sidecar import (
    parse_metadata_lua,
    partial_id_from_archive_path,
    progress_from_sidecar,
)

SAMPLE = """
return {
    ["percent_finished"] = 0.42,
    ["last_xpointer"] = "/body/DocFragment[2]/body/p[5]",
    ["doc_path"] = "/mnt/Books/Test Book.epub",
    ["summary"] = { ["status"] = "reading", ["modified"] = "2025-01-02" },
    ["stats"] = { ["title"] = "Test Book", ["authors"] = "Someone" },
    ["text"] = "Highlighted line one",
}
"""


class KoreaderSidecarTest(unittest.TestCase):
    def test_partial_id_from_hash_sdr(self):
        hid = "b3fb8f4f8448160365087d6ca05c7fa2"
        path = f"koreader/docsettings/ab/{hid}.sdr/metadata.epub.lua"
        self.assertEqual(partial_id_from_archive_path(path), hid)

    def test_partial_id_from_named_sdr(self):
        path = "documents/Baking Yesteryear.epub.sdr/metadata.epub.lua"
        self.assertIsNone(partial_id_from_archive_path(path))

    def test_parse_progress(self):
        parsed = parse_metadata_lua(SAMPLE)
        pct, prog, status = progress_from_sidecar(parsed)
        self.assertAlmostEqual(pct or 0, 0.42)
        self.assertIn("DocFragment", prog or "")
        self.assertEqual(status, "reading")
        self.assertEqual((parsed.get("stats") or {}).get("title"), "Test Book")


if __name__ == "__main__":
    unittest.main()
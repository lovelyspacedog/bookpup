import unittest
import xml.etree.ElementTree as ET

from lib import opds as opds_mod
from lib import user_paths


class OpdsFeedTests(unittest.TestCase):
    def test_root_xml(self) -> None:
        body = opds_mod.feed_root("https://example.test")
        root = ET.fromstring(body)
        self.assertTrue(root.tag.endswith("feed"))

    def test_catalog_empty(self) -> None:
        user_paths.set_user("book")
        body = opds_mod.feed_catalog("https://example.test", "book")
        root = ET.fromstring(body)
        entries = root.findall("{http://www.w3.org/2005/Atom}entry")
        self.assertIsInstance(entries, list)


if __name__ == "__main__":
    unittest.main()
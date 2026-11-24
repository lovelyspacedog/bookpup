import unittest

from lib.irc_presence import ChannelPresence, strip_nick_prefix


class IrcPresenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.presence = ChannelPresence(("#bookz",))

    def test_353_and_366_populate(self) -> None:
        line353 = ":server 353 nick = #bookz :@Oatmeal PeppyLion pondering-ebooks2"
        line366 = ":server 366 nick #bookz :End of /NAMES list"
        self.presence.handle_server_line(line353)
        self.assertTrue(self.presence.is_in_channel("#bookz", "oatmeal"))
        self.presence.handle_server_line(line366)
        self.assertTrue(self.presence.wait_names_ready("#bookz", timeout=0.1))

    def test_join_part(self) -> None:
        self.presence.handle_server_line(":pondering-ebooks2!x JOIN :#bookz")
        self.assertTrue(self.presence.is_in_channel("#bookz", "pondering-ebooks2"))
        self.presence.handle_server_line(":pondering-ebooks2!x PART #bookz")
        self.assertFalse(self.presence.is_in_channel("#bookz", "pondering-ebooks2"))

    def test_strip_prefix(self) -> None:
        self.assertEqual(strip_nick_prefix("@Oatmeal"), "oatmeal")


if __name__ == "__main__":
    unittest.main()
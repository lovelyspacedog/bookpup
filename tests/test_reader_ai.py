import unittest
from unittest import mock

from lib import epub_text, reader_ai


class ReaderAiTest(unittest.TestCase):
    def test_cache_key_stable(self) -> None:
        with mock.patch("lib.reader_ai._config_ai", return_value={"prompt_version": 1, "model_id": "m.gguf"}):
            a = reader_ai.cache_key("item1", "epub:spine:0", "summarize")
            b = reader_ai.cache_key("item1", "epub:spine:0", "summarize")
            self.assertEqual(a, b)
            self.assertNotEqual(a, reader_ai.cache_key("item1", "epub:spine:1", "summarize"))

    def test_truncate(self) -> None:
        self.assertEqual(len(epub_text.truncate_for_model("hello", 3)), 3)
        self.assertTrue(epub_text.truncate_for_model("x" * 20, 10).endswith("…"))

    @mock.patch("lib.reader_ai.llama_local.chat", return_value="Summary bullets.")
    @mock.patch("lib.reader_ai._cache_read", return_value=None)
    @mock.patch("lib.reader_ai._cache_write")
    @mock.patch("lib.reader_ai.check_rate_limit")
    @mock.patch("lib.reader_ai.require_ai_enabled")
    @mock.patch(
        "lib.reader_ai._config_ai",
        return_value={"max_output_tokens": 128, "prompt_version": 1, "model_id": "m.gguf"},
    )
    def test_summarize_calls_llama(self, *_mocks) -> None:
        out = reader_ai.summarize("id", "epub:spine:0", "word " * 50, client_key="test")
        self.assertFalse(out["cached"])
        self.assertIn("Summary", out["summary"])
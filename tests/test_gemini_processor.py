import os
import unittest
from unittest.mock import Mock, patch

from modules.ai_processing.processor import process_document_text


class GeminiProcessorTests(unittest.TestCase):
    def test_returns_demo_response_without_api_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            result = process_document_text("A sample business document.")

        self.assertEqual(result["mode"], "demo")
        self.assertIn("GEMINI_API_KEY", " ".join(result["key_details"]))

    @patch("modules.ai_processing.processor.genai.Client")
    def test_sends_text_to_gemini_and_parses_structured_response(self, client_factory):
        response = Mock()
        response.text = (
            '{"summary":"A customer requested an address update.",'
            '"key_details":["Address update requested.","Customer record needs review."]}'
        )
        client = Mock()
        client.models.generate_content.return_value = response
        client_factory.return_value = client

        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-test-model"},
            clear=False,
        ):
            result = process_document_text("Customer requested an address update.")

        client_factory.assert_called_once_with(api_key="test-key")
        call = client.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-test-model")
        self.assertIn("Customer requested an address update.", call.kwargs["contents"])
        self.assertEqual(result["mode"], "gemini")
        self.assertEqual(result["summary"], "A customer requested an address update.")
        self.assertEqual(len(result["key_details"]), 2)

    @patch("modules.ai_processing.processor.genai.Client")
    def test_raises_when_gemini_returns_empty_text(self, client_factory):
        response = Mock()
        response.text = None
        client = Mock()
        client.models.generate_content.return_value = response
        client_factory.return_value = client

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with self.assertRaisesRegex(ValueError, "empty response"):
                process_document_text("Sample input")


if __name__ == "__main__":
    unittest.main()

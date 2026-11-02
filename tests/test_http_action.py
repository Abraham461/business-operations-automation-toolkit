import os
import unittest
from unittest.mock import Mock, patch

from modules.workflow_engine.http_action import (
    _json_path, _substitute, _validate_destination, run_http_action,
)


class HttpWorkflowActionTests(unittest.TestCase):
    @patch.dict(os.environ, {"OPSPILOT_HTTP_ALLOWED_HOSTS": "api.example.com"})
    @patch("modules.workflow_engine.http_action.socket.getaddrinfo")
    def test_destination_requires_allowlisted_public_host(self, resolve):
        resolve.return_value = [(None, None, None, None, ("93.184.216.34", 443))]
        self.assertEqual(_validate_destination("https://api.example.com/v1").hostname, "api.example.com")

    @patch.dict(os.environ, {"OPSPILOT_HTTP_ALLOWED_HOSTS": "api.example.com"})
    def test_destination_rejects_unlisted_host(self):
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            _validate_destination("https://other.example.com/data")

    @patch.dict(os.environ, {"OPSPILOT_HTTP_ALLOWED_HOSTS": "api.example.com"})
    @patch("modules.workflow_engine.http_action.socket.getaddrinfo")
    def test_destination_rejects_private_dns_result(self, resolve):
        resolve.return_value = [(None, None, None, None, ("127.0.0.1", 443))]
        with self.assertRaisesRegex(ValueError, "private or reserved"):
            _validate_destination("https://api.example.com")

    def test_variable_substitution_and_json_path(self):
        self.assertEqual(_json_path({"data": {"id": 42}}, "data.id"), 42)
        self.assertEqual(_substitute("/users/{{user_id}}", {"user_id": 42}), "/users/42")
        with self.assertRaisesRegex(ValueError, "has not been defined"):
            _substitute("{{missing}}", {})

    @patch.dict(os.environ, {"OPSPILOT_HTTP_ALLOWED_HOSTS": "api.example.com"})
    @patch("modules.workflow_engine.http_action.socket.getaddrinfo")
    @patch("modules.workflow_engine.http_action.requests.Session")
    def test_http_request_extracts_json_and_disables_environment_proxies(self, session_cls, resolve):
        resolve.return_value = [(None, None, None, None, ("93.184.216.34", 443))]
        response = Mock()
        response.status_code = 200
        response.iter_content.return_value = [b'{"data":{"token":"abc123"}}']
        session = session_cls.return_value
        session.request.return_value = response
        result = run_http_action({
            "method": "GET", "url": "https://api.example.com/token",
            "extract": {"access_token": "data.token"},
        })
        self.assertEqual(result["variables"], {"access_token": "abc123"})
        self.assertEqual(result["response"], {"data": {"token": "abc123"}})
        self.assertFalse(session.trust_env)
        self.assertFalse(session.request.call_args.kwargs["allow_redirects"])
        response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

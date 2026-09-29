import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from src.llm import openrouter_client as client


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(dir=client.PROJECT_ROOT / "tests")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for patcher in (patch.object(client, "PROJECT_ROOT", self.root),
                        patch.dict(os.environ, {}, clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.opener_patch = patch.object(client.urllib.request, "build_opener")
        self.opener = self.opener_patch.start().return_value
        self.addCleanup(self.opener_patch.stop)

    def response(self, data):
        os.environ["OPENROUTER_API_KEY"] = "unit-test-placeholder"
        self.opener.open.return_value.__enter__.return_value.read.return_value = data

    def test_missing_key(self):
        self.assertEqual(client.test_connection()["error"]["code"], "missing_api_key")
        self.opener.open.assert_not_called()

    def test_dotenv_and_environment_priority(self):
        (self.root / ".env").write_text('OPENROUTER_API_KEY="unit-test-placeholder"\n', encoding="utf-8")
        self.assertTrue(client.load_api_key())
        self.assertTrue(client.load_api_key())

    def test_http_error_is_sanitized(self):
        self.response(b"")
        self.opener.open.side_effect = HTTPError(client.ENDPOINT, 429, "unit-test-placeholder", {}, io.BytesIO(b"private"))
        result = client.test_connection()
        self.assertEqual(result["http_status"], 429)
        self.assertNotIn("unit-test-placeholder", json.dumps(result))
        self.opener.open.assert_called_once()

    def test_api_error(self):
        self.response(b'{"error":{"message":"private"}}')
        self.assertEqual(client.test_connection()["error"]["code"], "api_error")

    def test_bad_json(self):
        for body, code in ((b"not json", "response_json_error"), (b'{"choices":[{"message":{"content":"not json"}}]}', "content_json_error")):
            self.response(body)
            self.assertEqual(client.test_connection()["error"]["code"], code)

    def test_strict_schema_no_downgrade(self):
        from src.llm.llm_planner import ACTION_SCHEMA
        self.response(b'{"error":{"code":404,"message":"No endpoints support requested parameters"}}')
        result = client.request_json([], json_schema=ACTION_SCHEMA)
        self.assertEqual(result["status"], "error")
        self.opener.open.assert_called_once()
        payload = json.loads(self.opener.open.call_args.args[0].data)
        self.assertEqual(payload["model"], "openrouter/free")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertTrue(payload["provider"]["require_parameters"])
        self.assertFalse(payload["provider"]["allow_fallbacks"])

    def test_conservative_fence(self):
        self.assertEqual(client.parse_content('```json\n{"x":1}\n```')["result"], {"x": 1})
        for text in ('Here is JSON: {"x":1}', '```json\n{"x":1}\n``` extra', '{"x":1}{"y":2}', '```json\n{"x":1}\n```\n```json\n{}\n```'):
            self.assertEqual(client.parse_content(text)["error"]["code"], "content_json_error")
        self.assertEqual(client.parse_content('[]')["error"]["code"], "action_validation_error")

    def test_safe_content_diagnostics(self):
        self.response(b"")
        text = 'unit-test-placeholder ' + 'x' * 500
        result = client.parse_content(text, 'length')
        self.assertNotIn('unit-test-placeholder', json.dumps(result))
        self.assertLessEqual(len(result['preview']), 300)
        self.assertEqual(result['finish_reason'], 'length')
        self.assertEqual(result['json_line'], 1)
        for text, kind in [('', 'empty'), ('```json\n{\n```', 'markdown_code_fence'), ('Answer: {}', 'natural_language_plus_json'), ('{"x":', 'malformed_json'), ('hello', 'unknown')]:
            self.assertEqual(client.parse_content(text)['format'], kind)

    def test_parse_original_before_redaction(self):
        with patch.object(client, 'redact', side_effect=AssertionError('must not redact before parsing')):
            self.assertEqual(client.parse_content('{"text":"unaltered"}')["result"], {"text": "unaltered"})

    def test_success_fixed_model_and_single_call(self):
        content = {"status": "ok", "message": "connection successful"}
        self.response(json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode())
        result = client.test_connection()
        self.assertEqual(result["status"], "ok")
        self.opener.open.assert_called_once()
        request = self.opener.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "openrouter/free")
        self.assertNotIn("models", payload)
        self.assertFalse(payload["provider"]["allow_fallbacks"])
        self.assertEqual(self.opener.open.call_args.kwargs["timeout"], 45)

    def test_network_error(self):
        self.response(b"")
        self.opener.open.side_effect = URLError("private")
        self.assertEqual(client.test_connection()["error"]["code"], "connection_error")

    def test_redirect_blocked(self):
        self.assertIsNone(client._NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_http_diagnostics(self):
        for status in (401, 429, 500, 503):
            with self.subTest(status=status):
                self.response(b"")
                body = json.dumps({"error": {"code": status, "message": "Provider unavailable",
                      "metadata": {"headers": {"Authorization": "private-header"}}}}).encode()
                self.opener.open.side_effect = HTTPError(client.ENDPOINT, status, "unused", {}, io.BytesIO(body))
                result = client.test_connection()
                self.assertEqual(result["http_status"], status)
                self.assertEqual(result["openrouter_code"], str(status))
                self.assertEqual(result["provider_error"], "Provider unavailable")
                self.assertEqual(result["error_type"], "http_error")
                self.assertNotIn("private-header", json.dumps(result))

    def test_timeout_diagnostics(self):
        for error in (TimeoutError(), URLError(TimeoutError())):
            self.response(b"")
            self.opener.open.side_effect = error
            result = client.test_connection()
            self.assertTrue(result["timeout"])
            self.assertEqual(result["error_type"], "timeout")

    def test_non_json_http_response(self):
        self.response(b"")
        self.opener.open.side_effect = HTTPError(client.ENDPOINT, 502, "unused", {}, io.BytesIO(b"<html>private</html>"))
        result = client.test_connection()
        self.assertTrue(result["json_parse_error"])
        self.assertNotIn("<html>", json.dumps(result))

    def test_structured_error_http_200(self):
        self.response(b'{"error":{"code":503,"message":"No provider available"}}')
        self.opener.open.return_value.__enter__.return_value.status = 200
        result = client.test_connection()
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["openrouter_code"], "503")
        self.assertEqual(result["provider_error"], "No provider available")

    def test_secret_redaction(self):
        self.response(json.dumps({"error": {"message": "failed unit-test-placeholder", "code": "sk-test-secret-token"}}).encode())
        text = json.dumps(client.test_connection())
        self.assertNotIn("unit-test-placeholder", text)
        self.assertNotIn("sk-test-secret-token", text)
        self.assertEqual(client.safe_error_text('Authorization: Bearer arbitrary-value'), '[敏感错误文本已省略]')


if __name__ == "__main__":
    unittest.main()

import json
import ssl
import unittest
from http.client import IncompleteRead
from unittest.mock import patch
import urllib.error

from api_client import (
    RetryableAPIError,
    build_chat_completion_payload,
    call_openai_compatible_chat,
    format_incomplete_read_error,
    parse_chat_completion_response,
)


class ApiClientTests(unittest.TestCase):
    def test_parse_chat_completion_response_reports_reasoning_token_exhaustion(self):
        body = json.dumps({
            "choices": [{
                "finish_reason": "length",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "thinking...",
                },
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 8192,
                "completion_tokens_details": {"reasoning_tokens": 8192},
            },
        }).encode("utf-8")

        with self.assertRaisesRegex(RuntimeError, "reasoning_tokens=8192"):
            parse_chat_completion_response(body)

        with self.assertRaisesRegex(RuntimeError, "max_tokens_per_chunk"):
            parse_chat_completion_response(body)

    def test_parse_chat_completion_response_returns_content_and_usage(self):
        body = json.dumps({
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "  你好  ",
                    "reasoning_content": "thinking...",
                },
            }],
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 5,
                "completion_tokens_details": {"reasoning_tokens": 2},
            },
        }).encode("utf-8")

        content, usage = parse_chat_completion_response(body)

        self.assertEqual(content, "你好")
        self.assertEqual(usage, {"prompt_tokens": 3, "completion_tokens": 5})

    def test_format_incomplete_read_error_mentions_response_body_disconnect(self):
        message = format_incomplete_read_error(IncompleteRead(b"", 128))

        self.assertIn("响应读取中断", message)
        self.assertIn("0 bytes", message)
        self.assertIn("提前关闭连接", message)

    def test_call_formats_ssl_eof_as_retryable_disconnect(self):
        ssl_error = ssl.SSLEOFError(
            ssl.SSL_ERROR_EOF,
            "UNEXPECTED_EOF_WHILE_READING",
        )
        url_error = urllib.error.URLError(ssl_error)

        with patch("api_client.urllib.request.urlopen", side_effect=url_error):
            with self.assertRaisesRegex(RetryableAPIError, "可安全重试"):
                call_openai_compatible_chat(
                    {
                        "api_key": "sk-test",
                        "api_base": "https://api.deepseek.com/v1",
                        "request_timeout": 1,
                    },
                    "system",
                    "user",
                )

    def test_build_payload_disables_deepseek_v4_thinking_by_default(self):
        payload = json.loads(build_chat_completion_payload(
            {
                "api_base": "https://api.deepseek.com/v1",
                "model": "deepseek-v4-flash",
                "temperature": 0.3,
            },
            "system",
            "user",
            8192,
        ))

        self.assertEqual(payload["thinking"], {"type": "disabled"})

    def test_build_payload_does_not_send_thinking_to_custom_endpoint_by_default(self):
        payload = json.loads(build_chat_completion_payload(
            {
                "api_base": "http://localhost:11434/v1",
                "model": "llama3",
                "temperature": 0.3,
            },
            "system",
            "user",
            8192,
        ))

        self.assertNotIn("thinking", payload)


if __name__ == "__main__":
    unittest.main()

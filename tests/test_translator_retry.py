import unittest
from unittest.mock import patch

from translator import _call_with_retry


class TranslatorRetryTests(unittest.TestCase):
    def test_retryable_errors_can_use_network_retry_budget(self):
        calls = []

        def llm_call(system_prompt, user_prompt):
            calls.append((system_prompt, user_prompt))
            if len(calls) < 5:
                exc = RuntimeError("temporary network disconnect")
                exc.retryable = True
                raise exc
            return " translated ", {"prompt_tokens": 1, "completion_tokens": 2}

        with patch("translator.time.sleep"):
            result, usage = _call_with_retry(
                llm_call,
                "system",
                "user",
                "chunk_0004",
                {
                    "max_retries": 3,
                    "network_max_retries": 5,
                    "retry_base_delay": 2,
                    "retry_max_delay": 60,
                },
            )

        self.assertEqual(result, "translated")
        self.assertEqual(usage, {"prompt_tokens": 1, "completion_tokens": 2})
        self.assertEqual(len(calls), 5)

    def test_non_retryable_error_after_network_error_uses_standard_retry_budget(self):
        calls = []

        def llm_call(system_prompt, user_prompt):
            calls.append((system_prompt, user_prompt))
            if len(calls) == 1:
                exc = RuntimeError("temporary network disconnect")
                exc.retryable = True
                raise exc
            raise RuntimeError("bad request")

        with patch("translator.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "2 次重试后"):
                _call_with_retry(
                    llm_call,
                    "system",
                    "user",
                    "chunk_0004",
                    {
                        "max_retries": 2,
                        "network_max_retries": 5,
                        "retry_base_delay": 2,
                        "retry_max_delay": 60,
                    },
                )

        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()

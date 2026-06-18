"""
OpenAI-compatible chat completion client helpers.
"""

import json
from http.client import IncompleteRead
import socket
import ssl
import urllib.error
import urllib.request


class RetryableAPIError(RuntimeError):
    retryable = True


def build_chat_completion_payload(
    cfg: dict,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> bytes:
    """Build the JSON payload for /chat/completions."""
    payload = {
        "model": cfg.get("model", "deepseek-v4-pro"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": cfg.get("temperature", 0.3),
        "max_tokens": max_tokens,
        "stream": False,
    }

    api_base = cfg.get("api_base", "https://api.deepseek.com/v1")
    model = str(payload["model"])
    thinking = cfg.get("thinking")
    if thinking is None and "api.deepseek.com" in api_base and model.startswith("deepseek-v4"):
        thinking = "disabled"

    if thinking:
        payload["thinking"] = thinking if isinstance(thinking, dict) else {"type": str(thinking)}

    if cfg.get("reasoning_effort"):
        payload["reasoning_effort"] = cfg["reasoning_effort"]

    return json.dumps(payload).encode("utf-8")


def parse_chat_completion_response(body: bytes) -> tuple[str, dict]:
    """Parse a chat completion response into content and token usage."""
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"API 返回了无效 JSON: {exc}") from exc

    choices = result.get("choices") or []
    if not choices:
        raise RuntimeError("API 返回为空：没有 choices")

    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = message.get("content") or ""
    usage = result.get("usage") or {}
    usage_summary = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }

    if content.strip():
        return content.strip(), usage_summary

    finish_reason = choice.get("finish_reason")
    completion_details = usage.get("completion_tokens_details") or {}
    reasoning_tokens = completion_details.get("reasoning_tokens")
    reasoning_content = message.get("reasoning_content") or ""

    details = []
    if finish_reason:
        details.append(f"finish_reason={finish_reason}")
    if usage_summary["completion_tokens"]:
        details.append(f"completion_tokens={usage_summary['completion_tokens']}")
    if reasoning_tokens is not None:
        details.append(f"reasoning_tokens={reasoning_tokens}")
    if reasoning_content:
        details.append("reasoning_content 非空但最终 content 为空")

    suffix = f" ({', '.join(details)})" if details else ""
    advice = (
        "。模型可能把输出 token 用在 reasoning 上，未生成最终译文；"
        "请增大 max_tokens_per_chunk、减小 chunk_target_tokens，或换用非 reasoning 模型"
        if finish_reason == "length" or reasoning_tokens
        else ""
    )
    raise RuntimeError(f"LLM returned empty response{suffix}{advice}")


def format_incomplete_read_error(exc: IncompleteRead) -> str:
    partial = exc.partial or b""
    return (
        f"API 响应读取中断: IncompleteRead({len(partial)} bytes read)。"
        "服务端或网络代理提前关闭连接，可安全重试；如果频繁出现，"
        "请提高 request_timeout 或减小 chunk_target_tokens"
    )


def _iter_error_chain(exc: BaseException):
    seen = set()
    current = exc
    while isinstance(current, BaseException) and id(current) not in seen:
        seen.add(id(current))
        yield current

        reason = current.reason if isinstance(current, urllib.error.URLError) else None
        if isinstance(reason, BaseException) and id(reason) not in seen:
            current = reason
            continue

        current = current.__cause__ or current.__context__


def _is_retryable_connection_error(exc: BaseException) -> bool:
    retryable_types = (
        IncompleteRead,
        ssl.SSLEOFError,
        ssl.SSLZeroReturnError,
        ConnectionResetError,
        BrokenPipeError,
        TimeoutError,
        socket.timeout,
    )
    retryable_fragments = (
        "unexpected_eof_while_reading",
        "eof occurred in violation of protocol",
        "connection reset",
        "connection aborted",
        "remote end closed connection",
        "timed out",
    )

    for current in _iter_error_chain(exc):
        if isinstance(current, retryable_types):
            return True

        message = str(current).lower()
        if any(fragment in message for fragment in retryable_fragments):
            return True

    return False


def _format_retryable_connection_error(exc: BaseException) -> str:
    for current in _iter_error_chain(exc):
        if isinstance(current, IncompleteRead):
            return format_incomplete_read_error(current)

    return (
        f"API 连接被提前关闭: {exc}。"
        "服务端或网络代理提前关闭连接，可安全重试；如果频繁出现，"
        "请提高 request_timeout、减小 chunk_target_tokens，或稍后重试"
    )


def call_openai_compatible_chat(
    cfg: dict,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
) -> tuple[str, dict]:
    """Call an OpenAI-compatible /chat/completions endpoint."""
    api_key = cfg.get("api_key") or cfg.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("未设置 DEEPSEEK_API_KEY。请设置环境变量或在 config.json 中配置。")

    api_base = cfg.get("api_base", "https://api.deepseek.com/v1").rstrip("/")
    timeout = cfg.get("request_timeout", 300)

    payload = build_chat_completion_payload(cfg, system_prompt, user_prompt, max_tokens)

    req = urllib.request.Request(
        f"{api_base}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return parse_chat_completion_response(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else str(exc)
        raise RuntimeError(f"API 错误 ({exc.code}): {body[:500]}") from exc
    except IncompleteRead as exc:
        raise RetryableAPIError(format_incomplete_read_error(exc)) from exc
    except RuntimeError:
        raise
    except Exception as exc:
        if _is_retryable_connection_error(exc):
            raise RetryableAPIError(_format_retryable_connection_error(exc)) from exc
        raise RuntimeError(f"API 调用失败: {exc}") from exc

"""
API 客户端 — 统一的 LLM API 调用封装。

支持 DeepSeek 及任何 OpenAI 兼容 API。
内置重试机制（指数退避）。
"""

import json
import time
import urllib.request
import urllib.error
from rich.console import Console

console = Console()


def call_api(
    api_key: str,
    api_base: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    max_retries: int = 3,
    retry_base_delay: float = 2.0,
    retry_max_delay: float = 30.0,
) -> tuple[str, dict]:
    """调用 OpenAI 兼容 API，带重试。

    Args:
        api_key: API 密钥
        api_base: API Base URL（如 https://api.deepseek.com/v1）
        model: 模型名
        system_prompt: 系统提示
        user_prompt: 用户提示
        max_tokens: 最大输出 token 数
        temperature: 温度参数
        max_retries: 最大重试次数
        retry_base_delay: 重试基础延迟（秒）
        retry_max_delay: 重试最大延迟（秒）

    Returns:
        (response_text, usage_dict) — usage_dict 含 prompt_tokens, completion_tokens
    """
    if not api_key:
        raise ValueError("未设置 API Key。请设置环境变量 DEEPSEEK_API_KEY 或在 config.json 中配置。")

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode("utf-8")

    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                return content.strip(), {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                }
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else str(e)
            last_error = RuntimeError(f"API 错误 ({e.code}): {body[:500]}")
        except Exception as e:
            last_error = RuntimeError(f"API 调用失败: {e}")

        if attempt < max_retries - 1:
            delay = min(retry_base_delay * (2 ** attempt), retry_max_delay)
            console.print(f"  [yellow]⚠️ 第{attempt+1}次失败: {last_error}，{delay:.0f}s 后重试[/yellow]")
            time.sleep(delay)

    raise last_error

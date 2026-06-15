"""
API 客户端 — 统一的 LLM API 调用封装。

支持三种 Provider：
  - deepseek: 直连 DeepSeek API（urllib，零额外依赖）
  - litellm:  通过 liteLLM 统一接口调用 100+ 模型（OpenAI / Anthropic / Gemini / Groq / Qwen ...）
  - custom:   任意 OpenAI 兼容 API（Ollama / vLLM / 自定义端点）

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
    provider: str = "deepseek",
) -> tuple[str, dict]:
    """调用 LLM API，带重试。

    Args:
        api_key: API 密钥
        api_base: API Base URL（如 https://api.deepseek.com/v1），liteLLM 模式下可留空
        model: 模型名。liteLLM 模式下使用 "provider/model" 格式
        system_prompt: 系统提示
        user_prompt: 用户提示
        max_tokens: 最大输出 token 数
        temperature: 温度参数
        max_retries: 最大重试次数
        retry_base_delay: 重试基础延迟（秒）
        retry_max_delay: 重试最大延迟（秒）
        provider: 提供商类型 — "deepseek" | "litellm" | "custom"

    Returns:
        (response_text, usage_dict) — usage_dict 含 prompt_tokens, completion_tokens
    """
    if provider == "litellm":
        return _call_via_litellm(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=api_key,
            api_base=api_base,
        )
    else:
        # deepseek / custom: 直连 OpenAI 兼容 API
        return _call_via_http(
            api_key=api_key,
            api_base=api_base,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
            retry_max_delay=retry_max_delay,
        )


def _call_via_http(
    api_key: str,
    api_base: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    max_retries: int,
    retry_base_delay: float,
    retry_max_delay: float,
) -> tuple[str, dict]:
    """直连 OpenAI 兼容 API（urllib 实现，无第三方依赖）。"""
    if not api_key:
        raise ValueError("未设置 API Key。请设置环境变量或配置 api_key。")

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


def _call_via_litellm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    api_key: str = "",
    api_base: str = "",
) -> tuple[str, dict]:
    """通过 liteLLM 调用任意 LLM 提供商。

    liteLLM 支持 100+ 模型，统一接口：
      - openai/gpt-4o
      - anthropic/claude-sonnet-4-20250514
      - gemini/gemini-2.5-pro
      - groq/llama-4-maverick-17b-128e
      - deepseek/deepseek-chat
      - ... 等
    """
    try:
        import litellm
    except ImportError:
        raise ImportError(
            "liteLLM 未安装。运行: uv sync --extra litellm 或 uv add litellm"
        )

    # liteLLM 自动从环境变量读取各 provider 的 API key
    # 如 OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY 等
    # 也可以显式传入 api_key
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    try:
        response = litellm.completion(**kwargs)
        content = response.choices[0].message.content
        usage = response.usage
        return (content.strip() if content else ""), {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
        }
    except Exception as e:
        raise RuntimeError(f"liteLLM 调用失败 [{model}]: {e}")


def get_available_litellm_models() -> list[str]:
    """返回 liteLLM 支持的常用翻译模型列表。"""
    return [
        # OpenAI
        "openai/gpt-5.5",
        "openai/gpt-5.5-mini",
        # Anthropic
        "anthropic/claude-opus-4-8",
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-fable-5",
        # Google
        "gemini/gemini-3.5-pro",
        "gemini/gemini-3.5-flash",
        # DeepSeek
        "deepseek/deepseek-chat",
        "deepseek/deepseek-reasoner",
        # Mimo
        "mimo/mimo-v2.5-pro",
        "mimo/mimo-v2.5-omni",
        # Mistral
        "mistral/mistral-large-latest",
        "mistral/mistral-small-latest",
    ]

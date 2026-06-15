"""
book-translation config — 全局配置管理。
"""

import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()  # src/ → project root

DEFAULT_CONFIG = {
    # === 路径 ===
    "input_dir": str(PROJECT_ROOT / "input"),
    "output_dir": str(PROJECT_ROOT / "output"),  # 翻译成品 — 每本书一个子文件夹
    "reports_dir": str(PROJECT_ROOT / "reports"),  # 报告 (consistency / eval)
    "cache_dir": str(PROJECT_ROOT / "cache"),  # 断点文件
    "vector_store_dir": str(PROJECT_ROOT / "vector_store"),  # ChromaDB

    # === LLM 配置 ===
    "provider": "deepseek",  # deepseek | litellm | custom
    "model": "deepseek-v4-pro",
    # 安全提示: API Key 可通过环境变量 DEEPSEEK_API_KEY 设置，
    # 或写入 config.json（config.json 已被 .gitignore 排除，不会提交到 Git）。
    # 生产环境建议使用环境变量方式。
    "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
    "api_base": "https://api.deepseek.com/v1",
    "temperature": 0.3,
    "max_tokens_per_chunk": 8192,

    # === liteLLM 配置 ===
    # 当 provider='litellm' 时，使用 liteLLM 统一接口调用 100+ 模型。
    # 设置 LITELLM_API_KEY 环境变量或在此配置。
    "litellm_api_key": os.environ.get("LITELLM_API_KEY", ""),
    # liteLLM 模型路由表: provider_prefix → model_id
    # 格式: "openai/gpt-4o", "anthropic/claude-sonnet-4-20250514", "gemini/gemini-2.5-pro"
    "litellm_model": "deepseek/deepseek-chat",

    # === 翻译 ===
    "source_lang": "en",
    "target_lang": "zh",
    "genre": "auto",  # auto | literature | philosophy | natural_science | social_science | technical

    # === 分块 ===
    "chunk_target_tokens": 1500,
    "chunk_max_tokens": 3000,
    "overlap_by_genre": {
        "literature": 4,
        "philosophy": 3,
        "natural_science": 2,
        "social_science": 2,
        "technical": 1,
        "auto": 3,
    },

    # === RAT ===
    "rat_top_k": 5,
    "rat_min_distance": 0.3,

    # === 一致性 ===
    "consistency_check_interval": 20,
    "consistency_alert_threshold": 0.8,

    # === QA ===
    "enable_back_translation": False,
    "enable_llm_judge": False,
    "assembly_strategy": "first_lock",  # first_lock | llm_judge

    # === Reflection 反思工作流 ===
    # 启用后每个 chunk 翻译 → LLM 自审 → 修订。显著提升质量，约 2x token 消耗。
    "enable_reflection": False,
    "reflection_depth": 1,  # 反思轮数（1=审一次改一次，2=审两次改两次）
    "reflection_focus": ["accuracy", "fluency", "terminology", "style"],  # 审查维度

    # === Agentic Pre-read ===
    "enable_agentic_preread": True,
    "preread_sample_ratio": 0.1,  # 采样 10%
    "preread_max_sample_tokens": 30000,

    # === CPU/GPU ===
    "use_gpu": True,

    # === 并行 ===
    "parallel_workers": 4,  # 并行翻译章节数（0=禁用）

    # === 文件限制 ===
    "max_input_file_mb": 100,  # 输入文件最大 MB（超出警告）
    "max_input_file_mb_abort": 500,  # 硬限制，超过拒绝

    # === 定价 ===
    # 定价表: (input_per_1M, output_per_1M)。自定义模型为 None 时不显示费用
    "pricing": {
        # DeepSeek
        "deepseek-v4-pro":   {"input": 0.435, "output": 0.87},
        "deepseek-v4-flash": {"input": 0.14,  "output": 0.28},
        "deepseek/deepseek-chat": {"input": 0.435, "output": 0.87},
        # OpenAI (GPT-5.5 family)
        "openai/gpt-5.5":       {"input": 5.00, "output": 15.00},
        "openai/gpt-5.5-mini":  {"input": 1.50, "output": 6.00},
        # Anthropic
        "anthropic/claude-opus-4-8":     {"input": 5.00, "output": 25.00},
        "anthropic/claude-sonnet-4-6":   {"input": 3.00, "output": 15.00},
        "anthropic/claude-fable-5":      {"input": 10.00, "output": 50.00},
        # Google (Gemini 3.5 family)
        "gemini/gemini-3.5-pro":    {"input": 3.50, "output": 10.50},
        "gemini/gemini-3.5-flash":  {"input": 0.30, "output": 1.50},
        # Mimo (MiMo V2.5)
        "mimo/mimo-v2.5-pro":   {"input": 1.20, "output": 4.80},
        "mimo/mimo-v2.5-omni":  {"input": 0.40, "output": 1.60},
    },

    # === 高级 ===
    "batch_delimiter": "\n\n␞␞␞\n\n",
    "max_retries": 3,
    "retry_base_delay": 2,
    "retry_max_delay": 30,
}


def load_config(custom_path=None):
    """加载配置：默认值 < config.json（如果存在）"""
    cfg = DEFAULT_CONFIG.copy()
    config_path = Path(custom_path) if custom_path else (PROJECT_ROOT / "config.json")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
            cfg.update(user_cfg)
    return cfg


def save_config(cfg, path=None):
    """保存配置到 JSON。"""
    save_path = Path(path) if path else (PROJECT_ROOT / "config.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def calc_cost(model: str, prompt_tokens: int, completion_tokens: int, pricing: dict = None) -> tuple[float | None, str]:
    """计算翻译成本。返回 (美元金额, 显示字符串)。

    自定义模型（无定价）返回 (None, 提示信息)。
    """
    if pricing is None:
        pricing = DEFAULT_CONFIG["pricing"]
    rate = pricing.get(model)
    if rate is None:
        return None, f"{prompt_tokens:,}+{completion_tokens:,} tokens (自定义模型，费用未知)"
    cost = prompt_tokens / 1_000_000 * rate["input"] + completion_tokens / 1_000_000 * rate["output"]
    return cost, f"{prompt_tokens:,}+{completion_tokens:,} tokens · ${cost:.4f} (~¥{cost * 7.2:.2f})"


# 常用模型预设（GUI 下拉列表用）
# provider_label: GUI 下拉显示的平台名
# provider:      实际调用的 provider 类型（deepseek / litellm / custom）
MODEL_PRESETS = [
    # DeepSeek（直连）
    {"provider_label": "DeepSeek", "provider": "deepseek", "model": "deepseek-v4-pro", "label": "V4 Pro"},
    {"provider_label": "DeepSeek", "provider": "deepseek", "model": "deepseek-v4-flash", "label": "V4 Flash"},
    # OpenAI（via liteLLM）
    {"provider_label": "OpenAI", "provider": "litellm", "model": "openai/gpt-5.5", "label": "GPT-5.5"},
    {"provider_label": "OpenAI", "provider": "litellm", "model": "openai/gpt-5.5-mini", "label": "GPT-5.5 Mini"},
    # Anthropic（via liteLLM）
    {"provider_label": "Anthropic", "provider": "litellm", "model": "anthropic/claude-opus-4-8", "label": "Opus 4.8"},
    {"provider_label": "Anthropic", "provider": "litellm", "model": "anthropic/claude-sonnet-4-6", "label": "Sonnet 4.6"},
    {"provider_label": "Anthropic", "provider": "litellm", "model": "anthropic/claude-fable-5", "label": "Fable 5"},
    # Google（via liteLLM）
    {"provider_label": "Google", "provider": "litellm", "model": "gemini/gemini-3.5-pro", "label": "Gemini 3.5 Pro"},
    {"provider_label": "Google", "provider": "litellm", "model": "gemini/gemini-3.5-flash", "label": "Gemini 3.5 Flash"},
    # Mimo（via liteLLM）
    {"provider_label": "Mimo", "provider": "litellm", "model": "mimo/mimo-v2.5-pro", "label": "V2.5 Pro"},
    {"provider_label": "Mimo", "provider": "litellm", "model": "mimo/mimo-v2.5-omni", "label": "V2.5 Omni"},
    # Custom
    {"provider_label": "Custom", "provider": "custom", "model": "", "label": "自定义 API..."},
]

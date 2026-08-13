"""
book-translation config — 全局配置管理。
"""

import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()  # src/ → project root

DEFAULT_CONFIG = {
    # === 路径 ===
    "output_dir": str(PROJECT_ROOT / "output"),  # 翻译成品 — 每本书一个子文件夹
    "reports_dir": str(PROJECT_ROOT / "reports"),  # 报告 (consistency / eval)
    "cache_dir": str(PROJECT_ROOT / "cache"),  # 断点文件
    "vector_store_dir": str(PROJECT_ROOT / "vector_store"),  # ChromaDB

    # === LLM 配置 ===
    "provider": "custom",  # litellm | custom
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

    # === 三档模型策略（Wenyi 风格） ===
    # 按任务重要性分三档：
    #   strong: 翻译/润色 — deepseek-v4-pro（最高质量）
    #   cheap:  审校/一致性QA — deepseek-v4-flash（判断类，开思考）
    #   fast:   预读/术语抽取 — deepseek-v4-flash（机械任务，关思考省钱）
    # 未配置 llm_tiers 时回退到单模型 "model"。
    "use_tiered_models": True,
    "reasoning_effort": "high",
    "custom_prompt": "",
    "llm_tiers": {
        "strong": {
            "model": "deepseek-v4-pro",
            "reasoning_effort": "high",
        },
        "cheap": {
            "model": "deepseek-v4-flash",
            "reasoning_effort": "high",
        },
        "fast": {
            "model": "deepseek-v4-flash",
            "reasoning_effort": "low",
        },
    },

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
    # 术语抽取：从真实译文增量抽取高频术语对（cheap tier），
    # 与 KG 预读 glossary 互补，保证预读关闭时一致性审计仍有数据。
    # 默认关闭：开启后每 N 块额外调用一次 cheap 档模型，需用户显式开启。
    "enable_term_extraction": False,
    "term_extraction_interval": 20,   # 每 N 块抽取一次
    "term_extraction_max_terms": 30,  # 每次最多记录术语数

    # === QA ===
    "assembly_strategy": "body_join",  # body_join | first_lock

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
    "parallel_workers": 0,  # 并行翻译章节数（0=自动：min(章节数,4)）

    # === 文件限制 ===
    "max_input_file_mb": 100,  # 输入文件最大 MB（超出警告）
    "max_input_file_mb_abort": 500,  # 硬限制，超过拒绝

    # === 高级 ===
    "max_retries": 3,
    "retry_base_delay": 2,
    "retry_max_delay": 30,
}


_PATH_KEYS = ("output_dir", "reports_dir", "cache_dir", "vector_store_dir")


def load_config(custom_path=None):
    """加载配置：默认值 < config.json（如果存在）。

    路径类键：空值回退运行时默认（按当前执行环境解析 PROJECT_ROOT，
    避免 config.json 里写死的 Windows UNC 路径在 WSL/Linux 下失效）；
    相对路径相对 PROJECT_ROOT 解析；绝对路径原样使用。
    """
    cfg = DEFAULT_CONFIG.copy()
    config_path = Path(custom_path) if custom_path else (PROJECT_ROOT / "config.json")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
            cfg.update(user_cfg)
    for k in _PATH_KEYS:
        v = cfg.get(k)
        if not v:
            cfg[k] = DEFAULT_CONFIG[k]
        elif not Path(v).is_absolute():
            cfg[k] = str(PROJECT_ROOT / v)
    return cfg


def save_config(cfg, path=None):
    """保存配置到 JSON。"""
    save_path = Path(path) if path else (PROJECT_ROOT / "config.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# 常用模型预设（GUI 下拉列表用）
# provider_label: GUI 下拉显示的平台名
# provider:      实际调用的 provider 类型（deepseek / litellm / custom）
MODEL_PRESETS = [
    # DeepSeek（直连）
    {"provider_label": "DeepSeek", "provider": "custom", "model": "deepseek-v4-pro", "label": "V4 Pro"},
    {"provider_label": "DeepSeek", "provider": "custom", "model": "deepseek-v4-flash", "label": "V4 Flash"},
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
    {"provider_label": "Mimo", "provider": "litellm", "model": "mimo/mimo-v2.5-pro", "label": "MiMo-V2.5-Pro"},
    {"provider_label": "Mimo", "provider": "litellm", "model": "mimo/mimo-v2.5-omni", "label": "MiMo-V2.5-Omni"},
    # Custom
    {"provider_label": "Custom", "provider": "custom", "model": "", "label": "自定义 API..."},
]


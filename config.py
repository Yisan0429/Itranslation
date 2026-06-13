"""
book-translation config — 全局配置管理。
"""

import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

DEFAULT_CONFIG = {
    # === 路径 ===
    "input_dir": str(PROJECT_ROOT / "input"),
    "output_dir": str(PROJECT_ROOT / "output"),  # 翻译成品 — 每本书一个子文件夹
    "reports_dir": str(PROJECT_ROOT / "reports"),  # 报告 (consistency / eval)
    "cache_dir": str(PROJECT_ROOT / "cache"),  # 断点文件
    "vector_store_dir": str(PROJECT_ROOT / "vector_store"),  # ChromaDB

    # === LLM 配置 ===
    "provider": "deepseek",
    "model": "deepseek-v4-pro",
    "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
    "api_base": "https://api.deepseek.com/v1",
    "temperature": 0.3,
    "max_tokens_per_chunk": 8192,

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
        "deepseek-v4-pro":   {"input": 0.435, "output": 0.87},
        "deepseek-v4-flash": {"input": 0.14,  "output": 0.28},
    },

    # === 高级 ===
    "batch_delimiter": "\n\n␞␞␞\n\n",
    "max_retries": 3,
    "retry_base_delay": 2,
    "retry_max_delay": 60,
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

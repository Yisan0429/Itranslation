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
    "output_dir": str(PROJECT_ROOT / "output"),
    "final_dir": str(PROJECT_ROOT / "final"),
    "cache_dir": str(PROJECT_ROOT / "cache"),
    "chunks_dir": str(PROJECT_ROOT / "chunks"),
    "vector_store_dir": str(PROJECT_ROOT / "vector_store"),

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

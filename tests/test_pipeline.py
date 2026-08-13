"""pipeline 层测试：并行章节保序 / 配置优先级（mock 翻译器，不调真实 API）。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline  # noqa: E402
from pipeline import run_translation_pipeline  # noqa: E402


def _fake_translate(completion_delays: dict):
    """构造 translate_chapter 的 mock：每章按 title 延时不同，模拟乱序完成。

    返回的译文严格按「每 chunk 一句（␟ 分隔）」输出，正文句数=chunk 句数。
    """
    def fake(chapter_title, chunks, vector_store, consistency_model, glossary,
             kg, llm_call, config, checkpoint_path=None, cost_lock=None,
             chunk_cb=None, **kwargs):
        if chapter_title in completion_delays:
            time.sleep(completion_delays[chapter_title])
        translations = []
        for ch in chunks:
            n = ch.body_sentence_count
            sents = "␟".join(f"ZH[{chapter_title}]{i}" for i in range(n))
            translations.append(sents)
        return translations, []
    return fake


def _minimal_cfg(tmp_path: Path) -> dict:
    return {
        "genre": "literature",
        "overlap_by_genre": {"literature": 0, "auto": 0},
        "chunk_max_tokens": 3000,
        "chunk_target_tokens": 10000,
        "consistency_alert_threshold": 0.8,
        "assembly_strategy": "body_join",
        "enable_agentic_preread": False,
        "max_input_file_mb": 100,
        "max_input_file_mb_abort": 500,
        "cache_dir": str(tmp_path / "cache"),
        "reports_dir": str(tmp_path / "reports"),
        "vector_store_dir": str(tmp_path / "vs"),
    }


def _write_three_chapter_book(tmp_path: Path) -> Path:
    src = tmp_path / "three_chapters.txt"
    src.write_text(
        "# Chapter One\nOne A one. One B one.\n\n"
        "# Chapter Two\nTwo A two. Two B two.\n\n"
        "# Chapter Three\nThree A three. Three B three.\n",
        encoding="utf-8",
    )
    return src


def test_parallel_chapter_order(monkeypatch, tmp_path):
    """P0-1：多章并行且完成顺序乱序时，输出章节顺序必须与原文一致。"""
    src = _write_three_chapter_book(tmp_path)
    cfg = _minimal_cfg(tmp_path)
    # 第 2 章最快、第 1 章最慢 → as_completed 顺序为 Two, Three, One
    delays = {"Chapter One": 0.25, "Chapter Two": 0.01, "Chapter Three": 0.1}
    monkeypatch.setattr(pipeline, "translate_chapter", _fake_translate(delays))

    out = tmp_path / "out" / "three_chapters.txt"
    params = {
        "book": str(src),
        "config": cfg,
        "no_preread": True,
        "no_rat": True,
        "no_vision": True,
        "format": "txt",
        "output": str(out),
        "parallel": 3,
        "overlap": 0,
        "clear_cache": False,
    }
    result = run_translation_pipeline(
        params, log_fn=lambda m: None, progress_fn=lambda f, m: None,
    )

    assert result["num_errors"] == 0
    assert result["num_chapters"] == 3
    text = out.read_text(encoding="utf-8")
    i1 = text.find("ZH[Chapter One]0")
    i2 = text.find("ZH[Chapter Two]0")
    i3 = text.find("ZH[Chapter Three]0")
    assert -1 not in (i1, i2, i3), f"missing chapter translation in output:\n{text}"
def test_target_tokens_from_config(monkeypatch, tmp_path):
    """P0-4：CLI 未指定 --target-tokens 时，config 的 chunk_target_tokens 必须生效。"""
    monkeypatch.setattr(pipeline, "translate_chapter", _fake_translate({}))
    src = tmp_path / "book.txt"
    # 每章 3 个长句（约 16 tokens/句），小 target 时一句一块
    src.write_text(
        "# One\n" + " ".join(f"One sentence number {i} here." for i in range(3)) + "\n\n"
        "# Two\n" + " ".join(f"Two sentence number {i} here." for i in range(3)) + "\n",
        encoding="utf-8",
    )

    def run_with(chunk_target_tokens, params_target=None):
        cfg = _minimal_cfg(tmp_path)
        cfg["chunk_target_tokens"] = chunk_target_tokens
        params = {
            "book": str(src), "config": cfg, "no_preread": True, "no_rat": True,
            "no_vision": True, "format": "txt",
            "output": str(tmp_path / f"out_{chunk_target_tokens}_{params_target}.txt"),
            "parallel": 1, "overlap": 0, "clear_cache": False,
        }
        if params_target is not None:
            params["target_tokens"] = params_target
        return run_translation_pipeline(
            params, log_fn=lambda m: None, progress_fn=lambda f, m: None,
        )

    big = run_with(10000)
    small = run_with(5)
    override = run_with(5, params_target=10000)

    assert big["num_chunks"] == 2, f"大 target 应每章 1 块, 实际 {big['num_chunks']}"
    assert small["num_chunks"] == 6, f"小 target 应每句 1 块, 实际 {small['num_chunks']}"
    assert override["num_chunks"] == big["num_chunks"], (
        "CLI 显式 target_tokens 应覆盖 config"
    )

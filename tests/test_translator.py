"""translator 句数校验（P2-12）与辅助函数单元测试（mock LLM）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chunker import Chunk
from translator import translate_chapter, _count_output_sentences, _ensure_sentence_count


def _chunk(n_sentences: int, i: int = 0) -> Chunk:
    return Chunk(
        id=f"chunk_{i:04d}",
        text=". ".join(f"Sentence {j} here." for j in range(n_sentences)),
        start_sentence=i,
        end_sentence=i + n_sentences - 1,
        body_start_sentence=i,
        overlap_sentences=0,
        sentences=[f"Sentence {j} here." for j in range(n_sentences)],
    )


def test_count_output_sentences():
    assert _count_output_sentences("甲␟乙␟丙") == 3
    assert _count_output_sentences("甲\n乙") == 2
    assert _count_output_sentences("甲") == 1


def test_retry_once_fixes_count():
    """retry_once：首次句数不符 → 重译一次 → 修复后采用。"""
    chunk = _chunk(2)
    calls = []

    def llm(sp, up, tier=None):
        calls.append(up)
        return "甲␟乙", {"prompt_tokens": 1, "completion_tokens": 1}

    result, usage = _ensure_sentence_count(
        "一句。", chunk, "SYS", "USER", llm,
        {"on_count_mismatch": "retry_once"}, None,
    )
    assert result == "甲␟乙"
    assert usage["completion_tokens"] == 1
    assert len(calls) == 1  # 重试一次
    assert "[RETRY]" in calls[0]


def test_retry_once_still_mismatch_marks():
    """retry_once：重试仍不符 → 加标记。"""
    chunk = _chunk(3)

    def llm(sp, up, tier=None):
        return "一句。", {"prompt_tokens": 1, "completion_tokens": 1}

    result, _ = _ensure_sentence_count(
        "一句。", chunk, "SYS", "USER", llm,
        {"on_count_mismatch": "retry_once"}, None,
    )
    assert result.startswith("【⚠️句数不符 期望3")


def test_mark_mode():
    chunk = _chunk(2)
    result, _ = _ensure_sentence_count(
        "一句。", chunk, "SYS", "USER", None, {"on_count_mismatch": "mark"}, None,
    )
    assert result.startswith("【⚠️句数不符 期望2 实得1】")


def test_warn_mode_keeps_result():
    chunk = _chunk(2)
    result, _ = _ensure_sentence_count(
        "一句。", chunk, "SYS", "USER", None, {"on_count_mismatch": "warn"}, None,
    )
    assert result == "一句。"


def test_long_sentence_skips_check():
    chunk = _chunk(1)
    chunk.long_sentence = True
    result, _ = _ensure_sentence_count(
        "甲\n乙\n丙", chunk, "SYS", "USER", None, {"on_count_mismatch": "retry_once"}, None,
    )
    assert result == "甲\n乙\n丙"  # 长句允许拆多行，不校验不重译


def test_failed_placeholder_skips_check():
    chunk = _chunk(2)
    result, _ = _ensure_sentence_count(
        "[翻译失败: boom]", chunk, "SYS", "USER", None, {"on_count_mismatch": "retry_once"}, None,
    )
    assert result == "[翻译失败: boom]"


def test_translate_chapter_applies_retry_once():
    """集成：translate_chapter 内默认 retry_once 生效。"""
    chunk = _chunk(2)
    calls = []

    def llm(sp, up, tier=None):
        calls.append(1)
        if len(calls) == 1:
            return "一句。", {"prompt_tokens": 1, "completion_tokens": 1}
        return "甲␟乙", {"prompt_tokens": 1, "completion_tokens": 1}

    translations, errors = translate_chapter(
        "T", [chunk], None, None, {}, {}, llm, {"genre": "auto"}, None,
    )
    # consistency_model=None 时 _update_consistency 会崩溃？—— 不会：glossary 为空时跳过
    assert errors == []
    assert translations == ["甲␟乙"]
    assert len(calls) == 2

"""assembler 组装策略单元测试（纯逻辑，无外部依赖）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chunker import Chunk
from assembler import assemble_translations, SENTENCE_SEPARATOR


def _mk_chunk(cid: str, start: int, end: int, overlap: int = 0, body_start: int = None) -> Chunk:
    return Chunk(
        id=cid,
        text="",
        start_sentence=start,
        end_sentence=end,
        body_start_sentence=body_start if body_start is not None else start,
        overlap_sentences=overlap,
    )


def test_body_join_drops_overlap_context_translation():
    """a) body_join：第 2 块译文故意含 2 句重叠上下文译文，输出句序与原文一一对应且无重复。"""
    chunks = [
        _mk_chunk("chunk_0000", 0, 2, overlap=0),   # 正文句 0-2（3 句）
        _mk_chunk("chunk_0001", 3, 5, overlap=2),   # 正文句 3-5（3 句）
    ]
    translations = [
        "甲" + SENTENCE_SEPARATOR + "乙" + SENTENCE_SEPARATOR + "丙",
        "重叠一" + SENTENCE_SEPARATOR + "重叠二" + SENTENCE_SEPARATOR
        + "丁" + SENTENCE_SEPARATOR + "戊" + SENTENCE_SEPARATOR + "己",
    ]
    out = assemble_translations(chunks, translations, strategy="body_join")
    lines = out.split("\n")

    assert lines == ["甲", "乙", "丙", "丁", "戊", "己"], f"实际输出: {lines}"
    # 一一对应：6 个输出句 = 6 个正文句，无重复
    assert len(lines) == len(set(lines)) == 6
    # 重叠上下文译文被丢弃
    assert "重叠一" not in lines and "重叠二" not in lines


def test_first_lock_compat_legacy_chunk():
    """b) first_lock 兼容旧式 Chunk（无 body_start_sentence / body_start 字段）。"""
    class LegacyChunk:
        def __init__(self, start: int, end: int):
            self.start_sentence = start
            self.end_sentence = end

    chunks = [LegacyChunk(0, 2)]
    translations = ["第一句" + SENTENCE_SEPARATOR + "第二句" + SENTENCE_SEPARATOR + "第三句"]
    out = assemble_translations(chunks, translations, strategy="first_lock")
    assert out.split("\n") == ["第一句", "第二句", "第三句"]


def test_first_lock_dedup_across_chunks():
    """first_lock：块间重叠句第一次出现定稿，后续忽略。"""
    chunks = [
        _mk_chunk("chunk_0000", 0, 1, overlap=0),   # 句 0-1
        _mk_chunk("chunk_0001", 1, 2, overlap=1),   # 句 1-2（句 1 重叠）
    ]
    translations = [
        "A1" + SENTENCE_SEPARATOR + "B1",
        "B2" + SENTENCE_SEPARATOR + "C1",
    ]
    out = assemble_translations(chunks, translations, strategy="first_lock")
    assert out.split("\n") == ["A1", "B1", "C1"]


def test_short_translation_still_outputs():
    """c) 译文句数不足：不崩溃，输出已有句子。"""
    chunks = [_mk_chunk("chunk_0000", 0, 2, overlap=0)]  # 期望 3 句
    translations = ["只有一句"]
    out = assemble_translations(chunks, translations, strategy="body_join")
    assert out == "只有一句"


def test_strict_raises_on_missing_sentences():
    """P2-16: strict=True 且句数不足时抛 ValueError。"""
    import pytest

    chunks = [_mk_chunk("chunk_0000", 0, 1)]  # 2 句
    with pytest.raises(ValueError):
        assemble_translations(chunks, ["一句。"], strategy="body_join", strict=True)
    # 非 strict 仅警告
    assert assemble_translations(chunks, ["一句。"], strategy="body_join") == "一句。"


def test_sentence_mismatch_count():
    """P2-16: 错配计数跳过占位符与长句块。"""
    from assembler import sentence_mismatch_count

    chunks = [
        _mk_chunk("chunk_0000", 0, 1),  # 2 句
        _mk_chunk("chunk_0001", 2, 2),  # 1 句，长句
    ]
    chunks[1].long_sentence = True
    trans = ["甲␟乙", "丙\n丁\n戊"]  # 第一块匹配，第二块长句（多行）跳过
    assert sentence_mismatch_count(chunks, trans) == 0
    assert sentence_mismatch_count(chunks, ["甲", "[翻译失败: x]"]) == 1

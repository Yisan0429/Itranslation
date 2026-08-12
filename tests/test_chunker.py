"""chunk_text 分块器单元测试（纯逻辑，无外部依赖）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chunker import chunk_text


def _make_sentences(n: int, words_per_sentence: int = 10) -> list[str]:
    """构造 n 句英文句子（单段落，句号+空格分隔，可控长度）。"""
    return [
        " ".join(f"word{i}_{j}" for j in range(words_per_sentence)) + "."
        for i in range(n)
    ]


def _make_text(n: int, words_per_sentence: int = 10) -> str:
    return " ".join(_make_sentences(n, words_per_sentence))


def test_multi_chunk_overlap_and_body_fields():
    """a) 多块场景：相邻块 overlap 正确、body_start==start、body_sentence_count==end-start+1。"""
    sents = _make_sentences(16, words_per_sentence=10)
    text = " ".join(sents)
    chunks = chunk_text(text, target_tokens=40, max_tokens=200, overlap_sentences=3)

    assert len(chunks) >= 2, f"应切出多块, 实际 {len(chunks)} 块"

    for ch in chunks:
        # 每块 body_start == start_sentence（body 首句即本块首句）
        assert ch.body_start == ch.start_sentence
        assert ch.body_start_sentence == ch.start_sentence
        # body_sentence_count == end - start + 1
        assert ch.body_sentence_count == ch.end_sentence - ch.start_sentence + 1
        # 块内 sentences 数 == overlap + body_sentence_count
        assert len(ch.sentences) == ch.overlap_sentences + ch.body_sentence_count

    # 相邻块重叠句数正确（前块正文不足 overlap 时取全部）
    for i in range(1, len(chunks)):
        prev, cur = chunks[i - 1], chunks[i]
        expected = min(3, prev.body_sentence_count)
        assert cur.overlap_sentences == expected, (
            f"chunk[{i}] overlap={cur.overlap_sentences}, 期望 {expected}"
        )
        # 当前块开头 overlap 句 == 上一块末尾 overlap 句
        assert cur.sentences[:cur.overlap_sentences] == prev.sentences[-cur.overlap_sentences:]


def test_single_chunk_overlap_zero():
    """b) 单块场景：即使指定 overlap=3，单块也不产生重叠。"""
    sents = _make_sentences(12, words_per_sentence=6)
    text = " ".join(sents)
    chunks = chunk_text(text, target_tokens=100000, max_tokens=100000, overlap_sentences=3)

    assert len(chunks) == 1, f"应只有 1 块, 实际 {len(chunks)}"
    assert chunks[0].overlap_sentences == 0


def test_sentence_integrity_after_dedup_join():
    """c) 句子切分完整性：各块 sentences 去掉重叠后拼接 == 原文句序列。"""
    sents = _make_sentences(14, words_per_sentence=10)
    text = " ".join(sents)
    chunks = chunk_text(text, target_tokens=40, max_tokens=200, overlap_sentences=3)

    joined = []
    for ch in chunks:
        body = ch.sentences[ch.overlap_sentences:] if ch.overlap_sentences else ch.sentences
        joined.extend(body)

    assert joined == sents, f"拼接后 {len(joined)} 句 != 原文 {len(sents)} 句"

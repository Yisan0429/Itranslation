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


def test_long_sentence_atomic():
    """P0-3：含分号的超长句必须整体保留为单块（从句切割会造成同句索引重复）。"""
    long_sent = ("Clause " + "x " * 500 + "; clause " + "y " * 500 + ".")
    text = "Short sentence one. " + long_sent + " Short sentence two."

    chunks = chunk_text(text, target_tokens=10, max_tokens=100, overlap_sentences=3)

    long_chunks = [c for c in chunks if c.long_sentence]
    assert len(long_chunks) == 1, f"应有恰好 1 个长句块, 实际 {len(long_chunks)}"
    lc = long_chunks[0]
    # 原子化：整句一个块，句索引唯一且句数=1
    assert lc.start_sentence == lc.end_sentence
    assert lc.body_sentence_count == 1
    assert long_sent in lc.text
    # 其它块的句索引不得与长句块重复
    for c in chunks:
        if c is not lc:
            assert not (lc.start_sentence <= c.end_sentence and c.start_sentence <= lc.end_sentence), \
                "长句索引与其他块重叠"
    # 组装完整性：所有块正文句拼接后与原文句序列一致
    joined = []
    for c in sorted(chunks, key=lambda x: x.start_sentence):
        body = c.sentences[c.overlap_sentences:] if c.overlap_sentences else c.sentences
        joined.extend(body)
    assert long_sent in joined


def test_abbreviation_not_split():
    """P2-11: Mr. / e.g. / U.S. 等缩写不产生句子切分。"""
    from chunker import _split_sentences

    sents = [s for s in _split_sentences("Dr. Smith arrived. Then he left. U.S. policy changed.") if s not in ("§", "¶")]
    assert len(sents) == 3
    assert sents[0] == "Dr. Smith arrived."
    assert sents[2] == "U.S. policy changed."


def test_quote_dialogue_not_split():
    """P2-11: 引号内的句号不切分句子。"""
    from chunker import _split_sentences

    text = '"Hello. World." he said. She nodded.'
    sents = [s for s in _split_sentences(text) if s not in ("§", "¶")]
    assert sents == ['"Hello. World." he said.', "She nodded."]


def test_parse_structure_plain_book_chapters():
    """v1.5.1：Gutenberg 纯文本章节头（无 Markdown #）必须被识别为章节，解锁并行。"""
    from chunker import parse_structure

    text = (
        "CHAPTER I\n"
        "The story begins here.\n"
        "\n"
        "Chapter 2\n"
        "Second chapter text.\n"
        "\n"
        "BOOK TWO\n"
        "Book two text.\n"
        "\n"
        "PART III. The End\n"
        "Part three text.\n"
    )
    chapters = parse_structure(text)
    assert [c["title"] for c in chapters] == ["CHAPTER I", "Chapter 2", "BOOK TWO", "PART III. The End"]
    assert chapters[0]["paragraphs"] == ["The story begins here."]
    assert chapters[2]["paragraphs"] == ["Book two text."]


def test_parse_structure_markdown_still_works():
    from chunker import parse_structure

    text = "# Book\n\n## Chapter One\nSome text.\n\n## Chapter Two\nMore text.\n"
    chapters = parse_structure(text)
    # 无正文的空章（# Book 之后直接跟 ## Chapter One）按原语义被丢弃
    assert [c["title"] for c in chapters] == ["Chapter One", "Chapter Two"]
    assert chapters[0]["paragraphs"] == ["Some text."]


def test_parse_structure_body_text_not_chapter():
    """正文中以 'Chapter ...' 开头的长句不得被误判为章节头。"""
    from chunker import parse_structure

    text = (
        "Chapter after chapter, the days passed slowly and nothing changed at all.\n"
        "More body text here.\n"
    )
    chapters = parse_structure(text)
    assert [c["title"] for c in chapters] == ["Body"]
    assert len(chapters[0]["paragraphs"]) == 2

"""
Phase 1: 语义分块 + 重叠。

句子级分词 → 贪心打包（在安全边界封口）→ 层叠重叠。
"""

import re
from dataclasses import dataclass, field
from rich.console import Console

console = Console()


@dataclass
class Chunk:
    id: str
    text: str
    start_sentence: int
    end_sentence: int
    token_count: int = 0


def chunk_text(
    text: str,
    target_tokens: int = 1500,
    max_tokens: int = 3000,
    overlap_sentences: int = 3,
) -> list[Chunk]:
    """
    语义分块：句子级分词 → 贪心打包 → 重叠。

    Args:
        text: 输入文本
        target_tokens: 每块目标 token 数
        max_tokens: 单块最大 token 数（防止长句溢出）
        overlap_sentences: 相邻块重叠的句子数

    Returns:
        Chunk 列表
    """
    # Step 1: 分词
    sentences = _split_sentences(text)
    if not sentences:
        return []

    console.print(f"[cyan]✂️ 分块: {len(sentences)} 句 → 目标 {target_tokens} tokens/块，重叠 {overlap_sentences} 句[/cyan]")

    # Step 2: 计算每句 token 数
    sent_tokens = [(s, _estimate_tokens(s)) for s in sentences]

    # Step 3: 贪心打包
    raw_chunks = _greedy_pack(sent_tokens, target_tokens, max_tokens)

    # Step 4: 加重叠
    chunks = _add_overlap(raw_chunks, sent_tokens, overlap_sentences)

    console.print(f"[green]✅ 分块完成: {len(chunks)} 块[/green]")
    return chunks


# 列表项检测模式
_LIST_PATTERN = re.compile(r'^(\s*)([-*+]|\d+\.)\s')


def _split_sentences(text: str) -> list[str]:
    """将文本拆分为句子列表，保留段落分隔符。

    列表项会被合并为逻辑组，避免跨块断裂。
    """
    paragraphs = text.split("\n\n")
    all_sentences = []
    list_buffer = []  # 列表项缓冲区

    for para in paragraphs:
        para = para.strip()
        if not para:
            # 先输出缓存的列表项
            if list_buffer:
                all_sentences.append("⟨LIST⟩" + " || ".join(list_buffer))
                list_buffer = []
            all_sentences.append("§")
            continue

        # 检测章节标题
        if para.startswith("#"):
            if list_buffer:
                all_sentences.append("⟨LIST⟩" + " || ".join(list_buffer))
                list_buffer = []
            all_sentences.append("§")
            all_sentences.append(para)
            continue

        # 检测是否为列表项
        if _LIST_PATTERN.match(para):
            list_buffer.append(para)
            continue
        else:
            # 非列表项，先输出缓存的列表项
            if list_buffer:
                all_sentences.append("⟨LIST⟩" + " || ".join(list_buffer))
                list_buffer = []

        # 句子分词：按 .!? 后跟空格或换行
        sents = re.split(r'(?<=[.!?])\s+', para)
        sents = [s.strip() for s in sents if s.strip()]
        all_sentences.extend(sents)
        all_sentences.append("¶")

    # 末尾可能残留的列表项
    if list_buffer:
        all_sentences.append("⟨LIST⟩" + " || ".join(list_buffer))

    return all_sentences


def _estimate_tokens(text: str) -> int:
    """粗略估计 token 数（~1.3 tokens/word for English）。"""
    words = len(text.split())
    return max(1, int(words * 1.3))


def _greedy_pack(
    sent_tokens: list[tuple[str, int]],
    target: int,
    max_single: int,
) -> list[list[int]]:
    """
    贪心打包：返回句子索引分组。

    在 § / ¶ / 句尾安全边界封口。
    """
    chunks = []
    current = []
    curr_tokens = 0
    chunk_id = 0

    for i, (text, tokens) in enumerate(sent_tokens):
        # 小节标记 → 强制封口
        if text == "§":
            if current:
                chunks.append(current)
                current = []
                curr_tokens = 0
            continue

        # 段落标记 → 倾向于封口
        if text == "¶":
            if curr_tokens > target * 0.7:
                chunks.append(current)
                current = []
                curr_tokens = 0
            continue

        # 单句就爆 max → 检查是否含占位符，若是则允许超出
        if tokens > max_single:
            if current:
                chunks.append(current)
                current = []
                curr_tokens = 0
            # 含占位符的句子（代码块/公式等）不切割，整体保留
            if "⟨" in text and "⟩" in text:
                current.append(i)
                curr_tokens = tokens
                continue
            # 普通超长句 → 从句切割
            sub_chunks = _split_long_sentence(i, text, max_single)
            chunks.extend(sub_chunks)
            continue

        # 正常情况：贪心装入
        if curr_tokens + tokens > target and current:
            # 当前篮子满了 → 封口
            chunks.append(current)
            current = []
            curr_tokens = 0

        current.append(i)
        curr_tokens += tokens

    # 剩余封口
    if current:
        chunks.append(current)

    return chunks


def _split_long_sentence(sent_idx: int, text: str, max_tokens: int) -> list[list[int]]:
    """极端长句：在从句边界（分号/冒号/破折号）处切割。"""
    clauses = re.split(r'(?<=[;:—])\s+', text)

    if len(clauses) <= 1:
        # 无法从句切割，强制按长度切
        words = text.split()
        mid = len(words) // 2
        return [[sent_idx]]  # 简化：直接放入，标记为长句

    result = []
    for clause in clauses:
        result.append([sent_idx])  # 每个从句都标同一个句子索引

    return result


def _add_overlap(
    raw_chunks: list[list[int]],
    sent_tokens: list[tuple[str, int]],
    overlap: int,
) -> list[Chunk]:
    """
    为每个块添加上下文重叠。

    chunk N 包含的句子：
        实际翻译部分：句 a ~ 句 b
        也同时出现在 chunk N-1 的末尾（overlap 句）
    """
    if overlap <= 0:
        # 无重叠：直接装箱
        result = []
        for chunk_id, indices in enumerate(raw_chunks):
            text = " ".join(sent_tokens[i][0] for i in indices)
            tokens = sum(sent_tokens[i][1] for i in indices)
            result.append(Chunk(
                id=f"chunk_{chunk_id:04d}",
                text=text,
                start_sentence=indices[0],
                end_sentence=indices[-1],
                token_count=tokens,
            ))
        return result

    # 有重叠：每个块在开头包含前 overlap 句的原文
    result = []
    for chunk_id, indices in enumerate(raw_chunks):
        # 扩展索引：向前取 overlap 句
        extended = list(indices)
        if chunk_id > 0:
            prev_indices = raw_chunks[chunk_id - 1]
            overlap_indices = prev_indices[-overlap:] if len(prev_indices) >= overlap else prev_indices[:]
            # 前置重叠句
            extended = overlap_indices + indices

        text = " ".join(sent_tokens[i][0] for i in extended)
        tokens = sum(sent_tokens[i][1] for i in extended)

        result.append(Chunk(
            id=f"chunk_{chunk_id:04d}",
            text=text,
            start_sentence=indices[0],
            end_sentence=indices[-1],
            token_count=tokens,
        ))

    return result


def parse_structure(markdown_text: str) -> list[dict]:
    """
    从 Markdown 中恢复章节结构。

    Returns:
        [{"title": "Chapter 1", "paragraphs": [...]}, ...]
    """
    lines = markdown_text.split("\n")
    chapters = []
    current_chapter = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("## ") or stripped.startswith("# "):
            # 新章节
            if current_chapter and current_chapter.get("paragraphs"):
                chapters.append(current_chapter)
            current_chapter = {"title": stripped.lstrip("# ").strip(), "paragraphs": []}
        elif current_chapter is not None:
            current_chapter["paragraphs"].append(stripped)
        else:
            # 没有章节标题的内容 → 放入默认章
            if not current_chapter:
                current_chapter = {"title": "正文", "paragraphs": []}
            current_chapter["paragraphs"].append(stripped)

    if current_chapter and current_chapter.get("paragraphs"):
        chapters.append(current_chapter)

    return chapters

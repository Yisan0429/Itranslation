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
    body_start_sentence: int | None = None
    overlap_sentences: int = 0
    long_sentence: bool = False
    sentences: list[str] = field(default_factory=list)

    @property
    def body_start(self) -> int:
        """正文第一句在章内句序列中的索引（兼容旧构造：未传时回退 start_sentence）。"""
        return self.start_sentence if self.body_start_sentence is None else self.body_start_sentence

    @property
    def body_sentence_count(self) -> int:
        """本块正文（需翻译输出）的句数。"""
        return self.end_sentence - self.body_start + 1

    def context_text(self) -> str:
        """chunk.text 中仅供上下文理解的重叠句文本（前 N 句）。"""
        n = self.overlap_sentences
        if n > 0 and self.sentences:
            return " ".join(self.sentences[:n])
        return ""

    def body_text(self) -> str:
        """chunk.text 中的正文文本（去掉重叠上下文句）。"""
        n = self.overlap_sentences
        if n > 0 and self.sentences:
            return " ".join(self.sentences[n:])
        return self.text


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

    console.print(f"[cyan]Chunking: {len(sentences)} sentences -> target {target_tokens} tokens/chunk, overlap {overlap_sentences}[/cyan]")

    # Step 2: 计算每句 token 数
    sent_tokens = [(s, _estimate_tokens(s)) for s in sentences]

    # 超长句（非占位符句）整体保留，标记 long_sentence 供翻译提示与组装使用
    long_indices = {
        i for i, (s, t) in enumerate(sent_tokens)
        if t > max_tokens and not ("⟨" in s and "⟩" in s)
    }

    # Step 3: 贪心打包
    raw_chunks = _greedy_pack(sent_tokens, target_tokens, max_tokens)

    # Step 4: 加重叠
    chunks = _add_overlap(raw_chunks, sent_tokens, overlap_sentences, long_indices)

    console.print(f"[green]Chunking done: {len(chunks)} chunks[/green]")
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

        # 句子分词：引号感知（引号内的 .!? 不切）+ 缩写合并
        sents = _split_para_into_sentences(para)
        all_sentences.extend(sents)
        all_sentences.append("¶")

    # 末尾可能残留的列表项
    if list_buffer:
        all_sentences.append("⟨LIST⟩" + " || ".join(list_buffer))

    return all_sentences


# 常见缩写（句尾点不表示句子结束）
_ABBREV_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|St|vs|etc|e\.g|i\.e|U\.S|U\.K|No|Vol|ch|fig|ed|"
    r"approx|dept|Inc|Ltd|Co|Jr|Sr)\.$",
    re.IGNORECASE,
)


def _split_para_into_sentences(para: str) -> list[str]:
    """把段落切为句子。

    - 引号感知：双引号内的 .!? 不切（对话如 "Hello. World." he said. 只切 1 次）
    - 缩写合并：以 Mr. / e.g. / etc. 等结尾的片段与后续片段合并
    """
    sents, last = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+", para):
        prefix = para[:m.start()]
        if prefix.count('"') % 2 == 0:  # 引号外的句末标点才切
            sents.append(para[last:m.start()].strip())
            last = m.end()
    tail = para[last:].strip()
    if tail:
        sents.append(tail)

    merged = []
    for s in sents:
        if merged and _ABBREV_RE.search(merged[-1]):
            merged[-1] = merged[-1] + " " + s
        else:
            merged.append(s)
    return merged


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
            # 普通超长句 → 整体保留（原子化）。
            # 从句切割会让多个从句共用同一句索引：first_lock 下互相覆盖丢句，
            # body_join 下句数对齐错位。现代模型上下文足以容纳单句，不切。
            chunks.append([i])
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


def _add_overlap(
    raw_chunks: list[list[int]],
    sent_tokens: list[tuple[str, int]],
    overlap: int,
    long_indices: set = None,
) -> list[Chunk]:
    """
    为每个块添加上下文重叠。

    chunk N 包含的句子：
        实际翻译部分：句 a ~ 句 b
        也同时出现在 chunk N-1 的末尾（overlap 句）
    """
    long_indices = long_indices or set()
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
                body_start_sentence=indices[0],
                overlap_sentences=0,
                long_sentence=any(i in long_indices for i in indices),
                sentences=[sent_tokens[i][0] for i in indices],
            ))
        return result

    # 有重叠：每个块在开头包含前 overlap 句的原文
    result = []
    for chunk_id, indices in enumerate(raw_chunks):
        # 扩展索引：向前取 overlap 句
        extended = list(indices)
        overlap_count = 0
        if chunk_id > 0:
            prev_indices = raw_chunks[chunk_id - 1]
            overlap_indices = prev_indices[-overlap:] if len(prev_indices) >= overlap else prev_indices[:]
            # 前置重叠句（仅供上下文理解，不参与正文翻译输出）
            extended = overlap_indices + indices
            overlap_count = len(overlap_indices)

        text = " ".join(sent_tokens[i][0] for i in extended)
        tokens = sum(sent_tokens[i][1] for i in extended)

        result.append(Chunk(
            id=f"chunk_{chunk_id:04d}",
            text=text,
            start_sentence=indices[0],
            end_sentence=indices[-1],
            token_count=tokens,
            body_start_sentence=indices[0],
            overlap_sentences=overlap_count,
            long_sentence=any(i in long_indices for i in indices),
            sentences=[sent_tokens[i][0] for i in extended],
        ))

    return result


# 普通书章节头识别（Gutenberg 纯文本格式，无 Markdown 标题）：
#   CHAPTER I / Chapter 1 / CHAPTER XII. / BOOK ONE / PART II / Section 3 ...
# 只匹配短行（章节标题行很短），避免误伤正文中以 "Chapter ..." 开头的句子。
_CHAPTER_NUM = r"(?:[IVXLCDM]+|\d+|[Oo]ne|[Tt]wo|[Tt]hree|[Ff]our|[Ff]ive|[Ss]ix|[Ss]even|[Ee]ight|[Nn]ine|[Tt]en|[Ee]leven|[Tt]welve)"
_PLAIN_CHAPTER_RE = re.compile(
    rf"^(?:(?:chapter|chap|ch)\.?\s+{_CHAPTER_NUM}"
    rf"|(?:book|part|section|sec)\.?\s+{_CHAPTER_NUM})"
    rf"\b(?:\s*[.:\-—]\s*.*)?$",
    re.IGNORECASE,
)


def _plain_chapter_title(line: str) -> str | None:
    """识别普通书章节头（非 Markdown），返回标题或 None。"""
    if len(line) > 60:  # 章节标题是短行
        return None
    if _PLAIN_CHAPTER_RE.match(line):
        return line.strip().rstrip(".").strip()
    return None


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

        title = _plain_chapter_title(stripped)
        if stripped.startswith("## ") or stripped.startswith("# "):
            title = stripped.lstrip("# ").strip()
        if title:
            # 新章节
            if current_chapter and current_chapter.get("paragraphs"):
                chapters.append(current_chapter)
            current_chapter = {"title": title, "paragraphs": []}
        elif current_chapter is not None:
            current_chapter["paragraphs"].append(stripped)
        else:
            # 没有章节标题的内容 → 放入默认章
            if not current_chapter:
                current_chapter = {"title": "Body", "paragraphs": []}
            current_chapter["paragraphs"].append(stripped)

    if current_chapter and current_chapter.get("paragraphs"):
        chapters.append(current_chapter)

    return chapters

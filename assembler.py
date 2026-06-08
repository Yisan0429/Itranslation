"""
Phase 4: 去重叠组装。

策略：翻译时 LLM 按句子输出（␟ 分隔），组装按句子索引去重。
"""

import re
from pathlib import Path
from rich.console import Console

console = Console()

# LLM 输出的句子分隔符
SENTENCE_SEPARATOR = "␟"

# 翻译 prompt 中的句子分隔指令
SENTENCE_INSTRUCTION = (
    f"Output each translated sentence on its own line, "
    f"separated by the character '{SENTENCE_SEPARATOR}'. "
    f"Do not merge sentences. Preserve sentence count exactly."
)


def assemble_translations(
    chunks: list,
    translations: list[str],
    strategy: str = "first_lock",
) -> str:
    """
    将分块译文组装为完整译文，处理重叠句。

    Args:
        chunks: Chunk 对象列表
        translations: 对应的译文列表（与 chunks 同序，每个译文用 ␟ 分隔句子）
        strategy: "first_lock" — 第一次出现就锁定

    Returns:
        完整译文文本
    """
    if not chunks or not translations:
        return ""

    assert len(chunks) == len(translations), \
        f"chunks ({len(chunks)}) and translations ({len(translations)}) must match"

    return _assemble_first_lock(chunks, translations)


def _assemble_first_lock(chunks: list, translations: list[str]) -> str:
    """
    策略 C: 每句话在第一次出现时定稿，后续忽略。

    算法：
    1. 每个 chunk 的译文按 ␟ 切分为句子列表
    2. 句子索引 = chunk.start_sentence + offset
    3. 只有在 first_seen 中不存在的句子才加入
    """
    first_seen = {}   # sentence_index → translated line
    chunk_sent_map = []  # [(chunk, [translated_sentences]), ...]

    for chunk, trans in zip(chunks, translations):
        # 按 ␟ 切分译文
        sentences = _split_by_separator(trans)
        chunk_sent_map.append((chunk, sentences))

    # 按 chunk 顺序处理（保证"第一次出现"的语义）
    for chunk, sentences in chunk_sent_map:
        for offset, zh_sentence in enumerate(sentences):
            sent_idx = chunk.start_sentence + offset
            if sent_idx not in first_seen:
                first_seen[sent_idx] = zh_sentence

    # 按句子索引排序输出
    result = []
    for idx in sorted(first_seen.keys()):
        result.append(first_seen[idx])

    return "\n".join(result)


def _split_by_separator(text: str) -> list[str]:
    """按 ␟ 切分译文句子。"""
    # 先去除首尾空白
    text = text.strip()

    # 按分隔符切分
    parts = text.split(SENTENCE_SEPARATOR)
    parts = [p.strip() for p in parts if p.strip()]

    # 如果切不出来（LLM 没按指令用分隔符），回退到按行切
    if len(parts) <= 1:
        parts = [line.strip() for line in text.split("\n") if line.strip()]

    return parts


def assemble_book(
    chapter_translations: list[tuple[str, str]],
    output_path: str,
    bilingual: bool = False,
    fmt: str = "txt",
):
    """
    将各章译文写入最终文件。

    Args:
        chapter_translations: [(章节标题, 完整译文), ...]
        output_path: 输出路径
        bilingual: True = 双语，False = 纯中文
        fmt: "txt" | "md" | "pdf"
    """
    ext_map = {"txt": ".txt", "md": ".md", "pdf": ".pdf"}
    path = Path(output_path)
    path = path.with_suffix(ext_map.get(fmt, ".txt"))

    if fmt == "pdf":
        _write_pdf(chapter_translations, str(path))
    elif fmt == "md":
        _write_markdown(chapter_translations, str(path), bilingual)
    else:
        _write_txt(chapter_translations, str(path), bilingual)

    console.print(f"[green]✅ 最终译文已保存到 {path}[/green]")


def _write_txt(chapters, path, bilingual):
    with open(path, "w", encoding="utf-8") as f:
        for title, text in chapters:
            f.write(f"\n\n## {title}\n\n")
            f.write(text)
            f.write("\n\n")


def _write_markdown(chapters, path, bilingual):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {Path(path).stem}\n\n")
        for title, text in chapters:
            f.write(f"## {title}\n\n")
            for para in text.split("\n"):
                para = para.strip()
                if para:
                    f.write(f"{para}\n\n")
            f.write("\n")


def _write_pdf(chapters, path):
    try:
        from fpdf import FPDF
    except ImportError:
        console.print("[yellow]⚠️ fpdf2 未安装，回退到 TXT[/yellow]")
        _write_txt(chapters, path.replace(".pdf", ".txt"), False)
        return

    pdf = FPDF()
    # 注册中文字体
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    font_ok = False
    for fp in font_paths:
        if Path(fp).exists():
            try:
                pdf.add_font("zh", "", fp, uni=True)
                pdf.add_font("zh", "B", fp, uni=True)
                font_ok = True
                break
            except Exception:
                continue

    pdf.set_auto_page_break(auto=True, margin=15)
    for title, text in chapters:
        pdf.add_page()
        if font_ok:
            pdf.set_font("zh", "B", 16)
        else:
            pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, title, ln=True, align="C")
        pdf.ln(6)

        if font_ok:
            pdf.set_font("zh", "", 11)
        else:
            pdf.set_font("Helvetica", "", 10)
        for para in text.split("\n"):
            para = para.strip()
            if para:
                pdf.multi_cell(0, 7, para)
                pdf.ln(2)

    pdf.output(path)
    console.print(f"[green]✅ PDF 已保存到 {path} ({font_ok and '中文' or '英文'}字体)[/green]")

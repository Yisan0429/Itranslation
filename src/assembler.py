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
        sentences = _split_by_separator(trans, expected_count=chunk.end_sentence - chunk.start_sentence + 1)
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


def _split_by_separator(text: str, expected_count: int = None) -> list[str]:
    """按 ␟ 切分译文句子。

    Args:
        text: LLM 输出的译文
        expected_count: 期望的句子数（用于验证）

    Returns:
        句子列表
    """
    text = text.strip()

    # 按分隔符切分
    parts = text.split(SENTENCE_SEPARATOR)
    parts = [p.strip() for p in parts if p.strip()]

    # 如果切不出来（LLM 没按指令用分隔符），回退到按行切
    if len(parts) <= 1:
        parts = [line.strip() for line in text.split("\n") if line.strip()]

    # 验证：如果期望句子数和实际差距过大，记录警告
    if expected_count and len(parts) != expected_count:
        console.print(
            f"  [yellow]⚠️ 句子数不匹配: 期望 {expected_count}, 实际 {len(parts)}"
            f" — LLM 可能未遵循 ␟ 分隔指令[/yellow]"
        )

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
    ext_map = {"txt": ".txt", "md": ".md", "pdf": ".pdf", "epub": ".epub"}
    path = Path(output_path)
    path = path.with_suffix(ext_map.get(fmt, ".txt"))

    if fmt == "pdf":
        _write_pdf(chapter_translations, str(path))
    elif fmt == "md":
        _write_markdown(chapter_translations, str(path), bilingual)
    elif fmt == "epub":
        _write_epub(chapter_translations, str(path))
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


def _write_epub(chapters, path):
    """输出 EPUB 电子书。"""
    try:
        from ebooklib import epub
    except ImportError:
        console.print("[yellow]⚠️ ebooklib 未安装，回退到 TXT[/yellow]")
        _write_txt(chapters, path.replace(".epub", ".txt"), False)
        return

    book = epub.EpubBook()
    book.set_identifier("itranslation")
    book.set_title(Path(path).stem)
    book.set_language("zh")
    book.add_author("Itranslation")

    spine = ["nav"]
    toc = []

    for i, (title, text) in enumerate(chapters):
        # 每章一个 xhtml
        ch = epub.EpubHtml(
            title=title,
            file_name=f"chapter_{i:03d}.xhtml",
            lang="zh",
        )
        content = f"<h1>{title}</h1>"
        for para in text.split("\n"):
            para = para.strip()
            if para:
                content += f"<p>{para}</p>"
        ch.content = content
        book.add_item(ch)
        spine.append(ch)
        toc.append(epub.Link(f"chapter_{i:03d}.xhtml", title, f"ch{i}"))

    book.toc = tuple(toc)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(path, book)
    console.print(f"[green]✅ EPUB 已保存到 {path}[/green]")


def _find_cjk_font() -> tuple[str, str] | None:
    """跨平台查找可用的 CJK 字体。返回 (family_name, file_path)。"""
    import platform
    system = platform.system()

    candidates = []
    if system == "Windows":
        candidates = [
            ("Microsoft YaHei", "C:/Windows/Fonts/msyh.ttc"),
            ("Microsoft YaHei", "C:/Windows/Fonts/msyhbd.ttc"),
            ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
            ("SimSun", "C:/Windows/Fonts/simsun.ttc"),
            ("KaiTi", "C:/Windows/Fonts/simkai.ttf"),
        ]
    elif system == "Darwin":  # macOS
        candidates = [
            ("PingFang SC", "/System/Library/Fonts/PingFang.ttc"),
            ("Heiti SC", "/System/Library/Fonts/STHeiti Light.ttc"),
            ("Heiti SC", "/System/Library/Fonts/STHeiti Medium.ttc"),
            ("Songti SC", "/System/Library/Fonts/STSong.ttc"),
            ("Hiragino Sans GB", "/System/Library/Fonts/Hiragino Sans GB.ttc"),
            ("Hiragino Sans GB", "/Library/Fonts/Hiragino Sans GB.ttc"),
        ]
    else:  # Linux
        candidates = [
            ("Noto Sans CJK SC", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            ("Noto Sans CJK SC", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
            ("Noto Sans SC", "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf"),
            ("WenQuanYi Micro Hei", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
            ("WenQuanYi Zen Hei", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            ("Droid Sans Fallback", "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
            ("SimSun", "/usr/share/fonts/truetype/winfonts/simsun.ttc"),
        ]

    for name, path in candidates:
        if Path(path).exists():
            return name, path

    return None


def _write_pdf(chapters, path):
    try:
        from fpdf import FPDF
    except ImportError:
        console.print("[yellow]⚠️ fpdf2 未安装，回退到 TXT[/yellow]")
        _write_txt(chapters, path.replace(".pdf", ".txt"), False)
        return

    pdf = FPDF()
    font_ok = False
    font_family = "Helvetica"

    cjk = _find_cjk_font()
    if cjk:
        name, fp = cjk
        try:
            pdf.add_font("zh", "", fp, uni=True)
            pdf.add_font("zh", "B", fp, uni=True)
            font_ok = True
            font_family = name
            console.print(f"[cyan]📄 PDF 使用字体: {font_family} ({fp})[/cyan]")
        except Exception:
            pass

    if not font_ok:
        console.print("[yellow]⚠️ 未找到 CJK 中文字体，PDF 可能无法正确显示中文[/yellow]")

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

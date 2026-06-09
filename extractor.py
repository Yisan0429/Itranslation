"""
Phase 0: PDF 提取器。

优先使用 marker（视觉提取），fallback 到 PyMuPDF（文本层提取）。
输出：干净的 Markdown 文本。
"""

import os
from pathlib import Path
from rich.console import Console

console = Console()


def extract_pdf(pdf_path: str, use_vision: bool = True) -> str:
    """
    提取 PDF 为 Markdown。

    Args:
        pdf_path: PDF 文件路径
        use_vision: True = 用 marker（视觉提取），False = 用 fitz（文本层提取）

    Returns:
        提取后的 Markdown 文本
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if use_vision:
        return _extract_with_marker(pdf_path)
    else:
        return _extract_with_fitz(pdf_path)


def _extract_with_marker(pdf_path: Path) -> str:
    """用 marker 视觉提取 PDF → Markdown。模型缓存在 D 盘。"""
    import os
    cache_dir = Path(__file__).parent / "models"
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HOME", str(cache_dir / "huggingface"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_dir / "huggingface" / "hub"))
    os.environ.setdefault("TORCH_HOME", str(cache_dir / "torch"))

    try:
        from marker.models import create_model_dict
        from marker.converters.pdf import PdfConverter

        # marker 用 datalab 管理模型缓存，需单独指定路径
        os.environ.setdefault("DATALAB_DIR", str(cache_dir / "datalab"))

        console.print("[bold cyan]📄 marker 视觉提取 PDF（加载模型...）[/bold cyan]")
        artifacts = create_model_dict()
        converter = PdfConverter(artifact_dict=artifacts)
        rendered = converter(str(pdf_path))
        console.print("[green]✅ marker 提取完成[/green]")
        return rendered

    except ImportError:
        raise
    except Exception as e:
        msg = str(e)[:200]
        console.print(f"[red]❌ marker 失败: {msg}[/red]")
        console.print("[yellow]→ 回退到 PyMuPDF 文本提取[/yellow]")
        return _extract_with_fitz(pdf_path)


def _extract_with_fitz(pdf_path: Path, use_markdown: bool = True) -> str:
    """用 PyMuPDF 提取 PDF 文本。"""
    try:
        if use_markdown:
            try:
                import pymupdf4llm
                console.print("[cyan]📄 使用 PyMuPDF4LLM 提取（Markdown 模式）[/cyan]")
                md = pymupdf4llm.to_markdown(str(pdf_path))
                console.print("[green]✅ PyMuPDF4LLM 提取完成[/green]")
                return md
            except ImportError:
                pass

        import fitz
        console.print("[cyan]📄 使用 PyMuPDF 逐页提取（文本模式）[/cyan]")

        doc = fitz.open(str(pdf_path))
        all_lines = []
        page_count = len(doc)

        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text:
                all_lines.extend(text.splitlines())

        doc.close()

        # 重新连接被 PDF 断开的段落
        text = _join_broken_lines(all_lines)
        console.print(f"[green]✅ PyMuPDF 提取完成 ({page_count} 页)[/green]")
        return text

    except ImportError:
        raise ImportError("需要安装 pymupdf: uv add pymupdf")


def _join_broken_lines(lines: list) -> str:
    """
    将 PDF 中因换行被断开的段落重新连接。
    """
    paragraphs = []
    buffer = []

    for line in lines:
        stripped = line.strip()
        if stripped:
            # 检测页码（纯数字行）
            if not stripped.isdigit():
                buffer.append(stripped)
        else:
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
            paragraphs.append("")  # 保留空行作为段落分隔

    if buffer:
        paragraphs.append(" ".join(buffer))

    return "\n".join(paragraphs)


def extract_epub(epub_path: str) -> str:
    """提取 EPUB 为章节文本列表。"""
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup

        console.print("[cyan]📖 解析 EPUB...[/cyan]")
        book = epub.read_epub(epub_path)
        chapters = []

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            # 提取纯文本，保留段落结构
            paragraphs = []
            for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6"]):
                text = tag.get_text(strip=True)
                if text:
                    if tag.name.startswith("h"):
                        paragraphs.append(f"\n## {text}\n")
                    else:
                        paragraphs.append(text)
            if paragraphs:
                chapters.append("\n\n".join(paragraphs))

        console.print(f"[green]✅ EPUB 提取完成 ({len(chapters)} 章)[/green]")
        return "\n\n".join(chapters)

    except ImportError:
        raise ImportError("需要安装 ebooklib + beautifulsoup4: uv add ebooklib beautifulsoup4")


def extract_text(txt_path: str) -> str:
    """读取纯文本文件。"""
    console.print("[cyan]📝 读取文本文件...[/cyan]")
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()
    console.print(f"[green]✅ 文本读取完成 ({len(text)} 字符)[/green]")
    return text


def extract_book(book_path: str, use_vision: bool = True) -> str:
    """自动检测文件类型并提取。"""
    path = Path(book_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_pdf(book_path, use_vision=use_vision)
    elif suffix == ".epub":
        return extract_epub(book_path)
    elif suffix in (".txt", ".md", ".markdown"):
        return extract_text(book_path)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")

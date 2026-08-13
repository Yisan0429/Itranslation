"""extractor 提取器测试：程序化生成最小 PDF/EPUB fixture，验证文本提取。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extractor import extract_book, extract_epub, extract_pdf  # noqa: E402

MARKER = "entropy-of-translation"


def test_extract_pdf_text_layer(tmp_path):
    """用 pymupdf 生成 1 页 PDF → 文本层提取包含关键词。"""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), f"The {MARKER} systems increase steadily.")
    pdf_path = tmp_path / "tiny.pdf"
    doc.save(str(pdf_path))
    doc.close()

    text = extract_pdf(str(pdf_path), use_vision=False)
    assert MARKER in text


def test_extract_epub_paragraphs(tmp_path):
    """用 ebooklib 生成最小 EPUB → 提取包含章节标题与正文。"""
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("itranslation-test")
    book.set_title("Tiny Book")
    book.set_language("en")
    ch = epub.EpubHtml(title="Chapter One", file_name="c1.xhtml", lang="en")
    ch.content = (
        "<html><body><h1>Chapter One</h1>"
        f"<p>Hello {MARKER} world.</p></body></html>"
    )
    book.add_item(ch)
    book.toc = (epub.Link("c1.xhtml", "Chapter One", "c1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch]
    epub_path = tmp_path / "tiny.epub"
    epub.write_epub(str(epub_path), book)

    text = extract_epub(str(epub_path))
    assert "Chapter One" in text
    assert MARKER in text


def test_extract_book_dispatch_txt(tmp_path):
    """extract_book 对 txt 的编码检测与内容返回。"""
    p = tmp_path / "book.txt"
    p.write_text(f"First line with {MARKER}.\nSecond line.", encoding="utf-8")
    text = extract_book(str(p), use_vision=False)
    assert MARKER in text

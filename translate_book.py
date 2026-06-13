#!/usr/bin/env python3
"""
book-translation CLI — 端到端书籍翻译。

用法:
    python translate_book.py input/book.pdf
    python translate_book.py input/book.pdf --genre philosophy --no-preread
    python translate_book.py input/book.epub --model deepseek-v4-pro
"""

import argparse
import json
import sys
import time
import threading
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from config import load_config, save_config, DEFAULT_CONFIG, calc_cost
from extractor import extract_book
from kg_builder import build_knowledge_graph, kg_to_glossary
from chunker import chunk_text, parse_structure
from vector_store import TranslationVectorStore
from consistency import ConsistencyModel, generate_consistency_report
from translator import translate_chapter
from assembler import assemble_translations, assemble_book
from api_client import call_api

console = Console()


def main():
    start_time = time.time()
    parser = argparse.ArgumentParser(
        description="book-translation — AI 全书翻译工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("book", help="输入文件路径 (PDF/EPUB/TXT)")
    parser.add_argument("--config", help="配置文件路径 (JSON)", default=None)
    parser.add_argument("--genre", help="体裁 (auto|literature|philosophy|natural_science|social_science|technical)", default="auto")
    parser.add_argument("--model", help="LLM 模型名", default="deepseek-v4-pro")
    parser.add_argument("--api-key", help="API Key", default=None)
    parser.add_argument("--api-base", help="API Base URL", default=None)
    parser.add_argument("--no-vision", help="禁用 marker 视觉提取，使用 fitz", action="store_true")
    parser.add_argument("--no-preread", help="跳过 Agentic Pre-Read (KG)", action="store_true")
    parser.add_argument("--no-rat", help="禁用 RAT 检索增强", action="store_true")
    parser.add_argument("--target-tokens", help="每块目标 token 数", type=int, default=1500)
    parser.add_argument("--overlap", help="重叠句子数（覆盖默认值）", type=int, default=None)
    parser.add_argument("--output", help="输出文件路径", default=None)
    parser.add_argument("--format", help="输出格式 (txt|md|pdf|epub)", default="txt")
    parser.add_argument("--parallel", help="并行翻译线程数（默认 0=禁用，建议 4）", type=int, default=0)
    parser.add_argument("--clear-cache", help="清空向量存储并重新翻译", action="store_true")
    parser.add_argument("-v", "--verbose", help="详细输出", action="store_true")

    args = parser.parse_args()

    # 加载配置
    cfg = load_config(args.config)
    cfg["model"] = args.model
    if args.api_key:
        cfg["api_key"] = args.api_key
    if args.api_base:
        cfg["api_base"] = args.api_base
    cfg["genre"] = args.genre if args.genre != "auto" else cfg.get("genre", "auto")
    if args.overlap is not None:
        cfg["overlap_by_genre"][cfg["genre"]] = args.overlap

    # 显示配置
    overlap = cfg["overlap_by_genre"].get(cfg["genre"], 3)
    if args.overlap is not None:
        overlap = args.overlap
    _print_header(args.book, cfg, args.target_tokens, overlap)

    # 可选功能检测
    _check_cli_features(cfg, args)

    # === Phase 0: 提取 + Pre-Read ===
    console.print("\n[bold cyan]━━━ Phase 0: 提取 + 预读 ━━━[/bold cyan]")

    book_path = Path(args.book)
    if not book_path.exists():
        console.print(f"[red]❌ 文件不存在: {args.book}[/red]")
        sys.exit(1)

    # 提取
    use_vision = not args.no_vision
    book_md = extract_book(str(book_path), use_vision=use_vision)
    console.print(f"  提取: {len(book_md)} 字符")

    # 解析章节结构
    chapters = parse_structure(book_md)
    console.print(f"  章节: {len(chapters)} 章")

    # Agentic Pre-Read
    kg = {}
    glossary = {}

    if not args.no_preread and cfg.get("enable_agentic_preread", True):
        def llm_for_kg(system_prompt, user_prompt):
            return _make_llm_call(cfg, system_prompt, user_prompt, max_tokens=4096)

        kg = build_knowledge_graph(
            book_md,
            llm_for_kg,
            sample_ratio=cfg.get("preread_sample_ratio", 0.1),
            max_sample_tokens=cfg.get("preread_max_sample_tokens", 30000),
        )
        glossary = kg_to_glossary(kg)

        # 保存 KG
        kg_path = PROJECT_ROOT / "reports" / "knowledge_graph.json"
        with open(kg_path, "w", encoding="utf-8") as f:
            json.dump(kg, f, ensure_ascii=False, indent=2)
        console.print(f"  KG 已保存到 {kg_path}")
        console.print(f"  Glossary: {len(glossary)} 个术语")
    else:
        console.print("  [dim]跳过 Pre-Read[/dim]")

    # 如果 genre 是 auto，从 KG 推断
    if cfg["genre"] == "auto":
        kg_genre = kg.get("book_metadata", {}).get("genre", "natural_science")
        cfg["genre"] = kg_genre
        if not args.no_preread:
            console.print(f"  自动检测体裁: {kg_genre}")

    # === Phase 1: 分块 ===
    console.print("\n[bold cyan]━━━ Phase 1: 语义分块 ━━━[/bold cyan]")

    overlap = cfg["overlap_by_genre"].get(cfg["genre"], 3)
    all_chapter_chunks = []
    all_chapter_translations = []

    for ch_idx, chapter in enumerate(chapters):
        chapter_text = "\n\n".join(chapter.get("paragraphs", []))
        if not chapter_text.strip():
            continue

        chunks = chunk_text(
            chapter_text,
            target_tokens=args.target_tokens,
            max_tokens=cfg.get("chunk_max_tokens", 3000),
            overlap_sentences=overlap,
        )
        all_chapter_chunks.append((chapter["title"], chunks))
        console.print(f"  {chapter['title']}: {len(chunks)} 块 (重叠 {overlap} 句)")

    total_chunks = sum(len(c) for _, c in all_chapter_chunks)
    console.print(f"  总计: {total_chunks} 块")

    # === Phase 2: 翻译 ===
    parallel_workers = args.parallel if args.parallel > 0 else cfg.get("parallel_workers", 0)
    if parallel_workers > 1:
        console.print(f"\n[bold cyan]━━━ Phase 2: RAT 翻译 ({total_chunks} 块, 并行 {parallel_workers} 线程) ━━━[/bold cyan]")
    else:
        console.print(f"\n[bold cyan]━━━ Phase 2: RAT 翻译 ({total_chunks} 块) ━━━[/bold cyan]")

    # 初始化向量存储
    if args.no_rat:
        vector_store = None
    else:
        vector_store = TranslationVectorStore(
            persist_dir=cfg["vector_store_dir"]
        )
        if args.clear_cache:
            vector_store.initialize()
            vector_store.clear()

    # 一致性模型
    consistency_model = ConsistencyModel()

    # LLM 调用函数
    def llm_translate(system_prompt, user_prompt):
        return _make_llm_call(cfg, system_prompt, user_prompt,
                              max_tokens=cfg.get("max_tokens_per_chunk", 4096))

    all_chapter_translations = []

    if parallel_workers > 1 and len(all_chapter_chunks) > 1:
        # 并行翻译
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cost_lock = threading.Lock()
        consistency_lock = threading.Lock()

        def translate_one(title, chunks):
            cm = ConsistencyModel()
            checkpoint_path = str(PROJECT_ROOT / "cache" / f"checkpoint_{title}.json")
            def llm_call(sp, up):
                return _make_llm_call(cfg, sp, up,
                                      max_tokens=cfg.get("max_tokens_per_chunk", 4096))
            trans = translate_chapter(
                chapter_title=title, chunks=chunks,
                vector_store=vector_store if not args.no_rat else None,
                consistency_model=cm, glossary=glossary, kg=kg,
                llm_call=llm_call, config=cfg,
                checkpoint_path=checkpoint_path,
                cost_lock=cost_lock,
            )
            # 合并一致性模型
            with consistency_lock:
                for term_en, usages in cm.term_usage.items():
                    for zh, count in usages.items():
                        consistency_model.term_usage[term_en][zh] += count
                for term_en, locs in cm.term_locations.items():
                    consistency_model.term_locations[term_en].extend(locs)
            return (title, chunks, trans)

        with ThreadPoolExecutor(max_workers=parallel_workers) as pool:
            futures = {pool.submit(translate_one, t, c): t for t, c in all_chapter_chunks}
            for fut in as_completed(futures):
                title, chunks, trans = fut.result()
                all_chapter_translations.append((title, chunks, trans))
    else:
        # 串行翻译
        for ch_idx, (title, chunks) in enumerate(all_chapter_chunks):
            checkpoint_path = str(PROJECT_ROOT / "cache" / f"checkpoint_{title}.json")
            translations = translate_chapter(
                chapter_title=title,
                chunks=chunks,
                vector_store=vector_store if not args.no_rat else None,
                consistency_model=consistency_model,
                glossary=glossary,
                kg=kg,
                llm_call=llm_translate,
                config=cfg,
                checkpoint_path=checkpoint_path,
            )
            all_chapter_translations.append((title, chunks, translations))

    # === Phase 3: QA ===
    console.print("\n[bold cyan]━━━ Phase 3: 质量审计 ━━━[/bold cyan]")

    # 一致性审计
    issues = consistency_model.audit_all(min_occurrences=3)
    report = generate_consistency_report(
        issues,
        consistency_model.get_glossary_snapshot(),
        output_path=str(PROJECT_ROOT / "reports" / "consistency" / "consistency_report.txt"),
    )
    console.print(report)

    # 保存一致性模型
    consistency_model.save(str(PROJECT_ROOT / "reports" / "consistency_model.json"))

    # 保存最终 glossary
    final_glossary = consistency_model.get_glossary_snapshot()
    glossary_path = PROJECT_ROOT / "reports" / "consistency" / "glossary_final.json"
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(glossary_path, "w", encoding="utf-8") as f:
        json.dump(final_glossary, f, ensure_ascii=False, indent=2)

    # === Phase 4: 组装 ===
    console.print("\n[bold cyan]━━━ Phase 4: 组装 — 去重叠 + 输出 ━━━[/bold cyan]")

    if args.output:
        output_path = args.output
    else:
        book_name = book_path.stem
        output_path = str(PROJECT_ROOT / "output" / book_name / f"{book_name}.txt")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    full_translations = []
    for title, chunks, translations in all_chapter_translations:
        full_text = assemble_translations(
            chunks, translations,
            strategy=cfg.get("assembly_strategy", "first_lock"),
        )
        full_translations.append((title, full_text))

    assemble_book(full_translations, output_path, fmt=args.format)

    # === 完成 ===
    _print_summary(cfg, len(chapters), total_chunks, len(issues), output_path, start_time)


def _make_llm_call(cfg: dict, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> tuple[str, dict]:
    """通过 api_client 封装调用 LLM API（内置重试）。"""
    return call_api(
        api_key=cfg.get("api_key") or cfg.get("DEEPSEEK_API_KEY", ""),
        api_base=cfg.get("api_base", "https://api.deepseek.com/v1"),
        model=cfg.get("model", "deepseek-v4-pro"),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=cfg.get("temperature", 0.3),
        max_retries=cfg.get("max_retries", 3),
        retry_base_delay=cfg.get("retry_base_delay", 2),
        retry_max_delay=cfg.get("retry_max_delay", 30),
    )


def _print_header(book_path: str, cfg: dict, target_tokens: int, overlap: int):
    table = Table(title="📚 book-translation v1.1.4", show_header=False)
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("输入", book_path)
    table.add_row("模型", cfg.get("model", "?"))
    table.add_row("体裁", cfg.get("genre", "auto"))
    table.add_row("分块大小", f"{target_tokens} tokens/块")
    table.add_row("重叠", f"{overlap} 句")
    table.add_row("RAT", "启用" if cfg.get("rat_top_k", 5) > 0 else "禁用")
    console.print(table)


def _check_cli_features(cfg: dict, args):
    """CLI 模式下检测可选功能，如缺失给出提示。"""
    try:
        from env_check import get_optional_features_status
        status = get_optional_features_status()
    except Exception:
        return

    warnings = []

    # 检查 marker（如果没加 --no-vision）
    if not args.no_vision and not status["marker"]["available"]:
        warnings.append(f"[yellow]⚠️ {status['marker']['message']}[/yellow]")
        if status["marker"]["detail"]:
            warnings.append(f"[dim]{status['marker']['detail']}[/dim]")

    # 检查 RAT（如果没加 --no-rat）
    if not args.no_rat and not status["rat"]["available"]:
        warnings.append(f"[yellow]⚠️ {status['rat']['message']}[/yellow]")
        if status["rat"]["detail"]:
            warnings.append(f"[dim]{status['rat']['detail']}[/dim]")

    if warnings:
        console.print()
        for w in warnings:
            console.print(w)
        console.print()


def _print_summary(cfg: dict, num_chapters: int, num_chunks: int, num_issues: int, output_path: str, start_time: float = 0):
    cost = cfg.get("_cost", {})
    prompt_tokens = cost.get("prompt_tokens", 0)
    completion_tokens = cost.get("completion_tokens", 0)

    model = cfg.get("model", "")
    cost_val, cost_str = calc_cost(model, prompt_tokens, completion_tokens)

    elapsed = time.time() - start_time if start_time else 0
    dur_str = f"{int(elapsed//60)}:{int(elapsed%60):02d}"

    console.print()
    console.print("=" * 55)
    console.print("[bold green]✅ 翻译完成！[/bold green]")
    console.print(f"  章节: {num_chapters} 章")
    console.print(f"  分块: {num_chunks} 块")
    console.print(f"  术语漂移: {num_issues} 个")
    console.print(f"  输入 tokens: {prompt_tokens:,}")
    console.print(f"  输出 tokens: {completion_tokens:,}")
    if cost_val is not None:
        console.print(f"  费用: ${cost_val:.4f} (~¥{cost_val * 7.2:.2f})")
    else:
        console.print(f"  费用: 自定义模型，费用未知")
    console.print(f"  用时: {dur_str}")
    console.print(f"  输出: {output_path}")
    console.print("=" * 55)


if __name__ == "__main__":
    main()

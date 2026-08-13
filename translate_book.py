#!/usr/bin/env python3
"""
book-translation CLI — 端到端书籍翻译。

用法:
    python translate_book.py input/book.pdf
    python translate_book.py input/book.pdf --genre philosophy --no-preread
    python translate_book.py input/book.epub --model deepseek-v4-pro
    python translate_book.py input/book.pdf --provider litellm --model openai/gpt-5.5 --reflect
"""

import argparse
import json
import sys
import time
import threading
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from config import load_config, save_config, DEFAULT_CONFIG, MODEL_PRESETS
from api_client import call_api
from extractor import extract_book
from kg_builder import build_knowledge_graph, kg_to_glossary
from chunker import chunk_text, parse_structure
from format_protector import protect, restore
from vector_store import TranslationVectorStore
from consistency import ConsistencyModel, generate_consistency_report
from translator import translate_chapter
from assembler import assemble_translations, assemble_book

console = Console()


def main():
    parser=argparse.ArgumentParser(description="book-translation — AI 全书翻译工具")
    parser.add_argument("book"); parser.add_argument("--config",default=None); parser.add_argument("--genre",default="auto"); parser.add_argument("--provider",default="custom"); parser.add_argument("--model",default="deepseek-v4-pro"); parser.add_argument("--api-key",default=None); parser.add_argument("--api-base",default=None); parser.add_argument("--no-vision",action="store_true"); parser.add_argument("--no-preread",action="store_true"); parser.add_argument("--no-rat",action="store_true"); parser.add_argument("--reflect",action="store_true"); parser.add_argument("--reflect-depth",type=int,default=1); parser.add_argument("--target-tokens",type=int,default=None); parser.add_argument("--overlap",type=int,default=None); parser.add_argument("--output",default=None); parser.add_argument("--format",default="txt"); parser.add_argument("--parallel",type=int,default=0); parser.add_argument("--clear-cache",action="store_true"); parser.add_argument("--strict",action="store_true"); parser.add_argument("-v","--verbose",action="store_true")
    a=parser.parse_args(); cfg=load_config(a.config); cfg.update(provider=a.provider,model=a.model); cfg["genre"]=a.genre if a.genre!="auto" else cfg.get("genre","auto")
    if a.api_key: cfg["api_key"]=a.api_key
    if a.api_base: cfg["api_base"]=a.api_base
    if a.overlap is not None: cfg["overlap_by_genre"][cfg["genre"]]=a.overlap
    if a.reflect: cfg.update(enable_reflection=True,reflection_depth=a.reflect_depth)
    if a.strict: cfg["strict_assembly"]=True
    _target_tokens = a.target_tokens if a.target_tokens is not None else cfg.get("chunk_target_tokens", 1500)
    _print_header(a.book,cfg,_target_tokens,a.overlap if a.overlap is not None else cfg["overlap_by_genre"].get(cfg.get("genre","auto"),3)); _check_cli_features(cfg,a)
    from pipeline import run_translation_pipeline
    with Progress(SpinnerColumn(),TextColumn("{task.description}"),BarColumn(),TaskProgressColumn(),TimeElapsedColumn(),TimeRemainingColumn(),console=console) as pr:
        task=pr.add_task("翻译中...",total=1)
        result=run_translation_pipeline(vars(a)|{"config":cfg},log_fn=console.print,progress_fn=lambda f,m:pr.update(task,completed=f,description=m))
    _print_summary(result)

def _print_header(book_path: str, cfg: dict, target_tokens: int, overlap: int):
    provider = cfg.get("provider", "custom")
    model = cfg.get("model", "?")
    rat = "on" if cfg.get("rat_top_k", 5) > 0 else "off"
    reflect = "on" if cfg.get("enable_reflection") else "off"
    console.print(f"Itranslation - {book_path}")
    console.print(f"model={model} ({provider}) | genre={cfg.get('genre','auto')} | chunk={target_tokens}t/{overlap}o | RAT={rat} | reflection={reflect}")


def _check_cli_features(cfg: dict, args):
    try:
        from env_check import get_optional_features_status
        status = get_optional_features_status()
    except Exception:
        return

    warnings = []
    if str(getattr(args, "book", "")).lower().endswith(".pdf") and not args.no_vision and not status["marker"]["available"]:
        warnings.append(f"[yellow]⚠️ {status['marker']['message']}[/yellow]")
        if status["marker"]["detail"]:
            warnings.append(f"[dim]{status['marker']['detail']}[/dim]")
    if not args.no_rat and not status["rat"]["available"]:
        warnings.append(f"[yellow]⚠️ {status['rat']['message']}[/yellow]")
        if status["rat"]["detail"]:
            warnings.append(f"[dim]{status['rat']['detail']}[/dim]")

    if warnings:
        console.print()
        for w in warnings:
            console.print(w)
        console.print()


def _print_summary(result: dict):
    num_chapters = result["num_chapters"]
    num_chunks = result["num_chunks"]
    num_issues = result["num_issues"]
    num_errors = result["num_errors"]
    output_path = result["output_path"]

    elapsed = result.get("elapsed_sec", 0) or 0
    dur_str = f"{int(elapsed//60)}:{int(elapsed%60):02d}"

    console.print(f"Translation complete | chapters: {num_chapters} | chunks: {num_chunks} | term drifts: {num_issues} | errors: {num_errors} | elapsed: {dur_str}")
    console.print(f"tokens used: {result.get('prompt_tokens', 0):,} in / {result.get('completion_tokens', 0):,} out")
    console.print(f"output: {output_path}")
    if num_errors > 0:
        console.print(f"\n[yellow]Re-run to skip completed chunks and retry the remaining {num_errors} failed ones[/yellow]")


if __name__ == "__main__":
    main()

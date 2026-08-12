<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/version-1.4.0-536DFE" alt="Version">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README-CN.md">简体中文</a>
</p>

<h1 align="center">Itranslation</h1>
<p align="center"><strong>AI-Powered Book Translation · CLI + Desktop GUI</strong></p>
<p align="center">
  PDF · EPUB · TXT · Markdown → Chinese<br>
  Sentence-Level Chunking · Overlap Redundancy · RAT · KG Pre-Read · Reflection · Consistency Audit · Checkpoint/Resume · Cost Tracking
</p>

> This project is under active development. Test with short texts (< 3,000 words) before processing larger files. Translations may be interrupted by network issues or API errors.

---

## Overview

Itranslation is a desktop application and command-line tool for translating entire books from English to Chinese. It accepts PDF, EPUB, TXT, and Markdown files, processes them through a multi-phase pipeline with sentence-level chunking, agentic knowledge-graph pre-reading, terminology consistency auditing, and an optional reflection workflow — then outputs clean Chinese text in TXT, Markdown, PDF, or EPUB format.

> **Knowledge should be free.** We encourage all users to share their translated books publicly — on [Internet Archive](https://archive.org), [GitHub](https://github.com), personal blogs, or any open platform. Every translation removes a language barrier between a reader and a book.

---

## Key Differentiators

| Capability | Typical Approach | Itranslation |
|---|---|---|
| Chunking | Fixed line count | Sentence-level tokenization with configurable overlap |
| Terminology Consistency | LLM memory across calls | Incremental tracking model with drift detection |
| Translation Quality | Single-pass, no validation | Overlap redundancy + RAT + KG pre-read + real-time audit |
| Post-Translation QA | Output as-is | Reflection workflow (translate → reflect → revise) |
| Interruption Handling | Restart from beginning | Checkpoint-based resume (GUI & CLI) |
| Cost Visibility | Unknown until billing | Real-time per-chunk token and cost display |

---

## Installation

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), and a [DeepSeek API key](https://platform.deepseek.com/).

```bash
git clone https://github.com/Yisan0429/Itranslation.git
cd Itranslation
uv sync
```

Optional extras:

```bash
uv sync --extra vision  # Marker visual PDF extraction (~1.4 GB model)
uv sync --extra rat     # Retrieval-Augmented Translation (~300 MB)
```

Launch:

```bash
uv run python desktop.py                                                       # Desktop GUI
uv run python translate_book.py book.pdf --genre literature --format pdf     # CLI
```

## API Configuration

Create your config from the template: `cp config.example.json config.json`, then fill in your key. Configuration precedence (highest first): CLI flags > GUI inputs > `config.json` > environment variables.

### Provider modes

| Mode | Provider value | Model format | Key source |
|---|---|---|---|
| Custom (OpenAI-compatible) | `custom` | any, e.g. `deepseek-v4-pro` | `DEEPSEEK_API_KEY` env var, `config.json`, or GUI/CLI |
| liteLLM (100+ models) | `litellm` | `openai/gpt-5.5`, `anthropic/claude-sonnet-4-6`, `gemini/gemini-3.5-pro` | `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` env vars, or explicit key |

### `config.json` examples

DeepSeek (default values):

```json
{
    "api_key": "sk-...",
    "model": "deepseek-v4-pro",
    "api_base": "https://api.deepseek.com/v1"
}
```

OpenAI via liteLLM:

```json
{
    "provider": "litellm",
    "model": "openai/gpt-5.5"
}
```

Any OpenAI-compatible endpoint:

```json
{
    "provider": "custom",
    "api_key": "sk-...",
    "api_base": "https://your-endpoint.example.com/v1",
    "model": "your-model-name"
}
```

### Tiered models

By default `use_tiered_models` is `true` and the pipeline uses three tiers (`llm_tiers.strong` for translation, `cheap` for audit, `fast` for pre-read), all preset to DeepSeek. When switching providers, either update `llm_tiers` accordingly or set `"use_tiered_models": false` to use a single `model` everywhere.

### CLI

```bash
uv run python translate_book.py book.txt --provider deepseek --model deepseek-v4-pro     --api-key sk-xxx --api-base https://api.deepseek.com/v1
```

### GUI

Fill in Provider / Model / API Key / API Base in the left panel. Values apply to the current session and are not persisted.

---

## Features

### Input Formats

| Format | Engine | Notes |
|---|---|---|
| PDF | PyMuPDF (default) / Marker (optional) | Marker adds multi-column and table support |
| EPUB | ebooklib | Preserves chapter structure |
| TXT / MD | Direct read | No extraction overhead |

### Genre-Aware Translation

Five presets (literature / philosophy / natural science / social science / technical) adapt tone, terminology handling, and format-protection rules per genre.

### Output Formats

TXT, Markdown, PDF (embedded CJK font), EPUB (chapter navigation).

### Reflection Workflow

Optional translate → reflect → revise loop; roughly 2× token consumption for higher quality on literary and philosophical texts. Enable with `--reflect` or the GUI switch.

### Parallel Translation

Chapters are translated concurrently with a configurable thread pool (default 4 workers; `parallel_workers: 0` disables).

### Checkpoint & Resume

Progress is persisted after every chunk. Interrupted runs resume with completed chunks skipped and failed chunks retried automatically. Checkpoints are named by book slug plus chapter index, so different books never collide.

### Quality Audit

After translation, a defect-family scan (10 regex families: passive-voice overuse, long modifiers, calques, nominalization, etc.) flags candidates at P1/P2/P3 severity with zero API cost; the incremental consistency model alerts when any term's dominant translation falls below 80%.

### RAT (Retrieval-Augmented Translation)

Translated passages are stored in a ChromaDB vector store (all-MiniLM-L6-v2 embeddings) and retrieved as reference context for new chunks. If dependencies are missing, translation continues without retrieval — with an explicit warning.

---

## Architecture

```
Input (PDF / EPUB / TXT / MD)
  │
  ├─ Phase 0: Extraction & Pre-Read — PyMuPDF or Marker → text cleaning → optional KG construction
  ├─ Phase 1: Semantic Chunking — sentence tokenization → greedy packing → overlap (3–4 sentences)
  ├─ Phase 2: Translation (parallel) + Reflection — per-chunk: terminology injection + RAT context → LLM → vector store
  ├─ Phase 3: Quality Audit — defect-family scan (10 regex families) + consistency model audit
  └─ Phase 4: Assembly — sentence-aligned body_join (first-lock fallback for legacy checkpoints) → output
```

## CLI Reference

```bash
uv run python translate_book.py book.pdf                            # Basic usage
uv run python translate_book.py book.pdf --genre philosophy --format pdf
uv run python translate_book.py book.pdf --no-preread --no-rat      # Fast mode
uv run python translate_book.py book.pdf --parallel 4 --output out/
uv run python translate_book.py book.pdf --provider litellm --model openai/gpt-5.5 --reflect
```

---

## Project Structure

```
Itranslation/
├── translate_book.py     CLI entry point (thin arg-parsing layer)
├── desktop.py            NiceGUI desktop application (UI layer only)
├── Itranslation-cli.spec PyInstaller build spec
├── src/
│   ├── pipeline.py       Unified translation pipeline (shared by CLI and GUI)
│   ├── extractor.py      PDF/EPUB/TXT/MD text extraction
│   ├── kg_builder.py     Agentic pre-read and knowledge graph construction
│   ├── chunker.py        Sentence-level chunking with labeled context overlap
│   ├── translator.py     Translation engine (RAT + terminology + reflection + chunk progress callback)
│   ├── consistency.py    Incremental terminology consistency model
│   ├── assembler.py      Sentence-aligned assembly (body_join + first_lock)
│   ├── vector_store.py   ChromaDB vector store for RAT
│   ├── format_protector.py  Code/formula/URL placeholder protection
│   ├── api_client.py     Unified API client (HTTP + liteLLM)
│   ├── auditor.py        Low-token defect-family scan engine
│   ├── defects.py        Defect family registry (10 families)
│   ├── benchmark.py      BLEU/chrF + LLM-as-Judge quality evaluation
│   ├── config.py         Configuration (DEFAULT_CONFIG + config.json)
│   ├── env_check.py      Optional feature readiness checker
│   └── eval.py           Component evaluation suite
├── tests/                Unit tests (chunker / assembler / checkpoint / defects / format protector)
├── input/                Source documents
├── output/               Translations (one folder per book)
├── reports/              Audit reports + benchmark results
├── cache/                Checkpoint files (JSON, named by book slug + chapter index)
└── models/               Model cache (Marker, sentence-transformers)
```

---

## Acknowledgments

Itranslation builds on ideas and inspiration from the following projects, studied across multiple development sessions:

| Project | What We Learned |
|:---|:---|
| [LifeBook](https://github.com/SaberOnGo/public-domain-books-translation) | Defect family classification, low-token audit, per-chapter quality gates, stratified random spot-checking (v1.3.3) |
| [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) | Bilingual EPUB output, sliding-window context as user/assistant pairs, delimiter-based batching, multi-key rotation (v1.0 foundation) |
| [Translation Agent](https://github.com/andrewyng/translation-agent) | Reflection workflow (translate → reflect → improve), agentic translation architecture (v1.3.0) |
| [TranslateBooksWithLLMs](https://github.com/hydropix/TranslateBooksWithLLMs) | Pre-built executables, format-preserving EPUB translation, Docker deployment (v1.3.1) |
| [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin) | MD5 content cache for re-runs, 48 input / 20 output formats, multi-engine design (v1.0 research) |
| [ebook-GPT-translator](https://github.com/jesselau76/ebook-GPT-translator) | Multi-format input support, SQLite-based resume caching (v1.0 research) |
| [pdf-translate](https://github.com/withmargin/pdf-translate) | Page-level isolation for non-narrative texts, layout preservation via content stream manipulation (v1.0 research) |
| [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate) | Self-hosted API design, Google Translate API format compatibility (v1.0 research) |
| [Argos Translate](https://github.com/argosopentech/argos-translate) | Offline NMT capability, language-pair model architecture (v1.0 research) |
| [Opus-MT](https://github.com/Helsinki-NLP/Opus-MT) | Open neural MT models, Marian NMT framework, 1000+ language pairs (v1.0 research) |
| [EasyNMT](https://github.com/UKPLab/EasyNMT) | Unified interface for multiple MT engines (v1.0 research) |
| [translate-shell](https://github.com/soimort/translate-shell) | CLI-first translation UX, multi-provider abstraction (v1.0 research) |
| [sacrebleu](https://github.com/mjpost/sacrebleu) | BLEU and chrF evaluation metrics for Chinese translation (v1.3.0) |
| [NiceGUI](https://github.com/zauberzeug/nicegui) | Desktop GUI framework with browser and native window modes (v1.2.0) |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | Standalone Windows executable packaging (v1.3.1) |

---

## License

MIT © 2026

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/version-1.1.1-536DFE" alt="Version">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20V4-536DFE?logo=deepseek" alt="DeepSeek">
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README-CN.md">简体中文</a>
</p>

<h1 align="center">Itranslation</h1>
<p align="center"><strong>AI-Powered Book Translation · Desktop GUI & CLI</strong></p>
<p align="center">
  PDF · EPUB · TXT · Markdown → Chinese<br>
  Sentence-Level Chunking · Consistency Audit · Pause/Resume · Cost Tracking
</p>

---

## Overview

Itranslation is a desktop application and command-line tool for translating entire books using large language models. It accepts PDF, EPUB, TXT, and Markdown files, processes them through a multi-phase pipeline with sentence-level chunking, terminology consistency auditing, and retrieval-augmented translation (RAT), then outputs clean Chinese text in TXT, Markdown, or PDF format.

Unlike tools that split text at arbitrary line boundaries, Itranslation tokenizes at the sentence level and employs overlapping chunks with a first-lock deduplication strategy — ensuring that no sentence is ever broken mid-thought.

---

## Key Differentiators

| Capability | Typical Approach | Itranslation |
|---|---|---|
| Chunking | Fixed line count (e.g., every 10 lines) | Sentence-level tokenization with configurable overlap |
| Terminology Consistency | Relies on LLM memory across calls | Incremental tracking model with automated drift detection |
| Translation Quality | Single-pass, no validation | Overlap redundancy + real-time audit at configurable intervals |
| Interruption Handling | Restart from beginning | Pause/Resume in GUI; checkpoint-based resume in CLI and GUI |
| Cost Visibility | Unknown until billing | Per-chunk token consumption and cost displayed in real time ($/¥) |
| Model Flexibility | Hardcoded provider | Preset models (DeepSeek V4 Pro/Flash) + custom OpenAI-compatible API configuration |

---

## Installation

### Prerequisites

- **Python 3.11** or later — [python.org](https://www.python.org/downloads/)
- **uv** package manager — `pip install uv`
- **DeepSeek API Key** — [platform.deepseek.com](https://platform.deepseek.com/) (free registration)

### Setup

```bash
git clone https://github.com/Yisan0429/Itranslation.git
cd Itranslation
uv sync
```

Core dependencies total approximately 80 MB and install in under 10 seconds.

### Optional Features

```bash
# Marker-based visual PDF extraction (90%+ accuracy for complex layouts; ~1.4 GB model download)
uv sync --extra vision

# Retrieval-Augmented Translation (ChromaDB + sentence-transformers; ~300 MB)
uv sync --extra rat
```

### Launch

```bash
# Desktop GUI
uv run python desktop.py

# Command line
uv run python translate_book.py book.pdf --genre literature --format pdf
```

On Windows, `book-translation.vbs` provides a silent GUI launcher (no terminal window).

---

## Features

### Input Formats

| Format | Extraction Engine | Accuracy | Notes |
|---|---|---|---|
| **PDF** | PyMuPDF (default) | 60–70% | Suitable for standard single-column layouts |
| **PDF** | Marker (optional) | 90%+ | Multi-column, tables, complex formatting; requires model download |
| **EPUB** | ebooklib | ~99% | Preserves chapter structure |
| **TXT / MD** | Direct read | 100% | No extraction overhead |

### Genre-Aware Translation

| Genre | Strategy | Use Cases |
|---|---|---|
| Literature | Preserve rhetoric, rhythm, and emotional tone; elegant modern Chinese | Novels, poetry, essays |
| Philosophy | Faithful direct translation; maintain logical structure; consistent terminology | Academic philosophy, treatises |
| Natural Science | Terminology accuracy prioritized; data, formulas, and units preserved verbatim | Textbooks, research papers |
| Social Science | Balanced direct translation with readability; citation format preserved | History, sociology, economics |
| Technical | Code, commands, and configuration values left unchanged | Documentation, manuals |

### Output Formats

- **TXT** — Plain text, minimal file size
- **MD** — Markdown with heading hierarchy and paragraph structure
- **PDF** — Typeset PDF with embedded CJK font (auto-detected per platform)

### Translation Models

| Model | Input Price | Output Price | Best For |
|---|---|---|---|
| DeepSeek V4 Pro | $0.435 / 1M tokens | $0.87 / 1M tokens | Highest translation quality |
| DeepSeek V4 Flash | $0.14 / 1M tokens | $0.28 / 1M tokens | High-speed, cost-sensitive tasks |
| Custom | — | — | Any OpenAI-compatible API (Ollama, vLLM, Groq, etc.) |

### Parallel Translation (v1.1)

Chapters are translated concurrently using a configurable thread pool. Default parallelism is 4 workers; disable by setting `parallel_workers: 0` in config or passing `--parallel 0` on the CLI.

### Checkpoint & Resume (v1.1)

Both GUI and CLI persist translation progress after each chapter. If a translation is interrupted — by network failure, application crash, or user cancellation — restarting on the same file presents a resume prompt with completed chapter list.

---

## Architecture

```
Input (PDF / EPUB / TXT / MD)
  │
  ├─ Phase 0: Extraction & Pre-Read
  │   └─ PyMuPDF or Marker → text cleaning → optional Knowledge Graph construction
  │
  ├─ Phase 1: Semantic Chunking
  │   └─ Sentence tokenization → greedy packing → overlap (3–4 sentences)
  │
  ├─ Phase 2: Translation (Parallel)
  │   └─ Per-chunk: terminology injection + context → LLM API → vector store
  │
  ├─ Phase 3: Quality Audit
  │   └─ Consistency model: audit every N chunks; alert if term consistency < 80%
  │
  └─ Phase 4: Assembly
      └─ Overlap removal (first-lock strategy) → TXT / MD / PDF output
```

### Core Design Decisions

**Sentence-Level Chunking.** Input text is split into sentences, then greedily packed into chunks of configurable token size. Adjacent chunks overlap by 3–4 sentences. During assembly, the first occurrence of each sentence is retained and subsequent duplicates are discarded. This provides redundant translation coverage at approximately 5% token overhead.

**Incremental Consistency Model.** Each term translation is recorded with its source location. After every 20 chunks (configurable), the model audits all tracked terms. Any term whose dominant translation falls below the 80% consistency threshold triggers an alert, identifying both the drift and the suggested canonical translation.

**Retrieval-Augmented Translation.** Previously translated passages are stored in a ChromaDB vector store using `all-MiniLM-L6-v2` embeddings. When translating a new chunk, the system retrieves the most semantically similar prior translations and injects them as reference context into the LLM prompt.

---

## Estimated Cost

Based on DeepSeek V4 Pro pricing and measured throughput:

| Book Size | Word Count | Est. Tokens | Est. Duration | Est. Cost |
|---|---|---|---|---|
| Short story | 3,000 | ~5K in / 5K out | ~10 sec | ~$0.01 (¥0.07) |
| Novella | 30,000 | ~50K in / 50K out | ~2 min | ~$0.07 (¥0.50) |
| Novel | 100,000 | ~150K in / 140K out | ~7 min | ~$0.20 (¥1.44) |
| Epic | 300,000 | ~450K in / 420K out | ~20 min | ~$0.60 (¥4.32) |

Measured: 1,196-word literary excerpt → 2 chunks → $0.0076 (¥0.06) in 10 seconds.

Cost calculation is automatic for DeepSeek models. Custom models display token counts without a monetary estimate to prevent misleading figures.

---

## CLI Reference

```bash
# Basic usage
uv run python translate_book.py book.pdf

# Genre + output format
uv run python translate_book.py book.pdf --genre philosophy --format pdf

# Fast mode (skip pre-read and RAT)
uv run python translate_book.py book.pdf --no-preread --no-rat

# Parallel translation with custom output
uv run python translate_book.py book.pdf \
  --genre literature \
  --format md \
  --model deepseek-v4-flash \
  --parallel 4 \
  --output final/translation
```

---

## Project Structure

```
Itranslation/
├── desktop.py            Desktop GUI (tkinter, high-DPI support)
├── translate_book.py     CLI entry point
├── extractor.py          PDF/EPUB/TXT/MD text extraction
├── chunker.py            Sentence-level semantic chunking with overlap
├── translator.py         Translation engine (RAT + terminology injection)
├── assembler.py          Overlap removal + TXT/MD/PDF output
├── consistency.py        Incremental terminology consistency model
├── vector_store.py       ChromaDB vector store for RAT
├── kg_builder.py         Agentic pre-read and knowledge graph construction
├── config.py             Configuration management (DEFAULT_CONFIG + config.json)
├── env_check.py          Optional feature readiness checker
├── input/                Source documents
├── final/                Completed translations
├── cache/                Checkpoint files (JSON)
└── models/               Model cache (Marker, sentence-transformers)
```

---

## Comparison with Related Work

### Top 5 Open-Source Projects (by GitHub stars)

| # | Project | Stars | Scope | Strengths | Limitations |
|---|---------|-------|-------|-----------|-------------|
| 1 | [Immersive Translate](https://github.com/immersive-translate/immersive-translate) | 17.8k | Browser extension (web, PDF, EPUB) | Broad platform coverage; 100+ languages; real-time bilingual display | Requires browser extension; not a standalone translation tool; Pro tier is paid |
| 2 | [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) | 9.3k | CLI ebook translator | Mature ecosystem (5 years); bilingual output; 40+ models via liteLLM | No GUI; fixed-line chunking; no terminology auditing |
| 3 | [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin) | 2.5k | Calibre plugin | 48 input formats; 20 output formats; multiple translation engines | Requires Calibre; higher learning curve |
| 4 | [ebook-GPT-translator](https://github.com/jesselau76/ebook-GPT-translator) | 1.7k | CLI ebook translator | Multi-format; modern v2 architecture; SQLite resume cache | CLI only; no translation quality auditing |
| 5 | [epub-translator](https://github.com/oomol-lab/epub-translator) | 771 | EPUB bilingual translation library | Preserves original formatting; clean API | EPUB only; early-stage ecosystem |

### Feature Comparison

| Dimension | Itranslation v1.1 | bilingual_book_maker | Calibre Plugin | ebook-GPT-translator | epub-translator |
|:---|:---:|:---:|:---:|:---:|:---:|
| Desktop GUI | ✓ | — | ✓ (via Calibre) | — | — |
| Checkpoint/Resume | ✓ (GUI + CLI) | ✓ | ✓ | ✓ | — |
| Parallel Translation | ✓ (chapter-level) | ✓ (API batch) | ✓ (multi-book) | — | ✓ |
| Sentence-Level Chunking | ✓ | — | — | — | — |
| Overlap Redundancy | ✓ | — | — | — | — |
| Terminology Consistency | ✓ (real-time audit) | Partial | — | — | — |
| Genre Adaptation | ✓ (5 presets) | Partial | — | Partial | — |
| Knowledge Graph Pre-Read | ✓ | — | — | — | — |
| RAG-Augmented Translation | ✓ (ChromaDB) | — | — | — | — |
| Cost Tracking | ✓ ($/¥ real-time) | — | — | — | ✓ |
| Bilingual Output | — | ✓ | — | — | ✓ |
| Output Formats | TXT / MD / PDF | Bilingual EPUB / TXT | 20 formats | EPUB / TXT | EPUB |
| Model Support | DeepSeek + custom | 40+ (liteLLM) | Multi-engine | OpenAI family | OpenAI / Claude |
| Maturity | v1.1 (2026) | 5 years | 3 years | v2 (2025) | v0.1 (2025) |

### Unique Advantages

1. **Translation Quality Pipeline.** Sentence-level chunking, overlap redundancy, and real-time terminology auditing form an integrated quality loop absent from every comparable open-source project.
2. **Desktop GUI.** The only standalone tool in this comparison that offers both a native desktop interface and a CLI — suitable for non-technical users without requiring additional software such as Calibre.
3. **Cost Transparency.** Token consumption and estimated cost (in both USD and CNY) update in real time. Custom models are explicitly annotated to avoid displaying incorrect pricing.

### Known Gaps

1. **No bilingual output.** Both bilingual_book_maker and epub-translator produce side-by-side bilingual editions — a frequently requested feature not yet available.
2. **Early-stage ecosystem.** v1.1 versus competitors with years of community-driven iteration and bug fixes.
3. **Limited input format coverage.** Four formats (PDF, EPUB, TXT, MD) versus Calibre Plugin's 48.

---

## FAQ

**What happens if the network drops mid-translation?**

Both the GUI and CLI persist translation progress after every chapter. Re-running on the same file detects the existing checkpoint and offers to resume from the interruption point.

**Can scanned/image-based PDFs be translated?**

Yes, using the Marker visual extraction engine. Select "marker (视觉, 90%+ 精度)" as the PDF extraction method. Model files (~2 GB) are downloaded automatically on first use.

**Can I use my own LLM provider?**

Select "自定义..." from the model dropdown, then click the gear icon (⚙) to configure the API base URL, model name, and API key. Any OpenAI-compatible endpoint is supported (Ollama, vLLM, Groq, etc.).

**How do I run the environment checker?**

```bash
uv run python env_check.py
```

This reports whether Marker and RAT optional features are fully installed and ready.

---

## License

MIT © 2026

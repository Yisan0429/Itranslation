<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/version-1.3.3-536DFE" alt="Version">
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
| Chunking | Fixed line count (e.g., every 10 lines) | Sentence-level tokenization with configurable overlap |
| Terminology Consistency | Relies on LLM memory across calls | Incremental tracking model with automated drift detection |
| Translation Quality | Single-pass, no validation | Overlap redundancy + RAT + KG pre-read + real-time audit at configurable intervals |
| Post-Translation QA | Output as-is | Reflection workflow: LLM self-review → revision (translate → reflect → improve) |
| Interruption Handling | Restart from beginning | Pause/Resume in GUI; checkpoint-based resume in CLI and GUI |
| Cost Visibility | Unknown until billing | Per-chunk token consumption and cost displayed in real time ($/¥) |
| Quality Benchmarking | None | Built-in BLEU/chrF scoring + LLM-as-Judge evaluation suite |

---

## Installation

### Prerequisites

- Python 3.11 or later — [python.org](https://www.python.org/downloads/)
- uv package manager — `pip install uv`
- DeepSeek API Key — [platform.deepseek.com](https://platform.deepseek.com/) (free registration)

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

---

## Features

### Input Formats

| Format | Extraction Engine | Accuracy | Notes |
|---|---|---|---|
| PDF | PyMuPDF (default) | 60–70% | Suitable for standard single-column layouts |
| PDF | Marker (optional) | 90%+ | Multi-column, tables, complex formatting; requires model download |
| EPUB | ebooklib | ~99% | Preserves chapter structure |
| TXT / MD | Direct read | 100% | No extraction overhead |

### Genre-Aware Translation

| Genre | Strategy | Use Cases |
|---|---|---|
| Literature | Preserve rhetoric, rhythm, and emotional tone; elegant modern Chinese | Novels, poetry, essays |
| Philosophy | Faithful direct translation; maintain logical structure; consistent terminology | Academic philosophy, treatises |
| Natural Science | Terminology accuracy prioritized; data, formulas, and units preserved verbatim | Textbooks, research papers |
| Social Science | Balanced direct translation with readability; citation format preserved | History, sociology, economics |
| Technical | Code, commands, and configuration values left unchanged | Documentation, manuals |

### Output Formats

- TXT — Plain text, minimal file size
- MD — Markdown with heading hierarchy and paragraph structure
- PDF — Typeset PDF with embedded CJK font (auto-detected per platform)
- EPUB — Standard e-book format with chapter navigation

### Translation Models

| Provider | Model | Input Price | Output Price | Best For |
|---|---|---|---|---|
| DeepSeek | V4 Pro / V4 Flash | $0.14–0.435 | $0.28–0.87 | Best cost-quality ratio |
| OpenAI | GPT-5.5 / GPT-5.5 Mini | $1.50–5.00 | $6.00–15.00 | Highest general quality |
| Anthropic | Opus 4.8 / Sonnet 4.6 / Fable 5 | $3.00–10.00 | $15.00–50.00 | Literary nuance; complex reasoning |
| Google | Gemini 3.5 Pro / 3.5 Flash | $0.30–3.50 | $1.50–10.50 | Long documents; speed |
| Mimo | MiMo-V2.5-Pro / MiMo-V2.5 | $0.40–1.20 | $1.60–4.80 | Multimodal understanding |
| Custom | — | — | — | Any OpenAI-compatible API |

### Reflection Workflow

When enabled, each translated chunk goes through an additional quality loop:

1. Translate — Initial LLM translation
2. Reflect — LLM reviews the translation against the source, identifying issues in accuracy, fluency, terminology, and style
3. Revise — LLM re-translates based on the reflection feedback

This adds approximately 2× token consumption but significantly improves quality, especially for literary and philosophical texts. Configurable via `--reflect` flag (CLI) or Reflection switch (GUI).

### Parallel Translation

Chapters are translated concurrently using a configurable thread pool. Default parallelism is 4 workers; disable by setting `parallel_workers: 0` in config or passing `--parallel 0` on the CLI.

### Checkpoint & Resume

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
  ├─ Phase 2: Translation (Parallel) + Reflection
  │   └─ Per-chunk: terminology injection + context → LLM API → Reflect → Revise → vector store
  │
  ├─ Phase 3: Quality Audit
  │   └─ Consistency model: audit every N chunks; alert if term consistency < 80%
  │
  └─ Phase 4: Assembly
      └─ Overlap removal (first-lock strategy) → TXT / MD / PDF / EPUB output
```

### Core Design Decisions

Sentence-Level Chunking. Input text is split into sentences, then greedily packed into chunks of configurable token size. Adjacent chunks overlap by 3–4 sentences. During assembly, the first occurrence of each sentence is retained and subsequent duplicates are discarded. This provides redundant translation coverage at approximately 5% token overhead.

Incremental Consistency Model. Each term translation is recorded with its source location. After every 20 chunks (configurable), the model audits all tracked terms. Any term whose dominant translation falls below the 80% consistency threshold triggers an alert, identifying both the drift and the suggested canonical translation.

Retrieval-Augmented Translation. Previously translated passages are stored in a ChromaDB vector store using `all-MiniLM-L6-v2` embeddings. When translating a new chunk, the system retrieves the most semantically similar prior translations and injects them as reference context into the LLM prompt.

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

# Use GPT-5.5 via liteLLM with reflection
uv run python translate_book.py book.pdf \
  --provider litellm \
  --model openai/gpt-5.5 \
  --reflect \
  --format pdf
```

---

## Project Structure

```
Itranslation/
├── translate_book.py     CLI entry point
├── desktop.py            NiceGUI desktop application
├── Itranslation-cli.spec PyInstaller build spec
├── src/
│   ├── extractor.py      PDF/EPUB/TXT/MD text extraction
│   ├── kg_builder.py     Agentic pre-read and knowledge graph construction
│   ├── chunker.py        Sentence-level semantic chunking with overlap
│   ├── translator.py     Translation engine (RAT + terminology injection + reflection)
│   ├── consistency.py    Incremental terminology consistency model
│   ├── assembler.py      Overlap removal + TXT/MD/PDF/EPUB output
│   ├── vector_store.py   ChromaDB vector store for RAT
│   ├── format_protector.py  Code/formula/URL placeholder protection
│   ├── api_client.py     Unified API client (HTTP + liteLLM)
│   ├── benchmark.py      BLEU/chrF + LLM-as-Judge quality evaluation
│   ├── config.py         Configuration (DEFAULT_CONFIG + config.json)
│   ├── env_check.py      Optional feature readiness checker
│   └── eval.py           Component evaluation suite
├── input/                Source documents
├── output/               Translations (one folder per book)
├── reports/              Audit reports + benchmark results
├── cache/                Checkpoint files (JSON)
└── models/               Model cache (Marker, sentence-transformers)
```

---

## Comparison with Related Work

### Top 5 Open-Source Projects (by GitHub stars)

| # | Project | Stars | Scope | Strengths | Limitations |
|---|---------|-------|-------|-----------|-------------|
| 1 | [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) | 9.3k | CLI ebook translator | Mature ecosystem (5 years); bilingual output; 40+ models via liteLLM | No GUI; fixed-line chunking; no terminology auditing |
| 2 | [Translation Agent](https://github.com/andrewyng/translation-agent) | 5.8k | Agentic translation demo | Reflection workflow pioneer; highly customizable; MIT license | Experimental/demo; no book-specific features; no GUI |
| 3 | [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin) | 2.5k | Calibre plugin | 48 input formats; 20 output formats; multiple translation engines | Requires Calibre; higher learning curve |
| 4 | [ebook-GPT-translator](https://github.com/jesselau76/ebook-GPT-translator) | 1.7k | CLI ebook translator | Multi-format; modern v2 architecture; SQLite resume cache | CLI only; no translation quality auditing |
| 5 | [TranslateBooksWithLLMs](https://github.com/hydropix/TranslateBooksWithLLMs) | 450 | Desktop app (Web UI) | Pre-built executables (Win/Mac); EPUB/SRT/DOCX/TXT; formatting preservation; Docker | No sentence-level chunking; no RAT; no consistency auditing |

### Feature Comparison

| Dimension | Itranslation | bilingual_book_maker | Calibre Plugin | ebook-GPT-translator | Translation Agent | TranslateBooksWithLLMs |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| Desktop GUI | ✓ (NiceGUI) | — | ✓ (via Calibre) | — | — | ✓ (Web) |
| Checkpoint/Resume | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| Parallel Translation | ✓ | ✓ (API batch) | ✓ (multi-book) | — | — | ✓ |
| Sentence-Level Chunking | ✓ | — | — | — | — | — |
| Overlap Redundancy | ✓ | — | — | — | — | — |
| Terminology Consistency | ✓ | Partial | — | — | — | — |
| Genre Adaptation | ✓ (5 presets) | Partial | — | Partial | — | — |
| Knowledge Graph Pre-Read | ✓ | — | — | — | — | — |
| RAT-Augmented Translation | ✓ (ChromaDB) | — | — | — | — | — |
| Reflection Workflow | ✓ | — | — | — | ✓ | — |
| Format Protection | ✓ | — | — | — | — | — |
| Cost Tracking | ✓ ($/¥) | — | — | — | — | ✓ |
| Bilingual Output | — | ✓ | — | — | — | — |
| Benchmark Suite | ✓ | — | — | — | — | ✓ |
| Output Formats | TXT / MD / PDF / EPUB | Bilingual EPUB / TXT | 20 formats | EPUB / TXT | TXT | TXT / EPUB / SRT |
| Maturity | v1.3 (2026) | 5 years | 3 years | v2 (2025) | Research (2025) | Active (2026) |

### Unique Advantages

1. Most comprehensive open-source translation quality pipeline. Sentence-level chunking, overlap redundancy, RAT retrieval, KG pre-read, and real-time terminology auditing form an integrated quality loop absent from every comparable open-source project. The Reflection workflow adds a translate → reflect → revise cycle adapted from state-of-the-art agentic translation research.
3. Built-in quality benchmarks. The benchmark suite provides BLEU/chrF scoring against reference translations and LLM-as-Judge evaluation across accuracy, fluency, terminology, and style dimensions.
4. Cost transparency. Token consumption and estimated cost (in both USD and CNY) update in real time. Custom models are explicitly annotated to avoid displaying incorrect pricing.
5. API with built-in retry. All LLM API calls include exponential-backoff retry (configurable via `config.json`), ensuring robustness against transient network failures.

---

## FAQ

What happens if the network drops mid-translation?

The CLI persists translation progress after every chapter. Re-running on the same file detects the existing checkpoint and offers to resume from the interruption point.

Can scanned/image-based PDFs be translated?

Yes, using the Marker visual extraction engine. Model files (~2 GB) are downloaded automatically on first use.


How do I run the environment checker?

```bash
uv run python src/env_check.py
```

This reports whether Marker and RAT optional features are fully installed and ready.

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

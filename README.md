# 📚 Itranslation

> AI 全书翻译工具 — 将 PDF / EPUB / TXT / Markdown 书籍翻译为中文。
> 基于 DeepSeek V4，支持桌面 GUI、命令行、断点续传、术语一致性追踪。

[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20V4-536DFE)](https://api-docs.deepseek.com/)

---

## 为什么用这个

大多数开源翻译工具只是"能跑"——机械分块切碎句子、术语前后不一致、没暂停也没进度。这个项目做到了：

- 🧩 **句子级语义分块** — 保证不切碎句子，重叠提供冗余纠错
- 📋 **术语一致性追踪** — 实时审计所有术语翻译，低于 80% 自动报警
- ⏸️ **暂停/恢复** — 翻译到一半随时停，点击继续
- 💰 **实时成本** — 每翻完一块立刻知道花了多少

## 快速开始

### 安装

```bash
git clone https://github.com/Yisan0429/Itranslation.git
cd Itranslation
uv sync
```

### 设置 API Key

在 `config.json` 中填入 DeepSeek API Key，或设置环境变量：

```bash
set DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 启动桌面 GUI

```bash
uv run python desktop.py
```

> 桌面上双击 `book-translation.lnk` 一键启动（无终端窗口）。

### 命令行

```bash
uv run python translate_book.py input/book.pdf --genre literature --format pdf
```

## 功能

### 输入格式

| 格式 | 提取方式 | 精度 |
|------|---------|------|
| PDF | PyMuPDF 文本层 / marker 视觉 | 60-90% |
| EPUB | ebooklib 章节解析 | 99% |
| TXT / MD | 直接读取 | 100% |

### 翻译引擎

- DeepSeek V4 Pro（默认，文学翻译首选）
- DeepSeek V4 Flash（快速/低成本）
- 自定义 OpenAI 兼容 API（支持 Ollama / vLLM / Groq 等）

### 输出格式

- **TXT** — 纯文本
- **MD** — Markdown 带标题层级
- **PDF** — 排版 PDF（自动嵌入中文字体）

### 体裁自动适配

| 体裁 | 翻译策略 |
|------|---------|
| 文学 | 保留修辞、韵律、情感，优雅现代汉语 |
| 哲学 | 直译保真，长句不拆分，术语统一 |
| 自然科学 | 术语精确优先，数据/公式不变 |
| 社会科学 | 直译兼顾可读性，引文格式保留 |
| 技术 | 代码/命令/配置保持不变 |

## 成本

| 书的规模 | 字数 | DeepSeek V4 Pro | DeepSeek V4 Flash |
|---------|------|----------------|-------------------|
| 短篇 | 3,000 | ~¥0.14 | ~¥0.05 |
| 中篇 | 30,000 | ~¥1.08 | ~¥0.36 |
| 长篇 | 100,000 | ~¥3.60 | ~¥1.20 |
| 巨著 | 300,000 | ~¥10.80 | ~¥3.60 |

## 架构

```
PDF/EPUB/TXT → 提取 → 语义分块+重叠 → RAT翻译 → 一致性审计 → 去重叠组装 → TXT/MD/PDF
                  │                      │
            marker/fitz          DeepSeek/OpenAI
```

## 文件结构

```
book-translation/
├── desktop.py          ← 桌面 GUI（双击启动）
├── translate_book.py   ← CLI 入口
├── book-translation.vbs ← Windows 静默启动脚本
├── config.py           ← 配置管理
├── extractor.py        ← PDF/EPUB/TXT 提取
├── chunker.py          ← 句子级语义分块 + 重叠
├── translator.py       ← RAT 翻译引擎
├── assembler.py        ← 去重叠组装 + TXT/MD/PDF 输出
├── consistency.py      ← 术语一致性模型 + 审计报告
├── vector_store.py     ← ChromaDB 向量存储（RAT）
├── kg_builder.py       ← Agentic 预读 + 知识图谱
├── config.json         ← 用户配置（含 API Key）
├── input/              ← 原始文件
├── output/             ← 逐块译文
├── final/              ← 最终输出
├── cache/              ← 断点文件
└── models/             ← marker 模型缓存
```

## 与其他项目对比

| 特性 | Itranslation | bilingual_book_maker | Calibre 插件 |
|------|:---:|:---:|:---:|
| 桌面 GUI | ✅ | ❌ | ✅ |
| 句子级分块 | ✅ | ❌ | ❌ |
| 术语一致性追踪 | ✅ | ❌ | ❌ |
| 暂停/恢复 | ✅ | ❌ | ❌ |
| 实时成本显示 | ✅ | ❌ | ❌ |
| 双语输出 | ❌ | ✅ | ❌ |
| EPUB 输出 | ❌ | ✅ | ✅ |
| 成熟度 | v1.0 | 5年/9.3k⭐ | 3年/2.5k⭐ |

## 最低要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 包管理器
- DeepSeek API Key（[获取](https://platform.deepseek.com/)）
- Windows / macOS / Linux

## License

MIT

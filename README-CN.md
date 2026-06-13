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
<p align="center"><strong>AI 全书翻译工具 · 桌面 GUI + 命令行</strong></p>
<p align="center">
  PDF · EPUB · TXT · Markdown → 中文<br>
  句子级分块 · 术语一致性审计 · 暂停恢复 · 成本追踪
</p>

---

## 概述

Itranslation 是一个基于大语言模型的桌面翻译应用，支持将整本书籍从英文翻译为中文。输入 PDF、EPUB、TXT 或 Markdown 文件后，系统通过多阶段流水线处理——包括句子级语义分块、术语一致性审计和检索增强翻译（RAT）——最终输出 TXT、Markdown 或 PDF 格式的译文。

与按固定行数切割文本的工具不同，Itranslation 在句子级别进行分词，采用重叠分块和首次锁定去重策略，确保不会在句子中间断开。

---

## 核心差异

| 能力 | 业界通常做法 | Itranslation |
|---|---|---|
| 分块方式 | 每 N 行硬性切割 | 句子级分词 + 可配置重叠 |
| 术语一致性 | 依赖 LLM 跨调用记忆 | 增量追踪模型，自动检测术语漂移 |
| 翻译质量 | 单次翻译，无验证机制 | 重叠冗余 + 可配置间隔的实时审计 |
| 中断处理 | 重新开始 | GUI 暂停/恢复；CLI 与 GUI 均支持断点续传 |
| 成本可见性 | 结算时才知道 | 每块翻译后实时显示 token 消耗和费用（$/¥） |
| 模型灵活性 | 硬编码单一服务商 | 预设 DeepSeek 系列 + 自定义 OpenAI 兼容 API |

---

## 安装

### 前提条件

- **Python 3.11** 及以上 — [python.org](https://www.python.org/downloads/)
- **uv** 包管理器 — `pip install uv`
- **DeepSeek API Key** — [platform.deepseek.com](https://platform.deepseek.com/)（免费注册）

### 安装步骤

```bash
git clone https://github.com/Yisan0429/Itranslation.git
cd Itranslation
uv sync
```

核心依赖约 80 MB，10 秒内可完成安装。

### 可选功能

```bash
# Marker 视觉 PDF 提取（复杂排版精度 90%+，需下载约 1.4 GB 模型）
uv sync --extra vision

# RAT 检索增强翻译（ChromaDB + sentence-transformers，约 300 MB）
uv sync --extra rat
```

### 启动

```bash
# 桌面 GUI
uv run python desktop.py

# 命令行
uv run python translate_book.py book.pdf --genre literature --format pdf
```

Windows 用户可运行 `book-translation.vbs` 实现无终端窗口的静默启动。

---

## 功能

### 输入格式

| 格式 | 提取引擎 | 精度 | 说明 |
|---|---|---|---|
| **PDF** | PyMuPDF（默认） | 60–70% | 适用于标准单栏排版 |
| **PDF** | Marker（可选） | 90%+ | 多栏、表格等复杂排版；需下载模型 |
| **EPUB** | ebooklib | ~99% | 保留章节结构 |
| **TXT / MD** | 直接读取 | 100% | 无提取损耗 |

### 体裁适配

| 体裁 | 翻译策略 | 典型场景 |
|---|---|---|
| 文学 | 保留修辞、韵律与情感色彩，输出优雅现代汉语 | 小说、诗歌、散文 |
| 哲学 | 直译保真，维持逻辑结构，术语统一 | 学术哲学著作 |
| 自然科学 | 术语精确优先，数据、公式、单位原文保留 | 教材、研究论文 |
| 社会科学 | 直译兼顾可读性，引文格式保留 | 历史、社会学、经济学 |
| 技术 | 代码、命令、配置文件原文保持 | 技术文档、手册 |

### 输出格式

- **TXT** — 纯文本，体积最小
- **MD** — Markdown，保留标题层级和段落结构
- **PDF** — 排版输出，自动嵌入平台对应的 CJK 中文字体

### 翻译模型

| 模型 | 输入价格 | 输出价格 | 适用场景 |
|---|---|---|---|
| DeepSeek V4 Pro | $0.435 / 百万 token | $0.87 / 百万 token | 翻译质量最高 |
| DeepSeek V4 Flash | $0.14 / 百万 token | $0.28 / 百万 token | 高速、低成本 |
| 自定义 | — | — | 任何 OpenAI 兼容 API（Ollama、vLLM、Groq 等） |

### 并行翻译（v1.1）

章节级并行翻译，使用可配置的线程池。默认 4 个工作线程；可在 config 中设置 `parallel_workers: 0` 禁用，或通过 CLI `--parallel 0` 关闭。

### 断点续传（v1.1）

GUI 和 CLI 均在每章翻译完成后持久化进度。若翻译因网络中断、程序崩溃或用户取消而中止，重新启动同一文件时会弹窗询问是否从断点继续，并显示已完成章节列表。

---

## 架构

```
输入 (PDF / EPUB / TXT / MD)
  │
  ├─ Phase 0: 提取与预读
  │   └─ PyMuPDF 或 Marker → 文本清洗 → 可选知识图谱构建
  │
  ├─ Phase 1: 语义分块
  │   └─ 句子级分词 → 贪心打包 → 块间重叠（3–4 句）
  │
  ├─ Phase 2: 并行翻译
  │   └─ 逐块：术语注入 + 上下文 → LLM 调用 → 向量库存储
  │
  ├─ Phase 3: 质量审计
  │   └─ 一致性模型：每 N 块审计；术语一致性 < 80% 触发告警
  │
  └─ Phase 4: 组装输出
      └─ 去重叠（首次锁定策略）→ TXT / MD / PDF
```

### 核心设计

**句子级分块。** 输入文本先按句子拆分，再按可配置的 token 大小贪心打包。相邻块之间重叠 3–4 个句子。组装时，每句话仅保留首次出现的译文，后续重复版本丢弃。此举以约 5% 的 token 开销换取冗余纠错能力。

**增量一致性模型。** 每条术语翻译均记录原文词、译法和出处位置。每 20 块（可配置）自动审计全部术语，若某术语主译法占比低于 80% 阈值即触发告警，同时报告漂移术语和建议的统一译法。

**检索增强翻译（RAT）。** 已翻译段落通过 `all-MiniLM-L6-v2` 嵌入模型存入 ChromaDB 向量库。翻译新块时，系统检索语义最相近的历史翻译，作为参考上下文注入 LLM 提示词。

---

## 成本估算

基于 DeepSeek V4 Pro 官方定价与实测数据：

| 篇幅 | 字数 | 预估 Token | 预估耗时 | 预估费用 |
|---|---|---|---|---|
| 短篇 | 3,000 | ~5K 入 / 5K 出 | ~10 秒 | ~$0.01 (¥0.07) |
| 中篇 | 30,000 | ~50K 入 / 50K 出 | ~2 分钟 | ~$0.07 (¥0.50) |
| 长篇 | 100,000 | ~150K 入 / 140K 出 | ~7 分钟 | ~$0.20 (¥1.44) |
| 巨著 | 300,000 | ~450K 入 / 420K 出 | ~20 分钟 | ~$0.60 (¥4.32) |

实测：1,196 词文学作品 → 2 个分块 → 10 秒完成，费用 $0.0076（¥0.06）。

DeepSeek 系列模型自动计算费用；自定义模型仅显示 token 数量，不显示金额，避免误导。

---

## CLI 参考

```bash
# 基础用法
uv run python translate_book.py book.pdf

# 指定体裁与输出格式
uv run python translate_book.py book.pdf --genre philosophy --format pdf

# 快速模式（跳过预读与 RAT）
uv run python translate_book.py book.pdf --no-preread --no-rat

# 并行翻译 + 自定义输出
uv run python translate_book.py book.pdf \
  --genre literature \
  --format md \
  --model deepseek-v4-flash \
  --parallel 4 \
  --output final/translation
```

---

## 项目结构

```
Itranslation/
├── desktop.py            桌面 GUI（tkinter，高 DPI 支持）
├── translate_book.py     CLI 入口
├── extractor.py          PDF/EPUB/TXT/MD 文本提取
├── chunker.py            句子级语义分块与重叠
├── translator.py         翻译引擎（RAT + 术语注入）
├── assembler.py          去重叠组装 + TXT/MD/PDF 输出
├── consistency.py        增量术语一致性模型与审计报告
├── vector_store.py       ChromaDB 向量存储
├── kg_builder.py         Agentic 预读与知识图谱构建
├── config.py             全局配置（DEFAULT_CONFIG + config.json）
├── env_check.py          可选功能就绪检测器
├── input/                源文件目录
├── final/                成品输出目录
├── cache/                断点文件（JSON）
└── models/               模型缓存（Marker、sentence-transformers）
```

---

## 竞品对比

### Top 5 开源项目（按 GitHub 星标排序）

| # | 项目 | Stars | 定位 | 优势 | 局限 |
|---|------|-------|------|------|------|
| 1 | [Immersive Translate](https://github.com/immersive-translate/immersive-translate) | 17.8k | 浏览器扩展（网页/PDF/EPUB） | 平台覆盖广；100+ 语言；实时双语 | 需安装扩展；非独立翻译工具；Pro 收费 |
| 2 | [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) | 9.3k | CLI 电子书翻译 | 生态成熟（5 年）；双语输出；40+ 模型 | 无 GUI；固定行数分块；无术语审计 |
| 3 | [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin) | 2.5k | Calibre 插件 | 48 种输入格式；20 种输出；多引擎 | 依赖 Calibre；上手门槛较高 |
| 4 | [ebook-GPT-translator](https://github.com/jesselau76/ebook-GPT-translator) | 1.7k | CLI 电子书翻译 | 多格式支持；现代化 v2 架构；SQLite 缓存 | 仅 CLI；无翻译质量审计 |
| 5 | [epub-translator](https://github.com/oomol-lab/epub-translator) | 771 | EPUB 双语翻译库 | 保留原始格式；API 接口规范 | 仅 EPUB；生态尚新 |

### 功能维度对比

| 维度 | Itranslation v1.1 | bilingual_book_maker | Calibre 插件 | ebook-GPT-translator | epub-translator |
|:---|:---:|:---:|:---:|:---:|:---:|
| 桌面 GUI | ✓ | — | ✓（需 Calibre） | — | — |
| 断点续传 | ✓（GUI+CLI） | ✓ | ✓ | ✓ | — |
| 并行翻译 | ✓（章节级） | ✓（API 批量） | ✓（多书并行） | — | ✓ |
| 句子级分块 | ✓ | — | — | — | — |
| 重叠冗余 | ✓ | — | — | — | — |
| 术语一致性 | ✓（实时审计） | 部分支持 | — | — | — |
| 体裁适配 | ✓（5 种预设） | 部分支持 | — | 部分支持 | — |
| 知识图谱预读 | ✓ | — | — | — | — |
| RAG 增强翻译 | ✓（ChromaDB） | — | — | — | — |
| 成本追踪 | ✓（$/¥ 实时） | — | — | — | ✓ |
| 双语输出 | — | ✓ | — | — | ✓ |
| 输出格式 | TXT / MD / PDF | 双语 EPUB / TXT | 20 种 | EPUB / TXT | EPUB |
| 模型支持 | DeepSeek + 自定义 | 40+（liteLLM） | 多引擎 | OpenAI 系列 | OpenAI / Claude |
| 成熟度 | v1.1（2026） | 5 年 | 3 年 | v2（2025） | v0.1（2025） |

### 差异化优势

1. **翻译质量闭环。** 句子级分块、重叠冗余、实时术语审计三者形成"翻译→验证→纠偏"的完整质量闭环。在所有可比较的开源项目中，没有任何一个同时具备这三项能力。
2. **桌面 GUI 零门槛。** 对比范围内唯一同时提供原生桌面界面和命令行的独立翻译工具——无需安装 Calibre 等外部平台，非技术用户可直接使用。
3. **成本透明可控。** token 消耗和预估费用（美元/人民币双币种）实时更新。自定义模型明确标注"费用未知"，不显示错误定价。

### 已知不足

1. **暂无双语对照输出。** bilingual_book_maker 和 epub-translator 的核心卖点，属高频需求。
2. **生态尚处早期。** v1.1 对比竞品数年迭代和社区积累，在成熟度上存在客观差距。
3. **输入格式有限。** 目前支持 4 种格式，而 Calibre 插件支持 48 种。

---

## 常见问题

**翻译中途网络断了怎么办？**

GUI 与 CLI 均在每章完成后保存进度。中断后重新翻译同一文件，系统会自动检测 checkpoint 并询问是否从断点继续。

**扫描版 PDF 能翻译吗？**

可以，使用 Marker 视觉提取引擎。在 GUI 中将 PDF 提取方式选为"marker（视觉，90%+ 精度）"。首次使用会自动下载约 2 GB 模型文件。

**能否使用自己的模型服务？**

在模型下拉框选择「自定义...」，点击齿轮图标（⚙），填写 API Base URL、Model Name 和 API Key。支持 Ollama、vLLM、Groq 等任何 OpenAI 兼容接口。

**如何检测可选功能是否就绪？**

```bash
uv run python env_check.py
```

该脚本会检测 Marker 和 RAT 可选功能是否完整安装并可用。

---

## License

MIT © 2026

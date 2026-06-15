<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/version-1.3.1-536DFE" alt="Version">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20V4-536DFE?logo=deepseek" alt="DeepSeek">
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README-CN.md">简体中文</a>
</p>

<h1 align="center">Itranslation</h1>
<p align="center"><strong>AI 全书翻译工具 · CLI + 桌面 GUI</strong></p>
<p align="center">
  PDF · EPUB · TXT · Markdown → 中文<br>
  句子级分块 · 重叠冗余 · RAT · KG 预读 · Reflection · 术语一致性审计 · 断点续传 · 成本追踪
</p>

> 项目尚在积极开发中。建议先用短文本（< 3000 词）测试，确认翻译质量与费用符合预期后再处理大文件。翻译中途可能因网络波动或 API 异常中断。

---

## 概述

Itranslation 是一个基于大语言模型的桌面翻译应用，支持将整本书籍从英文翻译为中文。输入 PDF、EPUB、TXT 或 Markdown 文件后，系统通过多阶段流水线处理——包括句子级语义分块、检索增强翻译（RAT）、Agentic 知识图谱预读、术语一致性审计和可选的 Reflection 反思工作流——最终输出 TXT、Markdown、PDF 或 EPUB 格式的译文。

---

## 核心差异

| 能力 | 业界通常做法 | Itranslation |
|---|---|---|
| 分块方式 | 每 N 行硬性切割 | 句子级分词 + 可配置重叠 |
| 术语一致性 | 依赖 LLM 跨调用记忆 | 增量追踪模型，自动检测术语漂移 |
| 翻译质量 | 单次翻译，无验证机制 | 重叠冗余 + RAT + KG 预读 + 可配置间隔的实时审计 |
| 译后 QA | 直接输出 | Reflection 反思工作流：LLM 自审 → 修订（翻译 → 反思 → 改进） |
| 中断处理 | 重新开始 | GUI 暂停/恢复；CLI 与 GUI 均支持断点续传 |
| 成本可见性 | 结算时才知道 | 每块翻译后实时显示 token 消耗和费用（$/¥） |
| 模型灵活性 | 硬编码单一服务商 | 5 大平台 via liteLLM（DeepSeek、OpenAI、Anthropic、Google、Mimo）+ 自定义 API |
| 质量基准测试 | 无 | 内置 BLEU/chrF 评分 + LLM-as-Judge 评估套件 |

---

## 安装

### 前提条件

- Python 3.11 及以上 — [python.org](https://www.python.org/downloads/)
- uv 包管理器 — `pip install uv`
- DeepSeek API Key — [platform.deepseek.com](https://platform.deepseek.com/)（免费注册）

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

---

## 功能

### 输入格式

| 格式 | 提取引擎 | 精度 | 说明 |
|---|---|---|---|
| PDF | PyMuPDF（默认） | 60–70% | 适用于标准单栏排版 |
| PDF | Marker（可选） | 90%+ | 多栏、表格等复杂排版；需下载模型 |
| EPUB | ebooklib | ~99% | 保留章节结构 |
| TXT / MD | 直接读取 | 100% | 无提取损耗 |

### 体裁适配

| 体裁 | 翻译策略 | 典型场景 |
|---|---|---|
| 文学 | 保留修辞、韵律与情感色彩，输出优雅现代汉语 | 小说、诗歌、散文 |
| 哲学 | 直译保真，维持逻辑结构，术语统一 | 学术哲学著作 |
| 自然科学 | 术语精确优先，数据、公式、单位原文保留 | 教材、研究论文 |
| 社会科学 | 直译兼顾可读性，引文格式保留 | 历史、社会学、经济学 |
| 技术 | 代码、命令、配置文件原文保持 | 技术文档、手册 |

### 输出格式

- TXT — 纯文本，体积最小
- MD — Markdown，保留标题层级和段落结构
- PDF — 排版输出，自动嵌入平台对应的 CJK 中文字体
- EPUB — 标准电子书格式，含章节目录导航

### 翻译模型

| 平台 | 模型 | 输入价格 | 输出价格 | 适用场景 |
|---|---|---|---|---|
| DeepSeek | V4 Pro / V4 Flash | $0.14–0.435 | $0.28–0.87 | 最优性价比 |
| OpenAI | GPT-5.5 / GPT-5.5 Mini | $1.50–5.00 | $6.00–15.00 | 通用质量最高 |
| Anthropic | Opus 4.8 / Sonnet 4.6 / Fable 5 | $3.00–10.00 | $15.00–50.00 | 文学翻译见长；复杂推理 |
| Google | Gemini 3.5 Pro / 3.5 Flash | $0.30–3.50 | $1.50–10.50 | 长文档处理；速度优先 |
| Mimo | MiMo-V2.5-Pro / MiMo-V2.5-Omni | $0.40–1.20 | $1.60–4.80 | 多模态理解 |
| 自定义 | — | — | — | 任何 OpenAI 兼容 API |

### Reflection 反思工作流

启用后每个翻译块将经过额外的质量循环：

1. 翻译 — LLM 初始翻译
2. 反思 — LLM 对照原文审查译文，识别准确性、流畅性、术语和风格方面的问题
3. 修订 — LLM 根据反思反馈重新翻译

这会增加约 2 倍的 token 消耗，但显著提升翻译质量，尤其适用于文学和哲学类文本。CLI 通过 `--reflect` 启用，GUI 通过 Reflection 开关控制。

### 并行翻译

章节级并行翻译，使用可配置的线程池。默认 4 个工作线程；可在 config 中设置 `parallel_workers: 0` 禁用，或通过 CLI `--parallel 0` 关闭。

### 断点续传

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
  ├─ Phase 2: 并行翻译 + Reflection
  │   └─ 逐块：术语注入 + 上下文 → LLM 调用 → 反思 → 修订 → 向量库存储
  │
  ├─ Phase 3: 质量审计
  │   └─ 一致性模型：每 N 块审计；术语一致性 < 80% 触发告警
  │
  └─ Phase 4: 组装输出
      └─ 去重叠（首次锁定策略）→ TXT / MD / PDF / EPUB
```

### 核心设计

句子级分块。输入文本先按句子拆分，再按可配置的 token 大小贪心打包。相邻块之间重叠 3–4 个句子。组装时，每句话仅保留首次出现的译文，后续重复版本丢弃。此举以约 5% 的 token 开销换取冗余纠错能力。

增量一致性模型。每条术语翻译均记录原文词、译法和出处位置。每 20 块（可配置）自动审计全部术语，若某术语主译法占比低于 80% 阈值即触发告警，同时报告漂移术语和建议的统一译法。

检索增强翻译（RAT）。已翻译段落通过 `all-MiniLM-L6-v2` 嵌入模型存入 ChromaDB 向量库。翻译新块时，系统检索语义最相近的历史翻译，作为参考上下文注入 LLM 提示词。

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

# 使用 GPT-5.5（liteLLM） + Reflection
uv run python translate_book.py book.pdf \
  --provider litellm \
  --model openai/gpt-5.5 \
  --reflect \
  --format pdf
```

---

## 项目结构

```
Itranslation/
├── translate_book.py     CLI 入口
├── desktop.py            NiceGUI 桌面应用
├── Itranslation-cli.spec PyInstaller 构建配置
├── src/
│   ├── extractor.py      PDF/EPUB/TXT/MD 文本提取
│   ├── kg_builder.py     Agentic 预读与知识图谱构建
│   ├── chunker.py        句子级语义分块与重叠
│   ├── translator.py     翻译引擎（RAT + 术语注入 + Reflection）
│   ├── consistency.py    增量术语一致性模型与审计报告
│   ├── assembler.py      去重叠组装 + TXT/MD/PDF/EPUB 输出
│   ├── vector_store.py   ChromaDB 向量存储
│   ├── format_protector.py  代码/公式/URL 占位符保护
│   ├── api_client.py     统一 API 客户端（HTTP + liteLLM）
│   ├── benchmark.py       BLEU/chrF + LLM-as-Judge 质量评估
│   ├── config.py         全局配置（DEFAULT_CONFIG + config.json）
│   ├── env_check.py      可选功能就绪检测器
│   └── eval.py           组件评估套件
├── input/                源文件目录
├── output/               翻译成品（每本书一个子文件夹）
├── reports/              审计报告 + benchmark 结果
├── cache/                断点文件（JSON）
└── models/               模型缓存（Marker、sentence-transformers）
```

---

## 竞品对比

### Top 5 开源项目（按 GitHub 星标排序）

| # | 项目 | Stars | 定位 | 优势 | 局限 |
|---|------|-------|------|------|------|
| 1 | [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) | 9.3k | CLI 电子书翻译 | 生态成熟（5 年）；双语输出；40+ 模型 | 无 GUI；固定行数分块；无术语审计 |
| 2 | [Translation Agent](https://github.com/andrewyng/translation-agent) | 5.8k | Agentic 翻译演示 | Reflection 工作流开创者；高度可定制；MIT 协议 | 实验性项目；无书籍专项功能；无 GUI |
| 3 | [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin) | 2.5k | Calibre 插件 | 48 种输入格式；20 种输出；多引擎 | 依赖 Calibre；上手门槛较高 |
| 4 | [ebook-GPT-translator](https://github.com/jesselau76/ebook-GPT-translator) | 1.7k | CLI 电子书翻译 | 多格式支持；现代化 v2 架构；SQLite 缓存 | 仅 CLI；无翻译质量审计 |
| 5 | [TranslateBooksWithLLMs](https://github.com/hydropix/TranslateBooksWithLLMs) | 450 | 桌面应用（Web UI） | 预编译可执行文件（Win/Mac）；格式保留；Docker | 无句子级分块；无 RAT；无术语审计 |

### 功能维度对比

| 维度 | Itranslation | bilingual_book_maker | Calibre 插件 | ebook-GPT-translator | Translation Agent | TranslateBooksWithLLMs |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| 桌面 GUI | ✓（NiceGUI） | — | ✓（需 Calibre） | — | — | ✓（Web） |
| 断点续传 | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| 并行翻译 | ✓ | ✓（API 批量） | ✓（多书并行） | — | — | ✓ |
| 句子级分块 | ✓ | — | — | — | — | — |
| 重叠冗余 | ✓ | — | — | — | — | — |
| 术语一致性 | ✓ | 部分支持 | — | — | — | — |
| 体裁适配 | ✓（5 种预设） | 部分支持 | — | 部分支持 | — | — |
| 知识图谱预读 | ✓ | — | — | — | — | — |
| RAT 增强翻译 | ✓（ChromaDB） | — | — | — | — | — |
| Reflection 工作流 | ✓ | — | — | — | ✓ | — |
| 格式保护 | ✓ | — | — | — | — | — |
| 成本追踪 | ✓（$/¥） | — | — | — | — | ✓ |
| 多平台 liteLLM | ✓（5 平台） | ✓（40+ 模型） | 多引擎 | OpenAI 系列 | OpenAI | 多平台 |
| 双语输出 | — | ✓ | — | — | — | — |
| Benchmark 套件 | ✓ | — | — | — | — | ✓ |
| 输出格式 | TXT / MD / PDF / EPUB | 双语 EPUB / TXT | 20 种 | EPUB / TXT | TXT | TXT / EPUB / SRT |
| 模型支持 | DeepSeek + liteLLM | 40+（liteLLM） | 多引擎 | OpenAI 系列 | GPT-5.5 | Ollama, OpenAI, Gemini |
| 成熟度 | v1.3（2026） | 5 年 | 3 年 | v2（2025） | 研究阶段（2025） | 活跃（2026） |

### 差异化优势

1. 最全面的开源翻译质量管线。句子级分块、重叠冗余、RAT 检索、KG 预读和实时术语审计形成完整质量闭环，所有竞品均不同时具备。Reflection 反思工作流融入前沿 Agentic 翻译研究成果，实现翻译 → 反思 → 修订循环。
2. 多平台模型生态。liteLLM 集成提供 5 大平台（DeepSeek、OpenAI、Anthropic、Google、Mimo）模型的统一接口，同时保留 DeepSeek 直连 HTTP 通道。
3. 内置质量基准测试。benchmark 套件提供 BLEU/chrF 自动评分和 LLM-as-Judge 四维质量评估。
4. 成本透明可控。token 消耗和预估费用（美元/人民币双币种）实时更新。自定义模型明确标注，不显示错误定价。
5. API 内置重试。所有 LLM API 调用均内置指数退避重试机制（可通过 config.json 配置），确保网络波动时的稳定性。

---

## 常见问题

翻译中途网络断了怎么办？

CLI 在每章完成后保存进度。中断后重新翻译同一文件，系统会自动检测 checkpoint 并询问是否从断点继续。

扫描版 PDF 能翻译吗？

可以，使用 Marker 视觉提取引擎。首次使用会自动下载约 2 GB 模型文件。

能否使用自己的模型服务？

通过 `--provider litellm --model <model-id>` 使用 liteLLM，或 `--provider custom --api-base <url>` 配置任何 OpenAI 兼容 API（Ollama、vLLM、Groq 等）。

如何检测可选功能是否就绪？

```bash
uv run python src/env_check.py
```

该脚本会检测 Marker 和 RAT 可选功能是否完整安装并可用。

---

## License

MIT © 2026

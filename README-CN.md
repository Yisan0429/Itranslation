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
<p align="center"><strong>AI 全书翻译工具 · CLI + 桌面 GUI</strong></p>
<p align="center">
  PDF · EPUB · TXT · Markdown → 中文<br>
  句子级分块 · 重叠冗余 · RAT · KG 预读 · Reflection · 术语一致性审计 · 断点续传 · 成本追踪
</p>

> 项目尚在积极开发中。建议先用短文本（< 3000 词）测试，确认翻译质量与费用符合预期后再处理大文件。翻译中途可能因网络波动或 API 异常中断。

---

## 概述

Itranslation 是一个基于大语言模型的桌面翻译应用，支持将整本书籍从英文翻译为中文。输入 PDF、EPUB、TXT 或 Markdown 文件后，系统通过多阶段流水线处理——包括句子级语义分块、检索增强翻译（RAT）、Agentic 知识图谱预读、术语一致性审计和可选的 Reflection 反思工作流——最终输出 TXT、Markdown、PDF 或 EPUB 格式的译文。

> **知识应该自由流动。** 我们鼓励所有用户将翻译完成的书籍公开发布——上传至 [Internet Archive](https://archive.org)、[GitHub](https://github.com)、个人博客或任何开放平台。每一本译作，都在拆除读者与知识之间的一道语言隔墙。

---

## 核心差异

| 能力 | 常见做法 | Itranslation |
|---|---|---|
| 分块方式 | 每 N 行硬性切割 | 句子级分词 + 可配置重叠 |
| 术语一致性 | 依赖 LLM 跨调用记忆 | 增量跟踪模型 + 漂移自动告警 |
| 翻译质量 | 单次翻译，无验证 | 重叠冗余 + RAT + KG 预读 + 实时审计 |
| 译后质检 | 直接输出 | Reflection 反思工作流（翻译 → 反思 → 修订） |
| 中断处理 | 从头重来 | 断点续传（GUI 与 CLI） |
| 成本可见性 | 账单出来才知道 | 逐块 token 与费用实时显示 |

---

## 安装

前置条件：Python 3.11+、[uv](https://docs.astral.sh/uv/)、[DeepSeek API Key](https://platform.deepseek.com/)。

```bash
git clone https://github.com/Yisan0429/Itranslation.git
cd Itranslation
uv sync
```

可选扩展：

```bash
uv sync --extra vision  # Marker 视觉 PDF 提取（模型约 1.4 GB）
uv sync --extra rat     # 检索增强翻译（约 300 MB）
```

启动：

```bash
uv run python desktop.py                                                       # 桌面 GUI
uv run python translate_book.py book.pdf --genre literature --format pdf     # 命令行
```

## API 配置

从模板创建配置：`cp config.example.json config.json`，填入密钥即可。配置优先级（从高到低）：CLI 参数 > GUI 输入框 > config.json > 环境变量。

### 两种提供商模式

| 模式 | provider 值 | 模型格式 | API Key 来源 |
|---|---|---|---|
| Custom（OpenAI 兼容接口） | `custom` | 任意，如 `deepseek-v4-pro` | 环境变量 `DEEPSEEK_API_KEY`、config.json 或 GUI/CLI |
| liteLLM（100+ 模型） | `litellm` | `openai/gpt-5.5`、`anthropic/claude-sonnet-4-6`、`gemini/gemini-3.5-pro` | 环境变量 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`，或显式传入 |

### config.json 示例

DeepSeek（默认）：

```json
{
    "api_key": "sk-...",
    "model": "deepseek-v4-pro",
    "api_base": "https://api.deepseek.com/v1"
}
```

OpenAI（经 liteLLM）：

```json
{
    "provider": "litellm",
    "model": "openai/gpt-5.5"
}
```

任意 OpenAI 兼容接口：

```json
{
    "provider": "custom",
    "api_key": "sk-...",
    "api_base": "https://your-endpoint.example.com/v1",
    "model": "your-model-name"
}
```

### 三档模型

默认 `use_tiered_models` 为 `true`，管线使用三档模型（`llm_tiers.strong` 用于翻译、`cheap` 用于审计、`fast` 用于预读），默认全部指向 DeepSeek。切换提供商时，需同步修改 `llm_tiers`，或设置 `"use_tiered_models": false` 以全程使用单一 `model`。

### CLI

```bash
uv run python translate_book.py book.txt --provider deepseek --model deepseek-v4-pro     --api-key sk-xxx --api-base https://api.deepseek.com/v1
```

### GUI

在左侧面板填写 Provider / 模型 / API Key / API Base，仅在当前会话生效，不持久化。

---

## 功能特性

### 输入格式

| 格式 | 引擎 | 说明 |
|---|---|---|
| PDF | PyMuPDF（默认）/ Marker（可选） | Marker 支持多栏排版与表格 |
| EPUB | ebooklib | 保留章节目录结构 |
| TXT / MD | 直接读取 | 无提取开销 |

### 体裁感知翻译

五种预设（文学 / 哲学 / 自然科学 / 社会科学 / 技术）分别调整语气、术语处理与格式保护规则。

### 输出格式

TXT、Markdown、PDF（内嵌 CJK 字体）、EPUB（章节目录导航）。

### Reflection 反思工作流

可选的"翻译 → 反思 → 修订"循环；约 2 倍 token 消耗换取文学与哲学文本的更高质量。通过 `--reflect` 或 GUI 开关启用。

### 并行翻译

多章节线程池并发翻译（默认 4 线程；`parallel_workers: 0` 关闭）。

### 断点续传

每块翻译完成后保存进度。中断后重跑自动续传：已完成块跳过、失败块自动重译。checkpoint 按「书名 slug + 章节索引」命名，不同书籍互不冲突。

### 质量审计

翻译完成后自动运行缺陷族扫描（10 组正则：被字句滥用、长定语、硬译句式、名词化等），按 P1/P2/P3 分级标注候选，零 API 开销；增量一致性模型在任一术语主导译法低于 80% 时告警。

### RAT（检索增强翻译）

已翻译段落存入 ChromaDB 向量库（all-MiniLM-L6-v2 嵌入），翻译新块时检索相似段落作为参考上下文，提升风格与术语一致性。依赖缺失时翻译继续但无检索增强，并给出显式警告。

---

## 架构

```
输入（PDF / EPUB / TXT / MD）
  │
  ├─ Phase 0: 提取与预读 — PyMuPDF 或 Marker → 文本清洗 → 可选知识图谱构建
  ├─ Phase 1: 语义分块 — 句子级分词 → 贪心打包 → 块间重叠（3–4 句）
  ├─ Phase 2: 并行翻译 + Reflection — 逐块：术语注入 + RAT 上下文 → LLM → 向量库存储
  ├─ Phase 3: 质量审计 — 缺陷族扫描（10 组正则）+ 一致性模型审计
  └─ Phase 4: 组装输出 — 按句对齐 body_join（旧 checkpoint 回退 first_lock）→ 输出
```

## CLI 参考

```bash
uv run python translate_book.py book.pdf                            # 基本用法
uv run python translate_book.py book.pdf --genre philosophy --format pdf
uv run python translate_book.py book.pdf --no-preread --no-rat      # 快速模式
uv run python translate_book.py book.pdf --parallel 4 --output out/
uv run python translate_book.py book.pdf --provider litellm --model openai/gpt-5.5 --reflect
```

---

## 项目结构

```
Itranslation/
├── translate_book.py     CLI 入口（薄参数解析层）
├── desktop.py            NiceGUI 桌面应用（仅 UI 层）
├── Itranslation-cli.spec PyInstaller 构建配置
├── src/
│   ├── pipeline.py       统一翻译管线（CLI 与 GUI 共用）
│   ├── extractor.py      PDF/EPUB/TXT/MD 文本提取
│   ├── kg_builder.py     Agentic 预读与知识图谱构建
│   ├── chunker.py        句子级分块（上下文重叠句显式标注）
│   ├── translator.py     翻译引擎（RAT + 术语注入 + Reflection + 块级进度回调）
│   ├── consistency.py    增量术语一致性模型
│   ├── assembler.py      按句对齐组装（body_join + first_lock）
│   ├── vector_store.py   RAT 的 ChromaDB 向量库
│   ├── format_protector.py  代码/公式/URL 占位符保护
│   ├── api_client.py     统一 API 客户端（HTTP + liteLLM）
│   ├── auditor.py        低 token 缺陷族扫描引擎
│   ├── defects.py        缺陷族注册表（10 族）
│   ├── benchmark.py      BLEU/chrF + LLM-as-Judge 质量评估
│   ├── config.py         配置（DEFAULT_CONFIG + config.json）
│   ├── env_check.py      可选功能就绪检查
│   └── eval.py           组件评估套件
├── tests/                单元测试（chunker / assembler / checkpoint / defects / format protector）
├── input/                源文档
├── output/               译文（每本书一个目录）
├── reports/              审计报告与基准结果
├── cache/                checkpoint 文件（JSON，按书名 slug + 章节索引命名）
└── models/               模型缓存（Marker、sentence-transformers）
```

---

## 致谢

Itranslation 的设计和实现受以下项目的启发，这些项目在多个开发阶段中被深入研究：

| 项目 | 借鉴之处 |
|:---|:---|
| [LifeBook](https://github.com/SaberOnGo/public-domain-books-translation) | 问题族分类、低 token 审计、逐章质量门禁、分层随机抽检（v1.3.3） |
| [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) | 双语 EPUB 输出、滑动窗口上下文、分隔符批处理、多 Key 轮换（v1.0 基础） |
| [Translation Agent](https://github.com/andrewyng/translation-agent) | Reflection 反思工作流（翻译→反思→改进）、Agentic 翻译架构（v1.3.0） |
| [TranslateBooksWithLLMs](https://github.com/hydropix/TranslateBooksWithLLMs) | 预编译可执行文件、格式保留 EPUB 翻译、Docker 部署（v1.3.1） |
| [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin) | MD5 内容缓存、48 输入/20 输出格式、多引擎设计（v1.0 研究） |
| [ebook-GPT-translator](https://github.com/jesselau76/ebook-GPT-translator) | 多格式输入支持、SQLite 断点缓存（v1.0 研究） |
| [pdf-translate](https://github.com/withmargin/pdf-translate) | 非叙事文本逐页隔离、内容流操作保留排版（v1.0 研究） |
| [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate) | 自托管 API 设计、Google Translate 格式兼容（v1.0 研究） |
| [Argos Translate](https://github.com/argosopentech/argos-translate) | 离线 NMT 能力、语言对模型架构（v1.0 研究） |
| [Opus-MT](https://github.com/Helsinki-NLP/Opus-MT) | 开源神经 MT 模型、Marian NMT 框架、1000+ 语言对（v1.0 研究） |
| [EasyNMT](https://github.com/UKPLab/EasyNMT) | 多 MT 引擎统一接口（v1.0 研究） |
| [translate-shell](https://github.com/soimort/translate-shell) | CLI 优先翻译体验、多提供商抽象（v1.0 研究） |
| [sacrebleu](https://github.com/mjpost/sacrebleu) | 中文翻译 BLEU/chrF 评估指标（v1.3.0） |
| [liteLLM](https://github.com/BerriAI/litellm) | 100+ LLM 提供商统一 API 接口（v1.3.0） |
| [NiceGUI](https://github.com/zauberzeug/nicegui) | 桌面 GUI 框架（浏览器 + 原生窗口）（v1.2.0） |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | Windows 独立可执行文件打包（v1.3.1） |

---

## License

MIT © 2026

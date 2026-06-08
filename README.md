<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20V4-536DFE?logo=deepseek" alt="DeepSeek">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

<h1 align="center">Itranslation</h1>
<p align="center"><strong>AI 全书翻译 · 一行命令翻完一本书</strong></p>
<p align="center">PDF / EPUB / TXT / Markdown → 中文 · 桌面 GUI + 命令行 · 暂停恢复 · 术语一致性审计 · 实时成本</p>

---

## 为什么选 Itranslation

大多数翻译工具能做到"把文字从 A 语言变成 B 语言"。但这不够——翻开一本 300 页的书，你需要的是：

| 你需要 | 别人的做法 | Itranslation |
|--------|-----------|-------------|
| 不切碎句子 | 每 10 行一刀切 | 句子级分词 + 重叠冗余 |
| 术语不前后矛盾 | 靠 LLM 自觉 | 实时追踪 200+ 术语，<80% 自动报警 |
| 翻到一半想停 | 只能等它跑完 | 随时 ⏸ 暂停，随时 ▶ 继续 |
| 知道花了多少钱 | 不知道 | 每块翻完立刻显示 $/¥ |
| 换模型 | 写死在代码里 | 下拉框切换，自定义 ⚙ 填 URL |

## 快速开始

### 前提

- **Python 3.11+** — [下载](https://www.python.org/downloads/)
- **uv** 包管理器 — `pip install uv`
- **DeepSeek API Key** — [免费注册](https://platform.deepseek.com/)

### 安装

```bash
git clone https://github.com/Yisan0429/Itranslation.git
cd Itranslation
uv sync
```

### 启动

```bash
# 桌面 GUI（推荐）
uv run python desktop.py

# 命令行
uv run python translate_book.py book.pdf --genre literature
```

> Windows 用户：运行 `book-translation.vbs` 可直接启动 GUI，无终端窗口。

---

## 功能

### 输入

| 格式 | 引擎 | 精度 | 适用 |
|------|------|------|------|
| **PDF** | PyMuPDF 文本层 | 60-70% | 普通排版 PDF |
| **PDF** | marker 视觉 | 90%+ | 复杂排版、双栏、表格 |
| **EPUB** | ebooklib | ~99% | 电子书 |
| **TXT / MD** | 直接读取 | 100% | 纯文本 |

### 体裁

| 体裁 | 翻译策略 | 典型场景 |
|------|---------|---------|
| **文学** | 保留修辞、韵律、情感色彩，优雅现代汉语 | 小说、散文、诗歌 |
| **哲学** | 直译保真，长句不拆分，术语统一 | 康德、海德格尔 |
| **自然科学** | 术语精确优先，数据/公式/单位不变 | 论文、教科书 |
| **社会科学** | 直译兼可读，引文格式保留 | 历史、社会学 |
| **技术** | 代码/命令/配置原样保留 | 技术文档 |

### 翻译模型

| 模型 | 输入价格 | 输出价格 | 适用 |
|------|---------|---------|------|
| DeepSeek V4 Pro | $0.435 / 1M tokens | $0.87 / 1M tokens | 文学翻译，质量最高 |
| DeepSeek V4 Flash | $0.14 / 1M tokens | $0.28 / 1M tokens | 快速低成本，技术文档够用 |
| 自定义 | — | — | 任何 OpenAI 兼容 API |

### 输出

- **TXT** — 纯文本，无格式，最小体积
- **MD** — Markdown，保留标题 `#` 层级和段落结构
- **PDF** — 排版 PDF，自动嵌入微软雅黑中文字体

---

## 架构

```
输入 (PDF/EPUB/TXT/MD)
  │
  ├─ Phase 0: 提取 + 体裁检测
  │   └─ PyMuPDF / marker → 清洗 → 自动识别文学/哲学/科学
  │
  ├─ Phase 1: 语义分块 + 重叠
  │   └─ 句子级分词 → 贪心打包 → 重叠 3-4 句（冗余纠错）
  │
  ├─ Phase 2: 翻译
  │   └─ 每块: 术语注入 + 重叠上下文 → LLM → 向量存储
  │
  ├─ Phase 3: 质量审计
  │   └─ 术语一致性模型：每 20 块审计，<80% 报警
  │
  └─ Phase 4: 组装
      └─ 去重叠（首次锁定策略）→ TXT / MD / PDF
```

### 关键设计

**语义分块：** 不是机械地每 N 行一刀，而是先把文本拆成句子，再贪心打包。块之间有 3-4 句重叠——同一句话在两个块里各有一份翻译，组装时取首次出现的版本。

**术语一致性：** 每翻译一个术语就记录：哪个词 → 译成了什么 → 在第几段。每 20 块自动审计全部术语，发现同一个词有两种不同译法就报警。

---

## 成本

基于 DeepSeek V4 Pro 官方定价和实测数据：

| 书的规模 | 字数 | tokens | 耗时 | 费用 |
|---------|------|--------|------|------|
| 短篇 | 3,000 | ~5K in / 5K out | ~10 秒 | $0.01 (~¥0.07) |
| 中篇 | 30,000 | ~50K in / 50K out | ~2 分钟 | $0.07 (~¥0.50) |
| 长篇 | 100,000 | ~150K in / 140K out | ~7 分钟 | $0.20 (~¥1.44) |
| 巨著 | 300,000 | ~450K in / 420K out | ~20 分钟 | $0.60 (~¥4.32) |

> 实测：1196 词文学作品 → 2 块 → **$0.0076 (~¥0.06)** → 用时 10 秒。

---

## 命令行

```bash
# 基础
uv run python translate_book.py book.pdf

# 指定体裁 + PDF 输出
uv run python translate_book.py book.pdf --genre philosophy --format pdf

# 快速模式（跳过预读和 RAT）
uv run python translate_book.py book.pdf --no-preread --no-rat

# 完整参数
uv run python translate_book.py book.pdf \
  --genre literature \
  --format md \
  --model deepseek-v4-flash \
  --target-tokens 1500 \
  --overlap 3 \
  --output final/result
```

---

## 项目结构

```
Itranslation/
├── desktop.py          桌面 GUI（双击启动）
├── translate_book.py   CLI 入口
├── extractor.py        PDF/EPUB/TXT/MD 提取
├── chunker.py          句子级语义分块 + 层叠重叠
├── translator.py       RAT 翻译引擎（术语注入 + 上下文）
├── assembler.py        去重叠组装 + TXT/MD/PDF 输出
├── consistency.py      增量术语一致性模型 + 审计报告
├── vector_store.py     ChromaDB 向量存储
├── kg_builder.py       Agentic 预读 + 知识图谱构建
├── config.py           全局配置管理
├── input/              原始书籍文件
├── output/             逐块中间译文
├── final/              最终输出文件
├── cache/              JSON 断点文件
└── models/             marker 视觉模型缓存
```

---

## 与同类项目对比

| | Itranslation | [bilingual_book_maker](https://github.com/yihong0618/bilingual_book_maker) ⭐9.3k | [Calibre 插件](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin) ⭐2.5k |
|---|---|---|---|
| 桌面 GUI | ✅ tkinter 原生 | ❌ | ✅ Calibre 集成 |
| 句子级分块 | ✅ | ❌ (10行硬切) | ❌ (段落级) |
| 术语一致性 | ✅ 实时审计 | ⚠️ 滑动窗口 | ❌ |
| 暂停/恢复 | ✅ ⏸ | ❌ | ❌ |
| 成本显示 | ✅ $/¥ 实时 | ❌ | ❌ |
| 多模型 | ✅ 预设+自定义⚙ | ✅ 多 provider | ✅ 多引擎 |
| 输出格式 | TXT/MD/PDF | 双语 EPUB/TXT | 全 Calibre 格式 |
| 断点续传 | ✅ CLI | ✅ .bin 文件 | ✅ hash 缓存 |
| 双语输出 | ❌ | ✅ | ❌ |
| 成熟度 | v1.0.0 | 5 年维护 | 3 年维护 |

---

## 常见问题

**翻一半网络断了怎么办？**
CLI 有 checkpoint 机制，重跑自动跳过已翻译的块。GUI 暂不支持，需重新开始。

**扫描版 PDF 能翻吗？**
需要 marker 视觉提取（选 PDF 提取方式为 "marker"）。首次使用会下载约 2GB 模型。

**能用自己的模型吗？**
模型下拉选「自定义...」→ 点击 ⚙ → 填入 API Base URL + Model Name + Key。支持 Ollama、vLLM、Groq 等任何 OpenAI 兼容接口。

## License

MIT © 2026

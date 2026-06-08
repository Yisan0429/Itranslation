# Changelog

## v1.0.0 (2026-06-08)

### 🚀 首次发布

**核心功能**
- 桌面 GUI（tkinter，高 DPI 支持）
- 命令行接口（`translate_book.py`）
- PDF / EPUB / TXT / Markdown 输入支持
- TXT / MD / PDF 输出

**翻译引擎**
- DeepSeek V4 Pro / V4 Flash 原生支持
- 自定义 OpenAI 兼容 API（Ollama / vLLM / Groq 等）
- 5 种体裁自动适配（文学/哲学/自然科学/社会科学/技术）
- 实时 token 计数和成本显示（$ / ¥）

**创新特性**
- 句子级语义分块 — 保证不切碎句子
- 重叠层叠 — 冗余纠错，组装时首次锁定
- 术语一致性模型 — 增量追踪，<80% 自动报警
- 暂停/恢复 — 翻译中途随时暂停

**PDF 提取**
- PyMuPDF 文本层提取（默认，快速）
- marker 视觉提取（可选，90%+ 精度，需下载 2GB 模型）

**已知限制**
- marker 模型在国内网络下下载困难
- 不支持扫描版 PDF（需 marker 模型就绪）
- 无双语对照输出
- GUI 模式不支持断点续传（CLI 支持）

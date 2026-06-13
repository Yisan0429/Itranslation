# Changelog

## v1.1.1 (2026-06-13)

### 🔧 快捷方式改进
- `book-translation.vbs` 重写：自动检测项目目录、静默启动无终端窗口
- 新增 `install-shortcut.bat` 一键桌面快捷方式安装器

### 📖 文档
- README 中英双语（README.md + README-CN.md）
- 修复功能维度对比表格 Markdown 渲染问题

## v1.1.0 (2026-06-13)

### 🚀 新增

**并行翻译**
- GUI 和 CLI 均支持章节级并行翻译（`--parallel N` 或 `parallel_workers` 配置）
- 使用线程池，默认 4 线程，可配置
- 并行模式下每章独立 consistency model，翻译完成后合并审计

**GUI 断点续传**
- 翻译中断后重启自动检测 checkpoint，弹窗询问是否恢复
- 每完成一章即保存进度，断电/崩溃不怕
- 翻译完成后自动清理 checkpoint

**文件大小检查**
- 输入文件 >100MB 给出警告，>500MB 拒绝处理
- 阈值可在 config 中调整 (`max_input_file_mb`, `max_input_file_mb_abort`)

### 🔧 修复

**自定义模型成本显示**
- 非 DeepSeek 模型不再显示错误的费用估算
- 新增 `calc_cost()` 函数，从 `pricing` 配置表查询
- 无定价的模型显示"自定义模型，费用未知"

**风格区域匹配 (kg_builder.py)**
- `_zone_matches()` 从空壳函数改为完整的区间解析器
- 支持 `ch1-ch3`、`introduction`、`conclusion`、`part1` 等格式
- 支持逗号分隔多区间，开区间 `ch4-`

**PDF 字体跨平台**
- `_find_cjk_font()` 新增，自动检测 Windows/macOS/Linux 下的 CJK 字体
- Windows: 微软雅黑/黑体/宋体等
- macOS: PingFang SC/Heiti SC/Hiragino Sans GB
- Linux: Noto Sans CJK/WenQuanYi/Droid Sans Fallback

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

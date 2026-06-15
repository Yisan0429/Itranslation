# Changelog

## v1.3.0 (2026-06-15)

### 🚀 新增
- **liteLLM 多模型生态** — `api_client.py` 集成 liteLLM，支持 6 大 Provider 20+ 模型
  - DeepSeek / OpenAI / Anthropic / Google / Groq / Qwen 统一接口
  - CLI: `--provider litellm --model openai/gpt-4o`
  - GUI: Provider 下拉 + 模型预设选择
- **Reflection 反思工作流** — `translator.py` 增加 translate→reflect→revise 循环
  - 每块翻译后 LLM 自审（accuracy/fluency/terminology/style）
  - 根据反馈自动修订，显著提升翻译质量
  - CLI: `--reflect`；GUI: Reflection 开关
  - 配置: `enable_reflection`, `reflection_depth`
- **Benchmark 基准测试系统** — `src/benchmark.py`
  - BLEU/chrF 自动评分（sacrebleu）
  - LLM-as-Judge 四维质量评估（accuracy/fluency/terminology/style）
  - 6 样本多体裁基准语料库（文学/哲学/自然科学/社会科学）
  - 组件回归测试（Chunker/Consistency/Assembler）

### 🔧 改进
- GUI 增加 Provider 选择、模型预设下拉、Reflection 开关
- CLI 增加 `--provider`、`--reflect`、`--reflect-depth` 参数
- 配置增加 `provider`、`litellm_api_key`、`enable_reflection`、`reflection_depth`、`MODEL_PRESETS`
- 定价表扩展至 12 个模型（DeepSeek/OpenAI/Anthropic/Google/Groq/Qwen）

### 📖 文档
- README 对比表更新至 v1.3，新增 TBL 竞品对比
- 新增 Reflection Workflow 章节
- 更新架构图、项目结构、Known Limitations

## v1.2.0 (2026-06-14)

### 🚀 新增
- **NiceGUI 桌面 GUI** — `desktop.py`，支持浏览器和原生窗口模式，白底黑字
  - 输入/输出双栏，体裁/格式/并行三列
  - 实时进度条、费用/耗时追踪、日志面板
  - 预读/RAT/Marker 开关，自定义模型 + API Key 配置
  - 取消翻译按钮
- **格式保护系统** — `src/format_protector.py`，代码块/公式/URL 占位符保护

### 🔧 改进
- CLI 统一使用 `api_client.call_api`（内置重试），移除冗余 `_make_llm_call`
- 分块器列表项分组、占位符句子不切割
- 并行数默认"自动"（按 CPU 核数）

### 📖 文档
- README 中英双版添加项目成熟度警告

### 🐛 修复
- 并行模式下 `cfg["_cost"]` token 计数竞态条件（使用 `cost_lock` 保护累加操作）
- `_print_header` 版本号 "v3" → "v1.1.4"
- `_split_by_separator` fallback 增加期望句子数验证，LLM 未遵循 ␟ 分隔指令时给出警告
- `extract_text()` 添加多编码自动检测（utf-8 → gbk → gb2312 → gb18030 → latin-1），兼容 Windows 下 GBK 编码的 TXT 文件
- 移除未使用的 `nltk` 依赖，减小安装体积
- 移除 `--bilingual` CLI 参数（原为 no-op，未实际实现双语输出功能）

### 📖 文档
- README 中英双版全面更新：移除不存在 GUI 的安装说明和 FAQ 引用
- 版本号统一为 v1.1.4
- 新增 API 内置重试说明
- config.py 新增 API Key 安全提示注释

### 🔧 维护
- `eval.py` 硬编码 DeepSeek 定价替换为 `calc_cost()` 调用
- `eval.py` 改为从 `api_client` 导入，不再依赖 `translate_book.py` 私有函数

## v1.1.3 (2026-06-14)

### ⚡ 架构变更
- **暂时移除 GUI** — desktop.py / VBS / 快捷方式备份至 `.archive/`
- 当前发布为 CLI-only 版本
- GUI 解决 tkinter 跨线程问题后重新加入

### 🐛 修复
- `call_api` urlopen 显式 timeout=90
- 重试最大延迟 60→30s
- 每块 API 调用时显示进度状态

## v1.1.2 (2026-06-13)

### 🚀 新增

**GUI 翻译计时器**
- 实时显示已用时间（⏱ m:ss），有进度时自动计算预估剩余时间
- CLI 完成后显示总用时

**底部状态栏**
- 左下角彩色状态栏，按架构细分步骤
- 提取: 读取文件 → 解析章节 → 完成统计
- 分块: 逐章显示进度
- 翻译: 章完成数/总数 + 当前处理中章节列表
- 组装: 去重叠 → 写入格式名

**Agentic 预读 + RAT GUI 开关**
- 高级选项: Agentic 预读（知识图谱）复选框
- 高级选项: RAT 检索增强复选框
- 预读自动检测体裁并构建术语表
- RAT 初始化 ChromaDB 增强翻译上下文

**组件评估 (eval.py)**
- Chunker: 句子拆分准确性 + 重叠检测
- ConsistencyModel: 术语漂移检测
- VectorStore: 检索命中率 (3/3 100%)
- KG Builder: 体裁检测 + 术语提取
- E2E: 完整流水线翻译，含耗时/费用

### 🔧 修复
- Chunker `_zone_matches` 正则修复（ch1-ch3 格式兼容）
- translate_book.py CLI 计时输出

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

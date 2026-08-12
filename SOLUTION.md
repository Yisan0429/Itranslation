# Itranslation 改进方案与工作安排

> 状态：P0/P1 已全部执行完毕（2026-08-13），P2 待开始
> 执行摘要：P0 止血（GUI 签名修复、checkpoint 失败语义、管线统一、端到端验证）；P1 正确性（重叠句显式标注 + body_join 组装、checkpoint 哈希命名、pytest 基建、缺陷族正反例集、块级进度可视化）；GUI 界面英文化。11 项单测全绿，CLI/GUI 端到端均真实跑通。

## 1. 现状诊断

v1.3.3 共 16 个模块、约 5400 行代码，功能广度领先同类开源工具（句子级分块、overlap 冗余、KG 预读、RAT、Reflection、缺陷族审计、一致性模型、checkpoint、成本追踪）。核心问题不是功能缺失，而是**验证深度接近为零**：端到端翻译从未成功运行过一次，核心组装算法存在确定性正确性缺陷，质量体系无实证产出。

| 层 | 问题 | 证据 | 严重度 |
|---|---|---|---|
| 端到端 | GUI 翻译路径必崩：`desktop.py:529` 的 `llm_translate(sp, up)` 缺少 `tier` 参数，与 `src/translator.py:470` 的 `llm_call(sp, up, tier=tier)` 调用方式不匹配 | `cache/checkpoint_正文.json` 存有该 TypeError 的失败记录 | P0 |
| 端到端 | 失败被固化：失败占位符写入 checkpoint 并计入 `completed_chunks`，续跑直接跳过，成品嵌失败占位符 | `src/translator.py:233-243` 与 `149-155` | P0 |
| 架构 | 双管线分裂：`desktop.py` 内嵌完整管线，与 CLI 各自实现；集成靠鸭子类型闭包，无接口契约 | `desktop.py:419-667` vs `translate_book.py` | P0 |
| 正确性 | 重叠句未标注，`start_sentence` 指向与 `chunk.text` 内容错位；组装器按 `end - start + 1` 计数，与含重叠句的实际输入矛盾，成品句子错位 | `src/assembler.py:_assemble_first_lock` | P1 |
| 正确性 | 并行组装错配：`desktop.py:568` 恒用第一章 chunks 与任意 title 配对 | `desktop.py:568` | P0 |
| 正确性 | 并行路径每线程独立 `ConsistencyModel`，跨章术语一致性失效 | `desktop.py:550` | P1 |
| 质量体系 | 一致性审计零产出（0 术语 / 0 漂移）；缺陷族正则无正反例、无精确率/召回率统计；`term_inconsistency` 无检测表达式 | `reports/consistency/*` 空模型 | P1 |
| 评估 | golden 仅 6 短段、硬编码于 py 文件、无门槛（低分不 fail）；LLM-as-Judge 可见参考译文（评价泄漏） | `src/benchmark.py:404-409` | P2 |
| 产品 | README 声称 $/¥ 双币种、同一文件 resume，实际仅显示 $、checkpoint 按章节标题命名无源文件绑定；GUI 异常无 finally 清理 | `desktop.py:326-341,588` | P2 |
| 工程 | 测试仅 1 文件 93 行；uv.lock 被 gitignore；无 CI；无 pytest 声明 | `tests/test_format_protector.py` | P1 |

## 2. 改进方案

### P0 止血（本周）：让管线跑通一次

1. 修复 GUI `llm_translate` 签名（补 `tier=None`）。
2. 修复失败固化：失败块不写入 `completed_chunks`，checkpoint 记录 `failed_chunks`，重跑时重新翻译失败块。
3. 消灭双管线：将 `translate_book.py` 的管线抽为 `src/pipeline.py` 的可复用入口，CLI 与 GUI 共用。
4. 修复 `desktop.py:568` 组装错配与并行一致性模型共享。
5. 端到端验证：CLI 与 GUI 各完成一次真实翻译，产出第一个有效 `output/` 与 `reports/`。

### P1 正确性（1-2 周）：核心算法可被单测证明

6. 重构 chunker/assembler：重叠句显式标注（仅作上下文、不要求翻译），组装按句子对齐而非按计数。
7. checkpoint 按源文件内容哈希命名，`failed_chunks` 独立管理。
8. pytest 基建：chunker / assembler / checkpoint / format_protector 单测（无需 API）。
9. 缺陷族正则建正反例集，统计精确率/召回率，`term_inconsistency` 补齐检测表达式。

### P2 质量实证（2-4 周）

10. 评估体系重建：扩大标注集、golden 外置版本化、LLM-as-Judge 屏蔽参考译文、设质量门槛（低于阈值 exit 非零）、引入人工抽检协议。
11. consistency 模型加版本字段；众数修正改为候选列表，交人工确认。
12. 用一部真实中篇公版书端到端跑通，产出真实术语表与审计报告。

### P3 产品化

13. README 与实现对齐；GUI 状态机 + finally 清理 + notify 错误呈现。
14. uv.lock 入库；CI（lint + test + benchmark quick 模式）。
15. 文学翻译纵深：跨 chunk 人物/意象一致性上下文传递、样章风格参考、篇章级后审。

## 3. 工作安排

执行顺序：P0 → P1-6/7 → P1-8/9 → P2。每阶段完成须经语法检查 + 真实运行验证 + git commit。

| 任务 | 内容 | 依赖 | 执行方式 | 验收标准 |
|---|---|---|---|---|
| P0-1 | GUI 签名修复 | 无 | 直接执行 | GUI 管线不再抛 TypeError |
| P0-2 | checkpoint 失败语义 | P0-1 | 直接执行 | 失败块重跑可恢复，成功块不被覆盖 |
| P0-3 | 管线统一重构（抽 `src/pipeline.py`） | P0-2 | 子代理重构 + 逐行验证 | CLI/GUI 走同一条管线；CLI 行为不回归 |
| P0-4 | 组装错配 + 并行一致性共享修复 | P0-3 | 直接执行 | 多章并行时组装正确、术语统计跨章合并 |
| P0-5 | 端到端验证（56 词样本，CLI + GUI） | P0-1..4 | 直接执行（Playwright 测 GUI） | 产出 `output/` 译文，`reports/` 非空 |
| P1-6 | chunker/assembler 重叠标注重构 | P0-5 | 子代理实现 + 单测验证 | 组装成品与原文句子一一对应 |
| P1-7 | checkpoint 哈希命名 + failed 管理 | P0-5 | 直接执行 | 同名异书不串缓存 |
| P1-8 | pytest 基建与核心单测 | P1-6 | 子代理编写 | `pytest` 全绿，覆盖 chunker/assembler/checkpoint |
| P1-9 | 缺陷族正反例 + 指标统计 | P1-8 | 子代理编写 | 每族有正反例，精确率/召回率可报告 |
| P2-* | 评估重建、质量门禁、真实书验证 | P1 | 另行细化 | 见第 2 节 P2 描述 |

## 4. 分工原则

- 小规模、逻辑敏感修改（签名、checkpoint 语义、锁）由主线程直接执行并验证。
- 大规模、可独立验证的重构与测试编写（管线抽取、单测、正反例集）派子代理并行执行，产物须经主线程逐项验证后方可合入。
- 所有子代理产出按自报处理：合入前必须通过语法检查、单元测试或真实运行。

"""
Itranslation Desktop GUI — NiceGUI + pywebview 原生窗口。

用法:
    uv run python desktop.py             # 浏览器模式（http://localhost:8080）
    uv run python desktop.py --native    # 原生窗口模式
"""

import sys
import os
import json
import time
import asyncio
import threading
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from nicegui import ui, app, run
from config import load_config, calc_cost, MODEL_PRESETS
from extractor import extract_book
from chunker import chunk_text, parse_structure
from format_protector import protect, restore
from assembler import assemble_translations, assemble_book
from consistency import ConsistencyModel, generate_consistency_report

# ═══════════════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════════════

cfg = load_config()

state = {
    "file_path": None,
    "file_name": "",
    "genre": "auto",
    "provider": "deepseek",
    "model": "deepseek-v4-pro",
    "api_key": cfg.get("api_key", ""),
    "api_base": cfg.get("api_base", "https://api.deepseek.com/v1"),
    "output_format": "txt",
    "output_dir": str(PROJECT_ROOT / "output"),
    "parallel": 0,
    "enable_preread": False,
    "enable_rat": False,
    "use_vision": False,
    "enable_reflection": False,
    "translating": False,
    "cancel_flag": False,
    "log_lines": [],
    "progress": 0.0,
    "current_chapter": "",
    "cost_dollars": None,
    "elapsed_sec": 0,
    "output_path": None,
    "source_preview": "",
    "target_preview": "",
}

# ═══════════════════════════════════════════════════════
# UI 构建
# ═══════════════════════════════════════════════════════

@ui.page("/")
def main_page():
    with ui.header(elevated=True).classes("bg-gray-100 text-black"):
        ui.label("Itranslation").classes("text-lg font-bold")
        ui.space()

    with ui.row().classes("w-full h-[calc(100vh-50px)] p-0 gap-0"):
        _build_control_panel()
        _build_preview_panel()

    timer = ui.timer(0.5, lambda: _update_progress_ui())
    timer.active = False
    state["_timer"] = timer


def _build_control_panel():
    with ui.column().classes("w-96 p-4 gap-2 bg-gray-50 border-r border-gray-200 h-full"):
        ui.label("控制面板").classes("text-base font-bold mb-1")

        # 输入 + 输出
        with ui.row().classes("w-full gap-2"):
            with ui.column().classes("flex-1"):
                ui.label("输入").classes("text-xs text-gray-500")
                state["file_box"] = ui.label("未选择")\
                    .classes("w-full px-3 py-2 text-xs border rounded cursor-pointer")
                state["file_upload"] = ui.upload(on_upload=_on_file_upload, auto_upload=True)\
                    .classes("hidden")
                state["file_box"].on("click", lambda: state["file_upload"].run_method("pickFiles"))
            with ui.column().classes("flex-1"):
                ui.label("输出").classes("text-xs text-gray-500")
                state["output_box"] = ui.input(value="output")\
                    .classes("w-full text-xs").props("dense")

        # 体裁 + 输出格式 + 并行
        with ui.row().classes("w-full gap-2 mt-1"):
            with ui.column().classes("flex-1"):
                ui.label("体裁").classes("text-xs text-gray-500")
                ui.select(
                    options=["auto", "literature", "philosophy", "natural_science", "social_science", "technical"],
                    value="auto",
                    on_change=lambda e: state.update(genre=e.value),
                ).classes("w-full")
            with ui.column().classes("flex-1"):
                ui.label("输出").classes("text-xs text-gray-500")
                ui.select(
                    options=["txt", "md", "pdf", "epub"],
                    value="txt",
                    on_change=lambda e: state.update(output_format=e.value),
                ).classes("w-full")
            with ui.column().classes("flex-1"):
                ui.label("并行").classes("text-xs text-gray-500")
                ui.select(
                    options=["自动", "1", "2", "3", "4", "6", "8", "12", "16"],
                    value="自动",
                    on_change=lambda e: state.update(parallel=0 if e.value == "自动" else int(e.value)),
                ).classes("w-full")

        # Provider + 模型
        ui.label("Provider").classes("text-xs text-gray-500 mt-1")
        with ui.row().classes("w-full gap-2"):
            # 平台下拉（DeepSeek / OpenAI / Anthropic / Google / Mimo / Custom）
            provider_labels = list(dict.fromkeys(p["provider_label"] for p in MODEL_PRESETS))
            ui.select(
                options=provider_labels,
                value="DeepSeek",
                on_change=lambda e: _on_provider_change(e.value),
            ).classes("flex-1")
            # 模型下拉（根据所选平台动态更新）
            state["model_select"] = ui.select(
                options=[p["label"] for p in MODEL_PRESETS if p["provider_label"] == "DeepSeek"],
                value="V4 Pro",
                on_change=lambda e: _on_model_select(e.value),
            ).classes("flex-1")
        state["model_input"] = ui.input(value="",
            placeholder="输入模型名 (如 openai/gpt-5.5)",
            on_change=lambda e: state.update(model=e.value))
        state["model_input"].classes("w-full mt-1")
        state["model_input"].set_visibility(False)

        ui.label("API Key").classes("text-xs text-gray-500 mt-1")
        state["api_key_input"] = ui.input(
            value=state["api_key"], password=True, password_toggle_button=True,
            placeholder="sk-...",
            on_change=lambda e: state.update(api_key=e.value),
        ).classes("w-full")

        ui.label("API Base").classes("text-xs text-gray-500 mt-1")
        state["api_base_input"] = ui.input(
            value=state["api_base"],
            placeholder="https://api.deepseek.com/v1",
            on_change=lambda e: state.update(api_base=e.value),
        ).classes("w-full")

        with ui.row().classes("gap-3 mt-2"):
            ui.switch("预读", value=False,
                      on_change=lambda e: state.update(enable_preread=e.value))
            ui.switch("RAT", value=False,
                      on_change=lambda e: state.update(enable_rat=e.value))
            ui.switch("Marker", value=False,
                      on_change=lambda e: state.update(use_vision=e.value))
            ui.switch("Reflection", value=False,
                      on_change=lambda e: state.update(enable_reflection=e.value))

        # 按钮 + 状态
        state["start_btn"] = ui.button(
            "开始翻译",
            on_click=_start_translation,
        ).classes("w-full bg-black text-white font-bold mt-2")
        state["cancel_btn"] = ui.button(
            "取消",
            on_click=_cancel_translation,
        ).classes("w-full bg-red-600 text-white font-bold mt-1")
        state["cancel_btn"].set_visibility(False)

        with ui.row().classes("w-full justify-between mt-1"):
            state["cost_label"] = ui.label("--").classes("text-xs text-emerald-600 font-mono")
            state["time_label"] = ui.label("--").classes("text-xs text-gray-500 font-mono")

        state["progress_bar"] = ui.linear_progress(value=0).classes("w-full mt-1")
        state["chapter_label"] = ui.label("").classes("text-2xs text-gray-400")



def _build_preview_panel():
    with ui.column().classes("flex-1 p-4 gap-2 overflow-y-auto bg-white"):
        ui.label("原文").classes("text-sm font-bold")
        state["source_area"] = ui.label("选择文件后将显示原文预览...")\
            .classes("w-full h-48 text-xs overflow-auto border p-2")\
            .style("white-space: pre-wrap; font-family: monospace")

        ui.separator().classes("my-1")

        with ui.row().classes("w-full items-center"):
            ui.label("译文").classes("text-sm font-bold")
            ui.space()
            state["download_btn"] = ui.button("下载", on_click=_download_output)\
                .classes("bg-black text-white text-xs")
            state["download_btn"].set_visibility(False)
        state["target_area"] = ui.label("翻译完成后将在此显示译文...")\
            .classes("w-full h-48 text-xs overflow-auto border p-2")\
            .style("white-space: pre-wrap; font-family: monospace")

        state["log_area"] = ui.textarea(value="", label="日志")\
            .props("readonly outlined dense").classes("w-full text-2xs")


def _on_provider_change(provider_label: str):
    """切换平台时更新模型下拉列表。"""
    # 查找该平台的实际 provider 类型
    presets = [p for p in MODEL_PRESETS if p["provider_label"] == provider_label]
    if not presets:
        return

    actual_provider = presets[0]["provider"]
    state["provider"] = actual_provider

    if actual_provider == "custom":
        state["model_select"].set_visibility(False)
        state["model_input"].set_visibility(True)
        state["model_input"].value = ""
        state["model"] = ""
    else:
        labels = [p["label"] for p in presets]
        state["model_select"].options = labels
        state["model_select"].value = labels[0]
        state["model_select"].set_visibility(True)
        state["model_input"].set_visibility(False)
        # 同步 model ID
        state["model"] = presets[0]["model"]


def _on_model_select(label: str):
    """模型下拉选择时更新 model ID。"""
    for p in MODEL_PRESETS:
        if p["label"] == label:
            state["model"] = p["model"]
            return


# ═══════════════════════════════════════════════════════
# 事件处理
# ═══════════════════════════════════════════════════════

async def _on_file_upload(e):
    """文件上传回调。"""
    f = e.file
    fname = f.name or "uploaded_file"
    fpath = PROJECT_ROOT / "input" / fname
    fpath.parent.mkdir(parents=True, exist_ok=True)
    await f.save(fpath)

    state["file_path"] = str(fpath)
    state["file_name"] = fname
    state["file_box"].set_text(fname)
    ui.notify(f"已选择: {fname}", type="positive")

    # 原文预览
    try:
        text = fpath.read_text(encoding="utf-8")[:3000]
    except Exception:
        text = f"(预览不可用: {fname})"
    state["source_area"].set_text(text)


def _clear_file():
    state["file_path"] = None
    state["file_name"] = ""
    state["file_box"].set_text("未选择")
    state["source_area"].set_text("选择文件后将显示原文预览...")


def _cancel_translation():
    state["cancel_flag"] = True
    ui.notify("取消中...", type="warning")


async def _ask_clear_cache(book_name: str, checkpoints: list, outputs: list) -> bool | None:
    """弹窗询问：检测到旧缓存，是否清除后重新翻译？
    Returns: True=清除, False=保留续翻, None=取消
    """
    cp_names = [cp.stem.replace("checkpoint_", "") for cp in checkpoints]
    msg = f"「{book_name}」已有翻译记录"
    if cp_names:
        msg += f"\n断点: {', '.join(cp_names[:5])}"
    if outputs:
        msg += f"\n输出: {len(outputs)} 个文件"
    msg += "\n\n清除后重新翻译？"

    result = {"value": None}

    with ui.dialog() as dialog, ui.card().classes("p-4 gap-2"):
        ui.label(msg).classes("text-sm whitespace-pre-line")
        with ui.row().classes("gap-2 mt-2"):
            ui.button("清除重译", on_click=lambda: [_set_result(result, True), dialog.close()])\
                .classes("bg-red-600 text-white")
            ui.button("保留续翻", on_click=lambda: [_set_result(result, False), dialog.close()])\
                .classes("bg-gray-200 text-black")
            ui.button("取消", on_click=lambda: dialog.close())\
                .classes("bg-gray-100 text-black")

    await dialog
    return result["value"]


def _set_result(container: dict, value):
    container["value"] = value


def _log(msg: str):
    """添加日志。"""
    state["log_lines"].append(msg)
    if state.get("log_area"):
        state["log_area"].value = "\n".join(state["log_lines"])


def _update_progress_ui():
    """定时器回调：更新进度 UI。"""
    if state.get("progress_bar"):
        state["progress_bar"].value = state["progress"]
    if state.get("chapter_label"):
        state["chapter_label"].set_text(state["current_chapter"])
    if state.get("time_label"):
        if state["elapsed_sec"] > 0:
            m, s = divmod(int(state["elapsed_sec"]), 60)
            state["time_label"].set_text(f"{m}:{s:02d}")
    if state.get("cost_label"):
        if state["cost_dollars"] is not None:
            state["cost_label"].set_text(
                f"${state['cost_dollars']:.4f}"
            )


async def _start_translation():
    """开始翻译。如有 checkpoint 则询问是否清除。"""
    if state["translating"]:
        return

    fp = state.get("file_path")
    if not fp or not Path(fp).exists():
        ui.notify("请先选择文件", type="warning")
        return

    # 检查是否有旧的 checkpoint/输出
    book_name = Path(fp).stem
    cache_dir = PROJECT_ROOT / "cache"
    existing_checkpoints = list(cache_dir.glob(f"checkpoint_*.json"))
    existing_output = list((PROJECT_ROOT / "output" / book_name).glob(f"{book_name}.*")) if (PROJECT_ROOT / "output" / book_name).exists() else []

    if existing_checkpoints or existing_output:
        result = await _ask_clear_cache(book_name, existing_checkpoints, existing_output)
        if result is None:  # 用户取消
            return
        if result:  # 清除缓存
            for cp in existing_checkpoints:
                cp.unlink(missing_ok=True)
            import shutil
            out_dir = PROJECT_ROOT / "output" / book_name
            if out_dir.exists():
                shutil.rmtree(out_dir)
            ui.notify("已清除缓存，重新翻译", type="positive")

    state["translating"] = True
    state["cancel_flag"] = False
    state["progress"] = 0.0
    state["cost_dollars"] = None
    state["elapsed_sec"] = 0
    state["log_lines"] = []
    state["output_path"] = None
    state["start_btn"].set_enabled(False)
    state["start_btn"].set_visibility(False)
    state["cancel_btn"].set_visibility(True)
    state["progress_bar"].value = 0
    state["log_lines"] = []
    if state.get("log_area"):
        state["log_area"].value = ""
    state["target_area"].set_text("翻译中...")
    state["download_btn"].set_visibility(False)

    # 启动进度定时器
    state["_timer"].activate()

    # 在后台线程中运行翻译
    errors = []
    def _run():
        try:
            _run_translation_pipeline()
        except Exception as e:
            errors.append(e)
    t = threading.Thread(target=_run, daemon=True)
    t.start()

    # 等待线程完成（同时保持 UI 响应）
    while t.is_alive():
        await asyncio.sleep(0.25)

    if errors:
        raise errors[0]

    state["translating"] = False
    state["start_btn"].set_enabled(True)
    state["start_btn"].set_visibility(True)
    state["cancel_btn"].set_visibility(False)
    state["_timer"].deactivate()

    if state.get("output_path"):
        state["download_btn"].set_visibility(True)


def _run_translation_pipeline():
    """在后台线程中运行完整翻译管线。"""
    start_time = time.time()
    cfg_local = load_config()
    cfg_local["provider"] = state["provider"]
    cfg_local["model"] = state["model"]
    cfg_local["api_key"] = state["api_key"]
    cfg_local["api_base"] = state["api_base"]
    cfg_local["genre"] = state["genre"]
    cfg_local["parallel_workers"] = state["parallel"]
    cfg_local["enable_agentic_preread"] = state["enable_preread"]
    cfg_local["enable_reflection"] = state["enable_reflection"]

    # 自动并行数：0 = 按章节数自动
    actual_parallel = state["parallel"]
    if actual_parallel == 0:
        import os
        actual_parallel = min(8, max(1, os.cpu_count() or 4))

    book_path = Path(state["file_path"])

    # Phase 0: 提取
    _log(f"📄 提取: {book_path.name}")
    state["current_chapter"] = "Phase 0: 提取文本..."
    state["progress"] = 0.02

    book_md = extract_book(str(book_path), use_vision=state["use_vision"])

    # 格式保护
    book_md, placeholders = protect(book_md, verbose=False)
    if placeholders:
        _log(f"🛡️ 格式保护: {len(placeholders)} 个占位符")

    # 解析章节
    chapters = parse_structure(book_md)
    _log(f"📖 {len(chapters)} 章")
    state["progress"] = 0.05

    # Phase 1: 分块
    state["current_chapter"] = "Phase 1: 语义分块..."
    overlap = cfg_local["overlap_by_genre"].get(cfg_local["genre"], 3)

    all_chapter_chunks = []
    for ch_idx, chapter in enumerate(chapters):
        if state["cancel_flag"]:
            _log("⚠️ 用户取消翻译")
            return
        chapter_text = "\n\n".join(chapter.get("paragraphs", []))
        if not chapter_text.strip():
            continue
        chunks = chunk_text(
            chapter_text,
            target_tokens=cfg_local.get("chunk_target_tokens", 1500),
            max_tokens=cfg_local.get("chunk_max_tokens", 3000),
            overlap_sentences=overlap,
        )
        all_chapter_chunks.append((chapter["title"], chunks))

    total_chunks = sum(len(c) for _, c in all_chapter_chunks)
    _log(f"✂️ {total_chunks} 块 (重叠 {overlap} 句)")

    # Phase 2: 翻译
    state["current_chapter"] = "Phase 2: 翻译中..."
    state["progress"] = 0.10

    import threading as th
    from api_client import call_api

    consistency_model = ConsistencyModel()

    # 初始化 RAT
    vector_store = None
    if state["enable_rat"]:
        try:
            from vector_store import TranslationVectorStore
            vector_store = TranslationVectorStore(
                persist_dir=cfg_local["vector_store_dir"]
            )
            _log("📚 RAT 向量存储已初始化")
        except Exception as e:
            _log(f"⚠️ RAT 初始化失败: {e}")

    # KG 预读
    glossary = {}
    kg = {}
    if state["enable_preread"]:
        _log("🧠 Agentic Pre-Read...")
        from kg_builder import build_knowledge_graph, kg_to_glossary

        def llm_kg(sp, up):
            return call_api(
                api_key=state["api_key"],
                api_base=state["api_base"],
                model=cfg_local["model"],
                system_prompt=sp, user_prompt=up,
                max_tokens=4096,
                provider=state["provider"],
            )

        try:
            kg = build_knowledge_graph(book_md, llm_kg,
                                        sample_ratio=0.1, max_sample_tokens=30000)
            glossary = kg_to_glossary(kg)
            if cfg_local["genre"] == "auto":
                cfg_local["genre"] = kg.get("book_metadata", {}).get("genre", "natural_science")
            _log(f"  体裁: {cfg_local['genre']}, 术语: {len(glossary)} 个")
        except Exception as e:
            _log(f"⚠️ 预读失败: {e}")

    # LLM 翻译函数
    def llm_translate(sp, up):
        return call_api(
            api_key=state["api_key"],
            api_base=state["api_base"],
            model=cfg_local["model"],
            system_prompt=sp, user_prompt=up,
            max_tokens=cfg_local.get("max_tokens_per_chunk", 4096),
            provider=state["provider"],
        )

    cost_lock = th.Lock()
    from translator import translate_chapter as do_chapter

    all_translations = []
    all_errors = []
    done_chunks = 0

    if actual_parallel > 1 and len(all_chapter_chunks) > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def translate_one(title, chunks_list):
            cm = ConsistencyModel()
            checkpoint_path = str(PROJECT_ROOT / "cache" / f"checkpoint_{title}.json")
            return do_chapter(
                chapter_title=title, chunks=chunks_list,
                vector_store=vector_store,
                consistency_model=cm, glossary=glossary, kg=kg,
                llm_call=llm_translate, config=cfg_local,
                checkpoint_path=checkpoint_path, cost_lock=cost_lock,
            )

        with ThreadPoolExecutor(max_workers=actual_parallel) as pool:
            futures = {pool.submit(translate_one, t, c): t for t, c in all_chapter_chunks}
            for fut in as_completed(futures):
                if state["cancel_flag"]:
                    pool.shutdown(wait=False, cancel_futures=True)
                    return
                title = futures[fut]
                trans, errs = fut.result()
                all_translations.append((title, all_chapter_chunks[0][1], trans))
                all_errors.extend(errs)
                done_chunks += len(trans)
                state["progress"] = 0.10 + 0.75 * (done_chunks / max(total_chunks, 1))
                state["current_chapter"] = f"翻译中: {title} ({done_chunks}/{total_chunks})"
                if errs:
                    _log(f"⚠️ {title}: {len(trans)} 块, {len(errs)} 错误")
                else:
                    _log(f"✅ {title}: {len(trans)} 块")

                cost = cfg_local.get("_cost", {})
                pt = cost.get("prompt_tokens", 0)
                ct = cost.get("completion_tokens", 0)
                cost_val, _ = calc_cost(cfg_local["model"], pt, ct)
                state["cost_dollars"] = cost_val
                state["elapsed_sec"] = time.time() - start_time
    else:
        for title, chunks_list in all_chapter_chunks:
            if state["cancel_flag"]:
                return
            checkpoint_path = str(PROJECT_ROOT / "cache" / f"checkpoint_{title}.json")
            trans, errs = do_chapter(
                chapter_title=title, chunks=chunks_list,
                vector_store=vector_store,
                consistency_model=consistency_model, glossary=glossary, kg=kg,
                llm_call=llm_translate, config=cfg_local,
                checkpoint_path=checkpoint_path, cost_lock=cost_lock,
            )
            all_translations.append((title, chunks_list, trans))
            all_errors.extend(errs)
            done_chunks += len(trans)
            state["progress"] = 0.10 + 0.75 * (done_chunks / max(total_chunks, 1))
            state["current_chapter"] = f"翻译中: {title} ({done_chunks}/{total_chunks})"
            if errs:
                _log(f"⚠️ {title}: {len(errs)} 个块失败")
            else:
                _log(f"✅ {title}: {len(trans)} 块")

            cost = cfg_local.get("_cost", {})
            pt = cost.get("prompt_tokens", 0)
            ct = cost.get("completion_tokens", 0)
            cost_val, _ = calc_cost(cfg_local["model"], pt, ct)
            state["cost_dollars"] = cost_val
            state["elapsed_sec"] = time.time() - start_time

    # 错误汇总
    if all_errors:
        _log(f"❌ 翻译错误: {len(all_errors)} 个块")
        for e in all_errors[:5]:
            _log(f"   {e['chapter']}/{e['chunk_id']}: {e['error'][:80]}")

    # 低 Token 审计
    from auditor import Auditor
    auditor = Auditor()
    for title, chunks_list, trans in all_translations:
        full_text = assemble_translations(chunks_list, trans, "first_lock")
        auditor.scan_chapter(full_text, title)
    if auditor.total_issues > 0:
        _log(f"📋 低 Token 审计: {auditor.total_issues} 处候选问题")
        # 只报告 P1/P2
        p1p2 = sum(len(v) for k, v in auditor.findings.items()
                    if auditor._family_severity(k) in ("P1", "P2"))
        if p1p2 > 0:
            _log(f"   ⚠️ P1/P2 严重问题: {p1p2} 处，建议审查")

    # Phase 4: 组装 + 还原
    state["current_chapter"] = "Phase 4: 组装输出..."
    state["progress"] = 0.88

    book_name = book_path.stem
    out_dir = state["output_box"].value or "output"
    output_path = str(PROJECT_ROOT / out_dir / book_name / f"{book_name}.{state['output_format']}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    full_translations = []
    for title, chunks_list, trans in all_translations:
        full_text = assemble_translations(chunks_list, trans, "first_lock")
        full_text = restore(full_text, placeholders, verbose=False)
        full_translations.append((title, full_text))

    _log(f"🔄 格式还原: {len(placeholders)} 占位符")

    assemble_book(full_translations, output_path, fmt=state["output_format"])

    state["progress"] = 1.0
    state["current_chapter"] = "✅ 完成"
    state["elapsed_sec"] = time.time() - start_time
    state["output_path"] = output_path

    # 显示译文预览
    try:
        preview = Path(output_path).read_text(encoding="utf-8")[:5000]
        state["target_area"].set_text(preview)
    except Exception:
        state["target_area"].set_text(f"译文已保存至: {output_path}")

    _log(f"✅ 翻译完成: {output_path}")
    _log(f"⏱ 用时: {int(state['elapsed_sec']//60)}:{int(state['elapsed_sec']%60):02d}")


async def _download_output():
    """下载输出文件。"""
    if state.get("output_path") and Path(state["output_path"]).exists():
        ui.download(state["output_path"])
    else:
        ui.notify("没有可下载的文件", type="warning")


# ═══════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Itranslation Desktop GUI")
    parser.add_argument("--native", action="store_true", help="原生窗口模式（桌面应用）")
    parser.add_argument("--port", type=int, default=8080, help="Web 服务器端口")
    args = parser.parse_args()

    if args.native:
        ui.run(
            native=True,
            window_size=(1280, 800),
            title="Itranslation",
            reload=False,
            storage_secret="itranslation-gui-2026",
        )
    else:
        ui.run(
            host="127.0.0.1",
            port=args.port,
            title="Itranslation",
            reload=False,
            storage_secret="itranslation-gui-2026",
        )


if __name__ == "__main__":
    main()

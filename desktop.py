"""
Itranslation Desktop GUI — NiceGUI + pywebview 原生窗口。

用法:
    uv run python desktop.py             # 浏览器模式（http://localhost:8080）
    uv run python desktop.py --native    # 原生窗口模式
"""

import sys
import os
import io
import json
import asyncio
import threading
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from nicegui import ui, app, run
from config import load_config
from pipeline import run_translation_pipeline, slugify

# ═══════════════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════════════

cfg = load_config()

state = {
    "file_path": None,
    "file_name": "",
    "genre": "auto",
    "provider": "custom",
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
    "elapsed_sec": 0,
    "output_path": None,
    "source_preview": "",
    "target_preview": "",
}

# ═══════════════════════════════════════════════════════
# UI 构建
# ═══════════════════════════════════════════════════════

@ui.page("/api/output_dir")
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
        ui.label("Control Panel").classes("text-base font-bold mb-1")

        # 输入 + 输出
        with ui.row().classes("w-full gap-2"):
            with ui.column().classes("flex-1"):
                ui.label("Input").classes("text-xs text-gray-500")
                state["file_box"] = ui.label("No file")\
                    .classes("w-full px-3 py-2 text-xs border rounded cursor-pointer")
                state["file_upload"] = ui.upload(on_upload=_on_file_upload, auto_upload=True)\
                    .classes("hidden")
                state["file_box"].on("click", lambda: state["file_upload"].run_method("pickFiles"))
            with ui.column().classes("flex-1"):
                ui.label("Output").classes("text-xs text-gray-500")
                state["output_box"] = ui.input(value="output")\
                    .classes("w-full text-xs").props("dense")

        # 体裁 + 输出格式 + 并行
        with ui.row().classes("w-full gap-2 mt-1"):
            with ui.column().classes("flex-1"):
                ui.label("Genre").classes("text-xs text-gray-500")
                ui.select(
                    options=["auto", "literature", "philosophy", "natural_science", "social_science", "technical"],
                    value="auto",
                    on_change=lambda e: state.update(genre=e.value),
                ).classes("w-full")
            with ui.column().classes("flex-1"):
                ui.label("Output").classes("text-xs text-gray-500")
                ui.select(
                    options=["txt", "md", "pdf", "epub"],
                    value="txt",
                    on_change=lambda e: state.update(output_format=e.value),
                ).classes("w-full")
            with ui.column().classes("flex-1"):
                ui.label("Parallel").classes("text-xs text-gray-500")
                ui.select(
                    options=["Auto", "1", "2", "3", "4", "6", "8", "12", "16"],
                    value="Auto",
                    on_change=lambda e: state.update(parallel=0 if e.value == "Auto" else int(e.value)),
                ).classes("w-full")

        # Model 名称（带 "前缀/名" 时自动走 liteLLM，裸名走 OpenAI 兼容直连）
        ui.label("Model").classes("text-xs text-gray-500 mt-1")
        state["model_input"] = ui.input(
            value=state["model"],
            placeholder="deepseek-v4-pro 或 openai/gpt-5.5",
            on_change=lambda e: state.update(model=e.value),
        ).classes("w-full")

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

        ui.button("Save API Config", on_click=_save_api_config).classes("text-xs mt-1")

        with ui.row().classes("gap-3 mt-2"):
            ui.switch("Pre-read", value=False,
                      on_change=lambda e: state.update(enable_preread=e.value))
            ui.switch("RAT", value=False,
                      on_change=lambda e: state.update(enable_rat=e.value))
            ui.switch("Marker", value=False,
                      on_change=lambda e: state.update(use_vision=e.value))
            ui.switch("Reflection", value=False,
                      on_change=lambda e: state.update(enable_reflection=e.value))

        # 按钮 + 状态
        state["start_btn"] = ui.button(
            "Start Translation",
            on_click=_start_translation,
        ).classes("w-full bg-black text-white font-bold mt-2")
        state["cancel_btn"] = ui.button(
            "Cancel",
            on_click=_cancel_translation,
        ).classes("w-full bg-red-600 text-white font-bold mt-1")
        state["cancel_btn"].set_visibility(False)

        with ui.row().classes("w-full justify-between mt-1"):
            state["time_label"] = ui.label("--").classes("text-xs text-gray-500 font-mono")

        with ui.row().classes("w-full items-center gap-2 mt-1"):
            state["progress_bar"] = ui.linear_progress(value=0).props("size=8px").classes("flex-1")
            state["percent_label"] = ui.label("0%").classes("text-xs font-mono text-gray-600 w-10 text-right")
        state["chapter_label"] = ui.label("").classes("text-2xs text-gray-400")



def _build_preview_panel():
    with ui.column().classes("flex-1 p-4 gap-2 overflow-y-auto bg-white"):
        ui.label("Source").classes("text-sm font-bold")
        state["source_area"] = ui.label("Select a file to preview the source...")\
            .classes("w-full h-48 text-xs overflow-auto border p-2")\
            .style("white-space: pre-wrap; font-family: monospace")

        ui.separator().classes("my-1")

        with ui.row().classes("w-full items-center"):
            ui.label("Translation").classes("text-sm font-bold")
            ui.space()
            state["download_btn"] = ui.button("Download", on_click=_download_output)\
                .classes("bg-black text-white text-xs")
            state["download_btn"].set_visibility(False)
        state["target_area"] = ui.label("Translation will appear here after completion.")\
            .classes("w-full h-48 text-xs overflow-auto border p-2")\
            .style("white-space: pre-wrap; font-family: monospace")

        state["log_area"] = ui.textarea(value="", label="Log")\
            .props("readonly outlined dense").classes("w-full text-2xs")


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
    ui.notify(f"Selected: {fname}", type="positive")

    # 原文预览（异步读取，避免阻塞 UI）
    async def _load_preview():
        try:
            text = fpath.read_text(encoding="utf-8")[:3000]
        except Exception:
            text = f"(Preview unavailable: {fname})"
        state["source_area"].set_text(text)
    asyncio.create_task(_load_preview())



def _clear_file():
    state["file_path"] = None
    state["file_name"] = ""
    state["file_box"].set_text("No file")
    state["source_area"].set_text("Select a file to preview the source...")


def _cancel_translation():
    state["cancel_flag"] = True
    ui.notify("Cancelling...", type="warning")


async def _ask_clear_cache(book_name: str, checkpoints: list, outputs: list) -> bool | None:
    """弹窗询问：检测到旧缓存，是否Clear cache and retranslate?
    Returns: True=清除, False=保留续翻, None=取消
    """
    cp_names = [cp.stem.replace("checkpoint_", "") for cp in checkpoints]
    msg = f'"{book_name}" has existing translation records'
    if cp_names:
        msg += f"\nCheckpoints: {', '.join(cp_names[:5])}"
    if outputs:
        msg += f"\nOutputs: {len(outputs)} files"
    msg += "\n\nClear cache and retranslate?"

    result = {"value": None}

    with ui.dialog() as dialog, ui.card().classes("p-4 gap-2"):
        ui.label(msg).classes("text-sm whitespace-pre-line")
        with ui.row().classes("gap-2 mt-2"):
            ui.button("Clear & Retranslate", on_click=lambda: [_set_result(result, True), dialog.close()])\
                .classes("bg-red-600 text-white")
            ui.button("Keep & Resume", on_click=lambda: [_set_result(result, False), dialog.close()])\
                .classes("bg-gray-200 text-black")
            ui.button("Cancel", on_click=lambda: dialog.close())\
                .classes("bg-gray-100 text-black")

    await dialog
    return result["value"]


def _set_result(container: dict, value):
    container["value"] = value


def _save_api_config():
    """保存当前 API 配置到 config.json（仅覆盖 API 相关字段）。"""
    cfg_path = PROJECT_ROOT / "config.json"
    existing = {}
    if cfg_path.exists():
        try:
            existing = json.loads(io.open(cfg_path, encoding="utf-8").read())
        except (json.JSONDecodeError, OSError):
            existing = {}
    _m = (state["model"] or "").strip()
    existing["provider"] = "litellm" if "/" in _m and not _m.startswith(("http", "https")) else "custom"
    existing["model"] = _m
    existing["api_key"] = state["api_key"]
    existing["api_base"] = state["api_base"]
    io.open(cfg_path, "w", encoding="utf-8").write(
        json.dumps(existing, ensure_ascii=False, indent=2))
    ui.notify("API configuration saved to config.json", type="positive")


def _log(msg):
    """添加日志。"""
    state["log_lines"].append(str(msg))
    if len(state["log_lines"]) > 500:
        del state["log_lines"][:-500]
    if state.get("log_area"):
        state["log_area"].value = "\n".join(state["log_lines"])


def _update_progress_ui():
    """定时器回调：更新进度 UI。"""
    if state.get("progress_bar"):
        state["progress_bar"].value = state["progress"]
    if state.get("percent_label"):
        state["percent_label"].set_text(f"{int(state['progress'] * 100)}%")
    if state.get("chapter_label"):
        state["chapter_label"].set_text(state["current_chapter"])
    if state.get("time_label"):
        if state["elapsed_sec"] > 0:
            m, s = divmod(int(state["elapsed_sec"]), 60)
            state["time_label"].set_text(f"{m}:{s:02d}")


async def _start_translation():
    """开始翻译。如有 checkpoint 则询问是否清除。"""
    if state["translating"]:
        return

    fp = state.get("file_path")
    if not fp or not Path(fp).exists():
        ui.notify("Please select a file first", type="warning")
        return

    # 检查是否有旧的 checkpoint/输出
    book_name = Path(fp).stem
    _cfg = load_config()
    cache_dir = Path(_cfg.get("cache_dir", str(PROJECT_ROOT / "cache")))
    existing_checkpoints = list(cache_dir.glob(f"checkpoint_{slugify(book_name)}__*.json"))
    _out_root = Path(_cfg.get("output_dir", str(PROJECT_ROOT / "output")))
    existing_output = list((_out_root / book_name).glob(f"{book_name}.*")) if (_out_root / book_name).exists() else []

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
            ui.notify("Cache cleared, retranslating", type="positive")

    state["translating"] = True
    state["cancel_flag"] = False
    state["progress"] = 0.0
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
    state["target_area"].set_text("Translating...")
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

    # 无论成功失败，恢复 UI 状态；错误通过 notify 与日志呈现
    if errors:
        ui.notify(f"Translation failed: {errors[0]}", type="negative", timeout=0)
        _log(f"❌ Translation failed: {errors[0]}")

    state["translating"] = False
    state["start_btn"].set_enabled(True)
    state["start_btn"].set_visibility(True)
    state["cancel_btn"].set_visibility(False)
    state["_timer"].deactivate()

    if not errors and state.get("output_path"):
        state["download_btn"].set_visibility(True)


def _run_translation_pipeline():
    """在后台线程中运行完整翻译管线（统一入口 src/pipeline.py）。"""
    cfg_local = load_config()
    cfg_local["provider"] = state["provider"]
    cfg_local["model"] = state["model"]
    cfg_local["api_key"] = state["api_key"]
    cfg_local["api_base"] = state["api_base"]
    _model = (state["model"] or "").strip()
    cfg_local["provider"] = "litellm" if "/" in _model and not _model.startswith(("http", "https")) else "custom"
    cfg_local["model"] = _model or cfg_local.get("model", "deepseek-v4-pro")
    cfg_local["genre"] = state["genre"]
    cfg_local["parallel_workers"] = state["parallel"]
    cfg_local["enable_agentic_preread"] = state["enable_preread"]
    cfg_local["enable_reflection"] = state["enable_reflection"]

    book_name = Path(state["file_path"]).stem
    out_dir_raw = state["output_box"].value or "output"
    output_path = str(PROJECT_ROOT / out_dir_raw / book_name / f"{book_name}.{state['output_format']}")

    if state["enable_rat"]:
        try:
            from env_check import check_rat
            _rat = check_rat()
            if not _rat.get("available"):
                _log("⚠️ RAT unavailable: " + _rat.get("message", ""))
                ui.notify("RAT unavailable, continuing without retrieval augmentation", type="warning")
        except Exception:
            pass
    params = {
        "book": state["file_path"],
        "config": cfg_local,
        "no_preread": not state["enable_preread"],
        "no_rat": not state["enable_rat"],
        "no_vision": not state["use_vision"],
        "format": state["output_format"],
        "parallel": state["parallel"],
        "output": output_path,
    }

    def _progress(frac: float, msg: str):
        if frac >= state["progress"]:
            state["progress"] = frac
        state["current_chapter"] = msg

    result = run_translation_pipeline(
        params=params,
        log_fn=_log,
        progress_fn=_progress,
        cancel_fn=lambda: state["cancel_flag"],
    )

    if result["output_path"] is None:
        _log("⚠️ Translation cancelled by user")
        return

    state["output_path"] = result["output_path"]
    state["elapsed_sec"] = result["elapsed_sec"]

    # 显示译文预览
    try:
        preview = Path(result["output_path"]).read_text(encoding="utf-8")[:5000]
        state["target_area"].set_text(preview)
    except Exception:
        state["target_area"].set_text(f"Translation saved to: {result['output_path']}")

    _log(f"✅ Translation complete: {result['output_path']}")
    _log(f"⏱ Elapsed: {int(result['elapsed_sec']//60)}:{int(result['elapsed_sec']%60):02d}")

async def _download_output():
    """下载输出文件。"""
    if state.get("output_path") and Path(state["output_path"]).exists():
        ui.download(state["output_path"])
    else:
        ui.notify("No file to download", type="warning")


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

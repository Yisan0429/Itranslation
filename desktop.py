#!/usr/bin/env python3
"""
Itranslation — AI 全书翻译工具
启动: uv run python desktop.py  (或 python desktop.py)
"""

import ctypes, json, os, sys, subprocess, time, traceback, threading, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ═══════════════════════════════════════════════════════════
# 环境检测（启动时自动检查，缺什么提示什么）
# ═══════════════════════════════════════════════════════════

def _check_env():
    """检查运行环境，缺失时给出明确修复指令。"""
    errors = []

    # 1. 检查 Python 版本
    if sys.version_info < (3, 11):
        errors.append(
            "❌ Python 版本过低\n"
            f"   当前: {sys.version}\n"
            "   需要: Python 3.11+\n"
            "   下载: https://www.python.org/downloads/"
        )

    # 2. 检查关键依赖
    missing_pkgs = []
    for pkg, import_name, desc in [
        ("pymupdf", "fitz", "PDF 文本提取"),
        ("nltk", "nltk", "句子分词"),
        ("rich", "rich", "终端美化"),
        ("tenacity", "tenacity", "API 重试"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            missing_pkgs.append(f"  {pkg:20s} — {desc}")

    if missing_pkgs:
        errors.append(
            "❌ 缺少依赖包\n"
            + "\n".join(missing_pkgs) +
            "\n\n修复方法:\n"
            "  uv sync"
        )

    # 3. 检查 uv（如果是 git clone 的新用户可能没装）
    try:
        subprocess.run(["uv", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        errors.append(
            "❌ 未找到 uv 包管理器\n\n"
            "安装方法:\n"
            "  pip install uv\n"
            "  # 然后运行: uv sync"
        )

    # 4. 检查 config.json
    config_path = Path(__file__).parent / "config.json"
    has_config = config_path.exists()
    if has_config:
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            has_api_key = bool(cfg.get("api_key", "").strip())
        except Exception:
            has_api_key = False
    else:
        has_api_key = False

    if not has_api_key:
        errors.append(
            "❌ 未配置 API Key\n\n"
            "创建 config.json 并填入 DeepSeek API Key:\n"
            '  {"api_key": "sk-你的key", "model": "deepseek-v4-pro"}\n\n'
            "获取免费 API Key: https://platform.deepseek.com/"
        )

    # 5. 显示所有错误
    if errors:
        print("\n" + "=" * 55)
        print("  Itranslation — 环境检测")
        print("=" * 55)
        for i, err in enumerate(errors, 1):
            print(f"\n  [{i}] {err}")
        print("\n" + "=" * 55)
        print("  修复后重新运行: uv run python desktop.py")
        print("=" * 55 + "\n")

        # 如果有 GUI 能力，弹窗提示
        try:
            import tkinter.messagebox as mb
            root = __import__("tkinter").Tk()
            root.withdraw()
            mb.showwarning("Itranslation — 环境检测",
                           f"发现 {len(errors)} 个问题:\n\n" +
                           "\n".join(f"{i}. {e.split(chr(10))[0][2:]}" for i, e in enumerate(errors, 1)) +
                           "\n\n请查看终端输出获取修复方法。")
            root.destroy()
        except Exception:
            pass

        sys.exit(1)

    # === 可选功能检测（仅警告，不阻止启动）===
    _check_optional_features()

    return True


def _check_optional_features():
    """检测可选功能，打印状态但不阻止启动。"""
    try:
        from env_check import get_optional_features_status
        status = get_optional_features_status()
    except Exception:
        return

    if status["all_ready"]:
        return

    print("\n" + "-" * 55)
    print("  可选功能状态")
    print("-" * 55)
    for issue in status["issues"]:
        print(f"  {issue}")
    print("-" * 55)

    # 打印简短安装提示
    any_missing = False
    if not status["marker"]["available"]:
        any_missing = True
    if not status["rat"]["available"]:
        any_missing = True

    if any_missing:
        install_needed = []
        if not status["marker"]["available"]:
            install_needed.append("  uv sync --extra vision    # marker 视觉 PDF 提取")
        if not status["rat"]["available"]:
            install_needed.append("  uv sync --extra rat       # RAT 检索增强翻译")
            if status["rat"]["chromadb_ready"] and not status["rat"]["st_ready"]:
                install_needed.append("  uv run python download_model.py  # 下载嵌入模型")
        print("\n  安装命令:")
        for cmd in install_needed:
            print(f"    {cmd}")
    print("")


_check_env()

# ═══════════════════════════════════════════════════════════
# 高 DPI 修复
# ═══════════════════════════════════════════════════════════

try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except: pass

# ═══════════════════════════════════════════════════════════
# 导入
# ═══════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from tkinter import (
    Tk, Frame, Label, Button, Entry, filedialog, messagebox, Toplevel,
    StringVar, Text, DISABLED, NORMAL, END, WORD,
)
from tkinter.ttk import Progressbar, Combobox

from config import load_config, calc_cost
from extractor import extract_book
from chunker import chunk_text, parse_structure
from translator import translate_chapter
from assembler import assemble_translations, assemble_book
from consistency import ConsistencyModel

# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

BG="#fff"; FG="#111"; GRAY="#888"; LGRAY="#e8e8e8"; LLGRAY="#f4f4f4"; ACC="#111"
FONT=("Microsoft YaHei UI",9); FB=("Microsoft YaHei UI",9,"bold")
FT=("Microsoft YaHei UI",14,"bold"); FS=("Microsoft YaHei UI",7); FM=("Consolas",9)

MODELS = {
    "DeepSeek V4 Pro":   {"model":"deepseek-v4-pro","base":"https://api.deepseek.com/v1"},
    "DeepSeek V4 Flash": {"model":"deepseek-v4-flash","base":"https://api.deepseek.com/v1"},
}
CUSTOM_MODEL = {"model":"", "base":"", "key":""}


def call_api(cfg, sp, up, max_tokens=8192):
    import urllib.request
    key = cfg.get("api_key","") or os.environ.get("DEEPSEEK_API_KEY","")
    if not key: raise ValueError("未设置 API Key")
    payload = json.dumps({
        "model":cfg.get("model","deepseek-v4-pro"),
        "messages":[{"role":"system","content":sp},{"role":"user","content":up}],
        "temperature":cfg.get("temperature",0.3),"max_tokens":max_tokens,"stream":False
    }).encode()
    req = urllib.request.Request(f"{cfg.get('api_base','https://api.deepseek.com/v1')}/chat/completions",
        data=payload,headers={"Content-Type":"application/json","Authorization":f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
        return d["choices"][0]["message"]["content"].strip(),{
            "prompt_tokens":d.get("usage",{}).get("prompt_tokens",0),
            "completion_tokens":d.get("usage",{}).get("completion_tokens",0)}

# ═══════════════════════════════════════════════════════════
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Itranslation")
        self.root.geometry("1040x700"); self.root.minsize(880,540)
        self.root.configure(bg=BG)

        self.input_path = StringVar()
        self.output_dir = StringVar(value=str(PROJECT_ROOT/"final"))
        self.genre_var = StringVar(value="auto")
        self.fmt_var = StringVar(value="txt")
        self.model_var = StringVar(value="DeepSeek V4 Pro")
        self.api_key_var = StringVar()
        self.extract_var = StringVar(value="fitz (文本, 快速)")
        self.running = False; self.paused = False
        self._pause_event = __import__("threading").Event(); self._pause_event.set()
        self._start_time = 0.0
        self._timer_id = None
        self.output_file = None

        self._load_settings()
        self._build()

    def _load_settings(self):
        try: self.api_key_var.set(load_config().get("api_key",""))
        except: pass

    def _build(self):
        pw = Frame(self.root, bg=BG); pw.pack(fill="both", expand=True)
        left = Frame(pw, bg=BG, width=320, padx=12, pady=10)
        left.pack(side="left", fill="y"); left.pack_propagate(False)
        self._left(left)
        right = Frame(pw, bg=BG); right.pack(side="left", fill="both", expand=True)
        right.grid_rowconfigure(0,weight=1); right.grid_rowconfigure(1,weight=1); right.grid_columnconfigure(0,weight=1)
        pr=Frame(right,bg=BG); pr.grid(row=0,column=0,sticky="nsew"); self._preview(pr)
        or_=Frame(right,bg=BG); or_.grid(row=1,column=0,sticky="nsew"); self._output(or_)

    def _left(self, p):
        Label(p,text="Itranslation",font=FT,fg=ACC,bg=BG).pack(anchor="w")
        Label(p,text="AI 全书翻译  ·  DeepSeek V4  ·  中文输出",font=FS,fg=GRAY,bg=BG).pack(anchor="w",pady=(0,8))

        Label(p,text="输入文件",font=FB,fg=ACC,bg=BG).pack(anchor="w")
        r=Frame(p,bg=BG);r.pack(fill="x",pady=(2,0))
        Entry(r,textvariable=self.input_path,font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=5).pack(side="left",fill="x",expand=True)
        Button(r,text="…",command=self._pick_input,font=FONT,bg=LGRAY,relief="flat",padx=6,cursor="hand2").pack(side="left",padx=(3,0))

        Label(p,text="输出目录",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        r2=Frame(p,bg=BG);r2.pack(fill="x",pady=(2,0))
        Entry(r2,textvariable=self.output_dir,font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=5).pack(side="left",fill="x",expand=True)
        Button(r2,text="…",command=self._pick_output,font=FONT,bg=LGRAY,relief="flat",padx=6,cursor="hand2").pack(side="left",padx=(3,0))

        Label(p,text="体裁",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        Combobox(p,textvariable=self.genre_var,state="readonly",font=FM,
                 values=["auto","literature","philosophy","natural_science","social_science","technical"],width=18).pack(fill="x",pady=(2,0))

        Label(p,text="PDF 提取",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        Combobox(p,textvariable=self.extract_var,state="readonly",font=FM,
                 values=["fitz (文本, 快速)","marker (视觉, 90%+ 精度)"],width=22).pack(fill="x",pady=(2,0))

        Label(p,text="翻译模型",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        mr=Frame(p,bg=BG);mr.pack(fill="x",pady=(2,0))
        Combobox(mr,textvariable=self.model_var,state="readonly",font=FM,
                 values=list(MODELS.keys())+["自定义..."],width=20).pack(side="left",fill="x",expand=True)
        Button(mr,text="⚙",command=self._custom_model,font=FB,bg=LGRAY,relief="flat",padx=8,pady=2,cursor="hand2").pack(side="left",padx=(4,0))

        Label(p,text="API Key",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        Entry(p,textvariable=self.api_key_var,show="•",font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=5).pack(fill="x",pady=(2,0))

        Label(p,text="输出格式",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        Combobox(p,textvariable=self.fmt_var,state="readonly",font=FM,values=["txt","md","pdf","epub"],width=18).pack(fill="x",pady=(2,0))

        br=Frame(p,bg=BG);br.pack(fill="x",pady=(14,6))
        self.btn=Button(br,text="开始翻译",command=self._start,font=FB,bg=ACC,fg="#fff",relief="flat",padx=12,pady=5,cursor="hand2")
        self.btn.pack(side="left",fill="x",expand=True)
        self.pause_btn=Button(br,text="⏸",command=self._toggle_pause,font=FB,bg=LGRAY,relief="flat",padx=8,pady=5,cursor="hand2",state=DISABLED)
        self.pause_btn.pack(side="left",padx=(4,0))

        self.phase_lbl=Label(p,text="就绪",font=FONT,fg=GRAY,bg=BG,anchor="w");self.phase_lbl.pack(fill="x")
        self.bar=Progressbar(p,mode="determinate");self.bar.pack(fill="x",pady=(3,1))
        self.pct_lbl=Label(p,text="—",font=FS,fg=GRAY,bg=BG);self.pct_lbl.pack(anchor="e")
        self.time_lbl=Label(p,text="",font=FS,fg=GRAY,bg=BG);self.time_lbl.pack(anchor="e")
        self.result_lbl=Label(p,text="",font=FONT,fg=ACC,bg=BG,anchor="w",wraplength=290)
        self.result_lbl.pack(fill="x",pady=(8,0))
        self.open_btn=Button(p,text="打开译文",command=self._open,font=FONT,bg=LGRAY,relief="flat",padx=10,pady=2,cursor="hand2")

        # 底部状态栏
        sf = Frame(p, bg="#eef2f5", height=26)
        sf.pack(side="bottom", fill="x", pady=(12, 0))
        sf.pack_propagate(False)
        self.status_lbl = Label(sf, text="● 就绪", font=("Microsoft YaHei UI", 8),
                                fg="#8a8a8a", bg="#eef2f5", anchor="w", padx=8)
        self.status_lbl.pack(fill="both", expand=True)

    def _set_status(self, text, color="#8a8a8a"):
        self.status_lbl.configure(text=text, fg=color)

    def _custom_model(self):
        dlg=Toplevel(self.root); dlg.title("自定义模型"); dlg.geometry("420x280"); dlg.configure(bg=BG)
        dlg.transient(self.root); dlg.grab_set()
        Label(dlg,text="自定义 API 配置",font=FB,fg=ACC,bg=BG).pack(pady=(12,4))
        fields=[("API Base URL","base","https://api.openai.com/v1"),("Model Name","model","gpt-4o"),("API Key","key",CUSTOM_MODEL.get("key",""))]
        entries={}
        for label,key,default in fields:
            Label(dlg,text=label,font=FONT,fg=GRAY,bg=BG).pack(anchor="w",padx=20,pady=(8,0))
            v=StringVar(value=CUSTOM_MODEL.get(key,"") or default); entries[key]=v
            Entry(dlg,textvariable=v,show="*" if key=="key" else "",font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=5).pack(fill="x",padx=20,pady=(2,0))
        def save():
            for k,v in entries.items(): CUSTOM_MODEL[k]=v.get()
            self.model_var.set("自定义..."); dlg.destroy()
        Button(dlg,text="保存",command=save,font=FB,bg=ACC,fg="#fff",relief="flat",padx=16,pady=4,cursor="hand2").pack(pady=(14,0))

    def _preview(self,p):
        Label(p,text="原文预览",font=FB,fg=ACC,bg=BG).pack(anchor="w",padx=10,pady=(6,2))
        self.pv=Text(p,font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=6,wrap=WORD,state=DISABLED,padx=8,pady=6)
        self.pv.pack(fill="both",expand=True,padx=6,pady=(0,4))
    def _output(self,p):
        Label(p,text="译文输出",font=FB,fg=ACC,bg=BG).pack(anchor="w",padx=10,pady=(6,2))
        self.ov=Text(p,font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=6,wrap=WORD,state=DISABLED,padx=8,pady=6)
        self.ov.pack(fill="both",expand=True,padx=6,pady=(0,4))
    def _pick_input(self):
        p=filedialog.askopenfilename(title="选择书籍",filetypes=[("支持格式","*.pdf *.epub *.txt *.md")])
        if p: self.input_path.set(p); self._show_preview(p)
    def _pick_output(self):
        d=filedialog.askdirectory(title="输出目录")
        if d: self.output_dir.set(d)
    def _show_preview(self,path=None):
        path=path or self.input_path.get()
        if not path or not Path(path).exists(): return
        try:
            t=extract_book(path,use_vision=False)
            self._set(self.pv,t[:8000]+(f"\n\n… (共 {len(t):,} 字符)" if len(t)>8000 else ""))
        except Exception as e: self._set(self.pv,f"[预览失败] {e}")
    def _set(self,w,text):
        w.configure(state=NORMAL); w.delete("1.0",END); w.insert("1.0",text); w.configure(state=DISABLED)
    def _update_ui(self,phase,done,total):
        self.root.after(0,lambda:self.phase_lbl.configure(text=phase))
        self.root.after(0,lambda:self.bar.configure(maximum=max(total,1)))
        self.root.after(0,lambda:self.bar.configure(value=done))
        self.root.after(0,lambda:self.pct_lbl.configure(text=f"{done} / {total}"))
        self._set_status(phase, "#111")
    def _update_timer(self):
        """更新计时器显示（已用时间 + 预估剩余时间）。每秒调用一次。"""
        if not self.running or self._start_time == 0:
            return
        elapsed = time.time() - self._start_time
        elapsed_str = f"{int(elapsed//60)}:{int(elapsed%60):02d}"
        text = f"⏱ {elapsed_str}"
        # 如果有进度，计算 ETA
        done = self.bar.cget("value")
        total = self.bar.cget("maximum")
        if done > 0 and total > 0 and done < total:
            eta = elapsed / done * (total - done)
            eta_str = f"{int(eta//60)}:{int(eta%60):02d}"
            text += f"  |  剩余 ~{eta_str}"
        self.time_lbl.configure(text=text)
        self._timer_id = self.root.after(1000, self._update_timer)

    def _start_timer(self):
        self._start_time = time.time()
        self._update_timer()

    def _stop_timer(self):
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
    def _toggle_pause(self):
        if not self.running: return
        self.paused=not self.paused
        if self.paused: self._pause_event.clear(); self.pause_btn.configure(text="▶"); self.phase_lbl.configure(text="⏸ 已暂停 — 点击 ▶ 继续"); self._set_status("⏸ 已暂停", "#d97706")
        else: self._pause_event.set(); self.pause_btn.configure(text="⏸"); self.phase_lbl.configure(text="翻译中..."); self._set_status("● 翻译中...", "#111")
    def _start(self):
        if self.running: return
        path=self.input_path.get()
        if not path or not Path(path).exists(): messagebox.showerror("错误","请选择文件"); return
        if not self.api_key_var.get().strip(): messagebox.showerror("错误","请输入 API Key"); return
        self.running=True;self.paused=False;self._pause_event.set()
        self.btn.configure(text="翻译中...",state=DISABLED);self.pause_btn.configure(state=NORMAL,text="⏸")
        self.open_btn.pack_forget();self.result_lbl.configure(text="");self._set(self.ov,"")
        self._set_status("● 翻译中...", "#111")
        self._start_timer()
        threading.Thread(target=self._run,args=(path,),daemon=True).start()

    def _checkpoint_path(self, book_path):
        """为每本书生成唯一 checkpoint 路径。"""
        h = hashlib.md5(str(Path(book_path).resolve()).encode()).hexdigest()[:12]
        name = Path(book_path).stem
        return os.path.join(PROJECT_ROOT, "cache", f"gui_checkpoint_{name}_{h}.json")

    def _save_checkpoint(self, ckpt_path, data):
        Path(ckpt_path).parent.mkdir(parents=True, exist_ok=True)
        with open(ckpt_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_checkpoint(self, ckpt_path):
        try:
            with open(ckpt_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _ask_resume(self, ckpt):
        """询问用户是否恢复断点。在后台线程调用，需要用 after 回到主线程。"""
        result = {"resume": False}
        event = threading.Event()
        def ask():
            try:
                completed = ckpt.get("completed_chapters", [])
                ans = messagebox.askyesno(
                    "断点续传",
                    f"发现上次中断的翻译进度。\n\n"
                    f"已完成 {len(completed)} 章 ({', '.join(completed)})\n"
                    f"是否从断点继续？"
                )
                result["resume"] = ans
            finally:
                event.set()
        self.root.after(0, ask)
        event.wait()
        return result["resume"]

    def _run(self, path):
        try:
            cfg = load_config()
            use_custom = self.model_var.get() == "自定义..."
            if use_custom:
                cfg["api_base"] = CUSTOM_MODEL["base"]; cfg["model"] = CUSTOM_MODEL["model"]
                if CUSTOM_MODEL.get("key"): cfg["api_key"] = CUSTOM_MODEL["key"]
                else: cfg["api_key"] = self.api_key_var.get().strip()
            else:
                md = MODELS.get(self.model_var.get(), MODELS["DeepSeek V4 Pro"])
                cfg["model"] = md["model"]; cfg["api_base"] = md["base"]; cfg["api_key"] = self.api_key_var.get().strip()
            genre = self.genre_var.get() or "literature"
            ov = cfg["overlap_by_genre"].get(genre, 3)
            use_marker = "marker" in self.extract_var.get()

            # 文件大小检查
            size_mb = Path(path).stat().st_size / (1024 * 1024)
            max_warn = cfg.get("max_input_file_mb", 100)
            max_abort = cfg.get("max_input_file_mb_abort", 500)
            if size_mb > max_abort:
                raise ValueError(f"文件过大: {size_mb:.0f} MB > {max_abort} MB 限制")

            # --- 断点检查 ---
            ckpt_path = self._checkpoint_path(path)
            ckpt = self._load_checkpoint(ckpt_path)
            resume_from = {}
            if ckpt:
                if not self._ask_resume(ckpt):
                    ckpt = {}  # 用户选择不恢复
                else:
                    resume_from = {t["title"]: t for t in ckpt.get("translations", [])}
                    resumed_chaps = set(ckpt.get("completed_chapters", []))
                    cost_so_far = ckpt.get("_cost", {"prompt_tokens": 0, "completion_tokens": 0})

            # --- Phase 0: 提取 ---
            if not ckpt or not ckpt.get("chapters"):
                self._update_ui("Phase 0/4 提取", 0, 1)
                self._set_status("提取 → 读取文件中...", "#2563eb")
                md_text = extract_book(path, use_vision=use_marker,
                                       max_mb=max_warn, max_mb_abort=max_abort)
                self._set_status("提取 → 解析章节结构...", "#2563eb")
                chapters = parse_structure(md_text)
                self._set_status(f"提取完成 — {len(md_text):,} 字符, {len(chapters)} 章", "#16a34a")
            else:
                chapters = ckpt["chapters"]
                md_text = None

            # --- Phase 1: 分块 ---
            self._update_ui("Phase 1/4 分块", 0, 1)
            all_chapter_data = []
            for i, ch in enumerate(chapters):
                self._set_status(f"分块 → {ch['title']} ({i+1}/{len(chapters)})", "#2563eb")
                ct = "\n\n".join(ch.get("paragraphs", []))
                if ct.strip():
                    cks = chunk_text(ct,
                                     target_tokens=cfg.get("chunk_target_tokens", 1500),
                                     max_tokens=cfg.get("chunk_max_tokens", 3000),
                                     overlap_sentences=ov)
                    all_chapter_data.append((ch["title"], cks, ct))
            total = sum(len(c) for _, c, _ in all_chapter_data)
            self._set_status(f"分块完成 — {len(all_chapter_data)} 章, {total} 块", "#16a34a")

            # --- Phase 2: 翻译（并行） ---
            workers = cfg.get("parallel_workers", 4)
            mode_str = f"并行 ×{workers}" if (workers > 1 and len(all_chapter_data) > 1) else "串行"
            self._update_ui(f"Phase 2/4 翻译 ({mode_str})", 0, total)

            # 共享状态
            cost_lock = threading.Lock()
            total_cost = {"prompt_tokens": cost_so_far.get("prompt_tokens", 0) if resume_from else 0,
                          "completion_tokens": cost_so_far.get("completion_tokens", 0) if resume_from else 0}
            done_count = [0]; chapter_done = [len(resumed_chaps) if resume_from else 0]
            done_lock = threading.Lock()
            active_chapters = set()  # 正在处理的章节标题
            active_lock = threading.Lock()
            total_chapters = len(all_chapter_data)
            failed = []

            def _status_phase2():
                """生成 Phase 2 状态文字。"""
                with done_lock:
                    cd = chapter_done[0]
                    dc = done_count[0]
                with active_lock:
                    active_list = sorted(active_chapters)[:5]
                    active_str = ", ".join(active_list) if active_list else "—"
                return (f"翻译 → {cd}/{total_chapters} 章完成 ({dc}/{total} 块)"
                        f" | 处理中: {active_str}")

            def translate_one_chapter(title, cks, ct):
                """翻译单个章节（在子线程中运行）。"""
                nonlocal failed
                # 断点恢复：检测已完成的章节
                if resume_from and title in resumed_chaps:
                    prev = resume_from[title]
                    with cost_lock:
                        total_cost["prompt_tokens"] += prev.get("_pt", 0)
                        total_cost["completion_tokens"] += prev.get("_ct", 0)
                    with done_lock:
                        done_count[0] += len(cks)
                        chapter_done[0] += 1
                        self._update_ui(
                            f"Phase 2/4 翻译 ({mode_str})", done_count[0], total)
                        self._set_status(_status_phase2(), "#2563eb")
                    return (title, cks, prev["trans"], ct, prev.get("_pt", 0), prev.get("_ct", 0))

                # 加入活跃列表
                with active_lock:
                    active_chapters.add(title)
                    self._set_status(_status_phase2(), "#2563eb")

                # 每个线程独立的 consistency model
                cm = ConsistencyModel()
                def llm(sp, up):
                    while self.paused and self.running:
                        time.sleep(0.3)
                    if not self.running:
                        raise RuntimeError("翻译已取消")
                    return call_api(cfg, sp, up, max_tokens=cfg.get("max_tokens_per_chunk", 8192))

                trans = translate_chapter(title, cks, None, cm, {}, {}, llm, cfg)
                pt = cfg.get("_cost", {}).get("prompt_tokens", 0)
                ct_tok = cfg.get("_cost", {}).get("completion_tokens", 0)

                with cost_lock:
                    total_cost["prompt_tokens"] += pt
                    total_cost["completion_tokens"] += ct_tok
                with done_lock:
                    done_count[0] += len(cks)
                    chapter_done[0] += 1
                with active_lock:
                    active_chapters.discard(title)
                    self._update_ui(
                        f"Phase 2/4 翻译 ({mode_str})", done_count[0], total)
                    self._set_status(_status_phase2(), "#2563eb")
                return (title, cks, trans, ct, pt, ct_tok)

            all_trans = []
            completed_chapters = list(resumed_chaps) if resume_from else []

            # 过滤已完成的章节
            pending = [(t, c, ct) for t, c, ct in all_chapter_data
                       if t not in (resumed_chaps if resume_from else set())]

            if workers <= 1 or len(pending) <= 1:
                # 串行模式
                for title, cks, ct in pending:
                    if not self.running:
                        return
                    result = translate_one_chapter(title, cks, ct)
                    all_trans.append(result)
                    completed_chapters.append(title)
                    # 保存断点
                    self._save_checkpoint(ckpt_path, {
                        "book_path": str(Path(path).resolve()),
                        "chapters": chapters,
                        "completed_chapters": completed_chapters,
                        "translations": [
                            {"title": t, "trans": tr, "_pt": pt, "_ct": ct2}
                            for t, _, tr, _, pt, ct2 in all_trans
                        ],
                        "_cost": total_cost,
                    })
            else:
                # 并行模式
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {pool.submit(translate_one_chapter, t, c, ct): t
                               for t, c, ct in pending}
                    for fut in as_completed(futures):
                        if not self.running:
                            pool.shutdown(wait=False, cancel_futures=True)
                            return
                        try:
                            result = fut.result()
                            all_trans.append(result)
                            completed_chapters.append(result[0])
                        except Exception as e:
                            failed.append((futures[fut], str(e)))
                        # 保存断点
                        self._save_checkpoint(ckpt_path, {
                            "book_path": str(Path(path).resolve()),
                            "chapters": chapters,
                            "completed_chapters": completed_chapters,
                            "translations": [
                                {"title": t, "trans": tr, "_pt": pt, "_ct": ct2}
                                for t, _, tr, _, pt, ct2 in all_trans
                            ],
                            "_cost": total_cost,
                        })

            if failed:
                raise RuntimeError(f"{len(failed)} 章翻译失败: " + "; ".join(
                    f"{t}: {e}" for t, e in failed))

            # --- Phase 3: 组装 ---
            self._update_ui("Phase 3/4 组装", total, total)
            self._set_status("组装 → 去重叠合并...", "#2563eb")
            oname = f"{Path(path).stem}_translation"
            odir = self.output_dir.get() or str(PROJECT_ROOT / "final")
            opath = os.path.join(odir, oname)
            Path(odir).mkdir(parents=True, exist_ok=True)
            full = [(t, assemble_translations(c, tr, "first_lock"))
                    for t, c, tr, _, _, _ in all_trans]
            output_fmt = self.fmt_var.get()
            fmt_names = {"txt": "TXT", "md": "Markdown", "pdf": "PDF", "epub": "EPUB"}
            self._set_status(f"组装 → 写入 {fmt_names.get(output_fmt, output_fmt)}...", "#2563eb")
            assemble_book(full, opath, fmt=output_fmt)
            # 根据输出格式确定实际文件路径
            ext_map = {"txt": ".txt", "md": ".md", "pdf": ".pdf", "epub": ".epub"}
            actual_path = opath + ext_map.get(output_fmt, ".txt")

            # 成本计算
            pt = total_cost["prompt_tokens"]; ct_val = total_cost["completion_tokens"]
            model_name = cfg.get("model", "")
            cost_val, cost_str = calc_cost(model_name if not use_custom else "", pt, ct_val)

            self.root.after(0, lambda: self._set(self.ov,
                "\n\n".join(txt for _, txt in full)[:10000]))
            self.output_file = actual_path
            self.root.after(0, lambda: self._done(oname, cost_str))

            # 翻译完成，清理 checkpoint
            try:
                os.remove(ckpt_path)
            except Exception:
                pass

        except Exception as e:
            self.root.after(0, lambda: self._fail(str(e)))

    def _done(self, n, cost_str):
        self._stop_timer()
        elapsed = time.time() - self._start_time
        dur = f"{int(elapsed//60)}:{int(elapsed%60):02d}"
        self.running = False; self.paused = False
        self.btn.configure(text="开始翻译", state=NORMAL)
        self.pause_btn.configure(state=DISABLED, text="⏸")
        self.phase_lbl.configure(text="翻译完成")
        self._set_status("✓ 翻译完成", "#16a34a")
        self.result_lbl.configure(text=f"{n}\n{cost_str}\n用时 {dur}")
        self.open_btn.pack(pady=(4, 0))

    def _fail(self, msg):
        self._stop_timer()
        self.running=False;self.paused=False;self.btn.configure(text="开始翻译",state=NORMAL)
        self.pause_btn.configure(state=DISABLED,text="⏸");self.phase_lbl.configure(text=f"失败: {msg}")
        self._set_status(f"✗ {msg}", "#dc2626")
    def _open(self):
        if self.output_file and Path(self.output_file).exists(): os.startfile(self.output_file)

if __name__=="__main__":
    root = Tk()
    App(root)
    root.mainloop()

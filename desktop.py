"""
book-translation Desktop GUI v4.1
- PDF 提取: marker 视觉 / PyMuPDF 文本 切换
- 暂停 / 恢复
- 多模型切换 (DeepSeek / OpenAI / Claude / 自定义)
- 自定义模型弹窗: API Base + Model Name + Key
- 输出格式: TXT / MD / PDF

启动: uv run python desktop.py
"""

import ctypes, json, os, sys, threading, time, traceback
from pathlib import Path

try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except: pass

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from tkinter import (
    Tk, Frame, Label, Button, Entry, filedialog, messagebox, Toplevel,
    StringVar, IntVar, Text, DISABLED, NORMAL, END, WORD, W, E,
)
from tkinter.ttk import Progressbar, Combobox

from config import load_config
from extractor import extract_book
from chunker import chunk_text, parse_structure
from translator import translate_chapter
from assembler import assemble_translations, assemble_book
from consistency import ConsistencyModel

BG="#fff";FG="#111";GRAY="#888";LGRAY="#e8e8e8";LLGRAY="#f4f4f4";ACC="#111"
FONT=("Microsoft YaHei UI",9);FB=("Microsoft YaHei UI",9,"bold")
FT=("Microsoft YaHei UI",14,"bold");FS=("Microsoft YaHei UI",7);FM=("Consolas",9)

MODELS = {
    "DeepSeek V4 Pro":    {"model":"deepseek-v4-pro","base":"https://api.deepseek.com/v1"},
    "DeepSeek V4 Flash":  {"model":"deepseek-v4-flash","base":"https://api.deepseek.com/v1"},
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


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("book-translation")
        self.root.geometry("1040x700"); self.root.minsize(880,540)
        self.root.configure(bg=BG)

        self.input_path = StringVar()
        self.output_dir = StringVar(value=str(PROJECT_ROOT/"final"))
        self.genre_var = StringVar(value="auto")
        self.fmt_var = StringVar(value="txt")
        self.model_var = StringVar(value="DeepSeek V4 Pro")
        self.api_key_var = StringVar()
        self.extract_var = StringVar(value="marker (视觉, 90%+ 精度)")
        self.running = False
        self.paused = False
        self._pause_event = threading.Event(); self._pause_event.set()
        self.output_file = None

        self._load_settings()
        self._build()

    def _load_settings(self):
        try:
            cfg=load_config()
            self.api_key_var.set(cfg.get("api_key",""))
        except: pass

    def _build(self):
        pw = Frame(self.root, bg=BG); pw.pack(fill="both", expand=True)
        left = Frame(pw, bg=BG, width=320, padx=12, pady=10)
        left.pack(side="left", fill="y"); left.pack_propagate(False)
        self._left(left)
        right = Frame(pw, bg=BG); right.pack(side="left", fill="both", expand=True)
        right.grid_rowconfigure(0,weight=1); right.grid_rowconfigure(1,weight=1)
        right.grid_columnconfigure(0,weight=1)
        pr=Frame(right,bg=BG); pr.grid(row=0,column=0,sticky="nsew"); self._preview(pr)
        or_=Frame(right,bg=BG); or_.grid(row=1,column=0,sticky="nsew"); self._output(or_)

    def _left(self, p):
        Label(p,text="book-translation",font=FT,fg=ACC,bg=BG).pack(anchor="w")
        Label(p,text="AI 全书翻译",font=FS,fg=GRAY,bg=BG).pack(anchor="w",pady=(0,8))

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
                 values=["auto","literature","philosophy","natural_science","social_science","technical"],
                 width=18).pack(fill="x",pady=(2,0))

        Label(p,text="PDF 提取",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        Combobox(p,textvariable=self.extract_var,state="readonly",font=FM,
                 values=["marker (视觉, 90%+ 精度)","fitz (文本, 快速)"],width=22).pack(fill="x",pady=(2,0))

        # 模型 + 自定义按钮
        Label(p,text="翻译模型",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        mr = Frame(p,bg=BG); mr.pack(fill="x",pady=(2,0))
        Combobox(mr,textvariable=self.model_var,state="readonly",font=FM,
                 values=list(MODELS.keys())+["自定义..."],width=20).pack(side="left",fill="x",expand=True)
        Button(mr,text="⚙",command=self._custom_model,font=FB,bg=LGRAY,relief="flat",padx=8,pady=2,cursor="hand2").pack(side="left",padx=(4,0))

        Label(p,text="API Key",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        Entry(p,textvariable=self.api_key_var,show="•",font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=5).pack(fill="x",pady=(2,0))

        Label(p,text="输出格式",font=FB,fg=ACC,bg=BG).pack(anchor="w",pady=(8,0))
        Combobox(p,textvariable=self.fmt_var,state="readonly",font=FM,
                 values=["txt","md","pdf"],width=18).pack(fill="x",pady=(2,0))

        br=Frame(p,bg=BG);br.pack(fill="x",pady=(14,6))
        self.btn=Button(br,text="开始翻译",command=self._start,font=FB,bg=ACC,fg="#fff",
                         relief="flat",padx=12,pady=5,cursor="hand2")
        self.btn.pack(side="left",fill="x",expand=True)
        self.pause_btn=Button(br,text="⏸",command=self._toggle_pause,font=FB,bg=LGRAY,
                               relief="flat",padx=8,pady=5,cursor="hand2",state=DISABLED)
        self.pause_btn.pack(side="left",padx=(4,0))

        self.phase_lbl=Label(p,text="就绪",font=FONT,fg=GRAY,bg=BG,anchor="w");self.phase_lbl.pack(fill="x")
        self.bar=Progressbar(p,mode="determinate");self.bar.pack(fill="x",pady=(3,1))
        self.pct_lbl=Label(p,text="—",font=FS,fg=GRAY,bg=BG);self.pct_lbl.pack(anchor="e")
        self.result_lbl=Label(p,text="",font=FONT,fg=ACC,bg=BG,anchor="w",wraplength=290)
        self.result_lbl.pack(fill="x",pady=(8,0))
        self.open_btn=Button(p,text="打开译文",command=self._open,font=FONT,bg=LGRAY,
                              relief="flat",padx=10,pady=2,cursor="hand2")

    def _custom_model(self):
        """弹出自定义模型设置窗口。"""
        dlg = Toplevel(self.root)
        dlg.title("自定义模型"); dlg.geometry("420x280"); dlg.configure(bg=BG)
        dlg.transient(self.root); dlg.grab_set()

        Label(dlg,text="自定义 API 配置",font=FB,fg=ACC,bg=BG).pack(pady=(12,4))

        fields = [
            ("API Base URL", "base", "https://api.openai.com/v1"),
            ("Model Name", "model", "gpt-4o"),
            ("API Key", "key", CUSTOM_MODEL.get("key","")),
        ]
        entries = {}
        for label, key, default in fields:
            Label(dlg,text=label,font=FONT,fg=GRAY,bg=BG).pack(anchor="w",padx=20,pady=(8,0))
            show = "*" if key=="key" else ""
            v=StringVar(value=CUSTOM_MODEL.get(key,"") or default)
            entries[key]=v
            Entry(dlg,textvariable=v,show=show,font=FM,bg=LLGRAY,fg=FG,
                  relief="flat",bd=5).pack(fill="x",padx=20,pady=(2,0))

        def save():
            for k, v in entries.items():
                CUSTOM_MODEL[k] = v.get()
            self.model_var.set("自定义...")
            dlg.destroy()

        Button(dlg,text="保存",command=save,font=FB,bg=ACC,fg="#fff",
               relief="flat",padx=16,pady=4,cursor="hand2").pack(pady=(14,0))

    def _preview(self,parent):
        Label(parent,text="原文预览",font=FB,fg=ACC,bg=BG).pack(anchor="w",padx=10,pady=(6,2))
        self.pv=Text(parent,font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=6,wrap=WORD,
                      state=DISABLED,padx=8,pady=6)
        self.pv.pack(fill="both",expand=True,padx=6,pady=(0,4))

    def _output(self,parent):
        Label(parent,text="译文输出",font=FB,fg=ACC,bg=BG).pack(anchor="w",padx=10,pady=(6,2))
        self.ov=Text(parent,font=FM,bg=LLGRAY,fg=FG,relief="flat",bd=6,wrap=WORD,
                      state=DISABLED,padx=8,pady=6)
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
            pre=t[:8000]+(f"\n\n… (共 {len(t):,} 字符)" if len(t)>8000 else "")
            self._set(self.pv,pre)
        except Exception as e: self._set(self.pv,f"[预览失败] {e}")
    def _set(self,w,text):
        w.configure(state=NORMAL);w.delete("1.0",END);w.insert("1.0",text);w.configure(state=DISABLED)
    def _update_ui(self,phase,done,total):
        self.root.after(0,lambda:self.phase_lbl.configure(text=phase))
        self.root.after(0,lambda:self.bar.configure(maximum=max(total,1)))
        self.root.after(0,lambda:self.bar.configure(value=done))
        self.root.after(0,lambda:self.pct_lbl.configure(text=f"{done} / {total}"))
    def _toggle_pause(self):
        if not self.running: return
        self.paused=not self.paused
        if self.paused: self._pause_event.clear(); self.pause_btn.configure(text="▶"); self.phase_lbl.configure(text="⏸ 已暂停 — 点击 ▶ 继续")
        else: self._pause_event.set(); self.pause_btn.configure(text="⏸"); self.phase_lbl.configure(text="翻译中...")
    def _start(self):
        if self.running: return
        path=self.input_path.get()
        if not path or not Path(path).exists(): messagebox.showerror("错误","请选择文件"); return
        if not self.api_key_var.get().strip(): messagebox.showerror("错误","请输入 API Key"); return
        self.running=True;self.paused=False;self._pause_event.set()
        self.btn.configure(text="翻译中...",state=DISABLED)
        self.pause_btn.configure(state=NORMAL,text="⏸")
        self.open_btn.pack_forget();self.result_lbl.configure(text="")
        self._set(self.ov,"")
        threading.Thread(target=self._run,args=(path,),daemon=True).start()
    def _run(self,path):
        try:
            cfg=load_config()
            use_custom = self.model_var.get()=="自定义..."
            if use_custom:
                cfg["api_base"]=CUSTOM_MODEL["base"]
                cfg["model"]=CUSTOM_MODEL["model"]
                if CUSTOM_MODEL.get("key"): cfg["api_key"]=CUSTOM_MODEL["key"]
                else: cfg["api_key"]=self.api_key_var.get().strip()
            else:
                md=MODELS.get(self.model_var.get(),MODELS["DeepSeek V4 Pro"])
                cfg["model"]=md["model"];cfg["api_base"]=md["base"]
                cfg["api_key"]=self.api_key_var.get().strip()

            genre=self.genre_var.get() or "literature"
            ov=cfg["overlap_by_genre"].get(genre,3)
            use_marker="marker" in self.extract_var.get()

            self._update_ui("Phase 0: 提取...",0,1)
            md_text=extract_book(path,use_vision=use_marker)
            chapters=parse_structure(md_text)
            self._update_ui("Phase 1: 分块...",0,1)
            all_chunks=[]
            for ch in chapters:
                ct="\n\n".join(ch.get("paragraphs",[]))
                if ct.strip():
                    cks=chunk_text(ct,target_tokens=cfg.get("chunk_target_tokens",1500),
                                   max_tokens=cfg.get("chunk_max_tokens",3000),overlap_sentences=ov)
                    all_chunks.append((ch["title"],cks,ct))
            total=sum(len(c) for _,c,_ in all_chunks)
            self._update_ui("Phase 2: 翻译...",0,total)
            cm=ConsistencyModel()
            def llm(sp,up): return call_api(cfg,sp,up,max_tokens=cfg.get("max_tokens_per_chunk",8192))
            all_trans,done=[],0
            for title,cks,ct in all_chunks:
                trans=translate_chapter(title,cks,None,cm,{},{},llm,cfg)
                all_trans.append((title,cks,trans,ct)); done+=len(cks)
                self._update_ui(f"Phase 2: 翻译...",done,total)
                while self.paused and self.running: time.sleep(0.3)
                if not self.running: return
            self._update_ui("Phase 3: 组装...",total,total)
            oname=f"{Path(path).stem}_translation"
            odir=self.output_dir.get() or str(PROJECT_ROOT/"final")
            opath=os.path.join(odir,oname);Path(odir).mkdir(parents=True,exist_ok=True)
            full=[(t,assemble_translations(c,tr,"first_lock")) for t,c,tr,_ in all_trans]
            assemble_book(full,opath,fmt=self.fmt_var.get())
            cost=cfg.get("_cost",{});pt=cost.get("prompt_tokens",0);ct2=cost.get("completion_tokens",0)
            tc=pt/1e6*0.435+ct2/1e6*0.87
            final_text="\n\n".join(txt for _,txt in full)
            self.root.after(0,lambda:self._set(self.ov,final_text[:10000]))
            self.output_file=opath
            self.root.after(0,lambda:self._done(oname,tc,pt,ct2))
        except Exception as e:
            self.root.after(0,lambda:self._fail(str(e)))
    def _done(self,name,cost,pt,ct):
        self.running=False;self.paused=False;self.btn.configure(text="开始翻译",state=NORMAL)
        self.pause_btn.configure(state=DISABLED,text="⏸")
        self.phase_lbl.configure(text="翻译完成")
        self.result_lbl.configure(text=f"{name}\n{pt:,}+{ct:,} tokens · ${cost:.4f} (~¥{cost*7.2:.2f})")
        self.open_btn.pack(pady=(4,0))
    def _fail(self,msg):
        self.running=False;self.paused=False;self.btn.configure(text="开始翻译",state=NORMAL)
        self.pause_btn.configure(state=DISABLED,text="⏸");self.phase_lbl.configure(text=f"失败: {msg}")
    def _open(self):
        if self.output_file and Path(self.output_file).exists(): os.startfile(self.output_file)


if __name__=="__main__":
    root = Tk()
    App(root)
    root.mainloop()

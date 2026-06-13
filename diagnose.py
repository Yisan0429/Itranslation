"""
Itranslation GUI 诊断工具
运行: uv run python diagnose.py
"""
import sys, os, json, time, traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 55)
print("  Itranslation GUI 诊断")
print("=" * 55)

# 1. Python
print(f"\n1. Python: {sys.version}")

# 2. Dependencies
for mod, name in [("tkinter", "tkinter"), ("fitz", "pymupdf"), ("rich", "rich"),
                   ("nltk", "nltk"), ("tenacity", "tenacity")]:
    try:
        __import__(mod)
        print(f"   ✓ {name}")
    except ImportError:
        print(f"   ✗ {name} MISSING")

# 3. Config
cfg_path = PROJECT_ROOT / "config.json"
print(f"\n2. Config: {'✓' if cfg_path.exists() else '✗ MISSING'}")
if cfg_path.exists():
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        has_key = bool(cfg.get("api_key", "").strip())
        print(f"   API Key: {'✓' if has_key else '✗ EMPTY'}")
        print(f"   Model: {cfg.get('model', '?')}")
    except Exception as e:
        print(f"   ✗ Parse error: {e}")

# 4. API connectivity
print(f"\n3. API connectivity test...")
try:
    import urllib.request, socket
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        key = cfg.get("api_key", "")
        if key:
            payload = json.dumps({
                "model": cfg.get("model", "deepseek-v4-pro"),
                "messages": [{"role": "user", "content": "Say 'OK' in one word."}],
                "max_tokens": 10, "temperature": 0, "stream": False
            }).encode()
            url = f"{cfg.get('api_base', 'https://api.deepseek.com/v1')}/chat/completions"
            req = urllib.request.Request(url, data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
            socket.setdefaulttimeout(30)
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read())
            elapsed = time.time() - t0
            content = d["choices"][0]["message"]["content"].strip()
            print(f"   ✓ {elapsed:.1f}s — response: '{content}'")
        else:
            print("   ⚠ SKIP (no API key)")
    else:
        print("   ⚠ SKIP (no config)")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

# 5. Pipeline
print(f"\n4. Pipeline (extract → chunk → translate)...")
try:
    from extractor import extract_book
    from chunker import chunk_text, parse_structure
    from translator import translate_chapter
    from consistency import ConsistencyModel
    from config import load_config

    cfg = load_config()
    test_file = PROJECT_ROOT / "input" / "test.txt"
    if not test_file.exists():
        # Create minimal test
        test_file.write_text("Hello world. This is a test.", encoding="utf-8")

    md = extract_book(str(test_file), use_vision=False)
    chapters = parse_structure(md)
    print(f"   Extract: {len(md)} chars, {len(chapters)} chapters ✓")

    all_data = []
    for ch in chapters:
        ct = "\n\n".join(ch.get("paragraphs", []))
        if ct.strip():
            cks = chunk_text(ct, target_tokens=1500, max_tokens=3000, overlap_sentences=3)
            all_data.append((ch["title"], cks, ct))
    print(f"   Chunk: {len(all_data)} chapters, {sum(len(c) for _,c,_ in all_data)} chunks ✓")

    if all_data and cfg.get("api_key"):
        cm = ConsistencyModel()
        title, cks, ct = all_data[0]

        import urllib.request as ur
        def llm(sp, up):
            key = cfg["api_key"]
            payload = json.dumps({
                "model": cfg.get("model", "deepseek-v4-pro"),
                "messages": [{"role": "system", "content": sp}, {"role": "user", "content": up}],
                "temperature": 0.3, "max_tokens": 8192, "stream": False
            }).encode()
            url = f"{cfg.get('api_base', 'https://api.deepseek.com/v1')}/chat/completions"
            req = ur.Request(url, data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
            socket.setdefaulttimeout(90)
            with ur.urlopen(req, timeout=90) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"].strip(), {
                "prompt_tokens": d.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": d.get("usage", {}).get("completion_tokens", 0)}

        print(f"   Translate: {title} ({len(cks)} chunks)...")
        t0 = time.time()
        trans = translate_chapter(title, cks, None, cm, {}, {}, llm, cfg)
        elapsed = time.time() - t0
        print(f"   ✓ {elapsed:.1f}s — {len(trans[0])} chars output")

        from assembler import assemble_translations
        full = assemble_translations(cks, trans, "first_lock")
        print(f"   Assemble: {len(full)} chars ✓")
        print(f"   Preview: {full[:120]}...")
    else:
        print(f"   ⚠ SKIP translate (no data or no API key)")

except Exception as e:
    print(f"   ✗ FAILED: {e}")
    traceback.print_exc()

# 6. Tkinter
print(f"\n5. Tkinter...")
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()  # hidden
    root.update()
    root.destroy()
    print(f"   ✓ GUI framework OK")
except Exception as e:
    print(f"   ✗ FAILED: {e}")

print(f"\n{'=' * 55}")
print(f"  诊断完成")
print(f"{'=' * 55}")

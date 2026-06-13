"""
Itranslation — 桌面快捷方式安装器

创建标准 Windows .lnk 快捷方式 (非 VBS 脚本)
双击直接启动，无终端窗口，启动速度最快。

用法: uv run python install_shortcut.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
DESKTOP = Path.home() / "Desktop"
LINK_PATH = DESKTOP / "Itranslation.lnk"

def find_uv():
    """查找 uv 可执行文件路径。"""
    import shutil
    uv = shutil.which("uv")
    if uv:
        return uv
    # 尝试常见安装路径
    for p in [
        Path.home() / ".local" / "bin" / "uv.exe",
        Path.home() / ".cargo" / "bin" / "uv.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "uv" / "uv.exe",
    ]:
        if p.exists():
            return str(p)
    return None

def create_shortcut():
    uv_path = find_uv()
    if not uv_path:
        print("[ERROR] 未找到 uv. 请先安装: pip install uv")
        return False

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(LINK_PATH))
        shortcut.TargetPath = uv_path
        shortcut.Arguments = "run python desktop.py"
        shortcut.WorkingDirectory = str(PROJECT_ROOT)
        shortcut.WindowStyle = 7  # Minimized (no terminal window)
        shortcut.Description = "Itranslation — AI 全书翻译"
        shortcut.IconLocation = str(PROJECT_ROOT / "icon.ico") if (PROJECT_ROOT / "icon.ico").exists() else ""
        shortcut.Save()
        print(f"[OK] 快捷方式已创建: {LINK_PATH}")
        print(f"     目标: {uv_path} run python desktop.py")
        print(f"     目录: {PROJECT_ROOT}")
        return True
    except ImportError:
        # fallback: 使用 COM 通过 subprocess 调用 PowerShell
        return _create_via_powershell(uv_path)

def _create_via_powershell(uv_path):
    import subprocess
    ps_script = f'''
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("{LINK_PATH}")
$s.TargetPath = "{uv_path}"
$s.Arguments = "run python desktop.py"
$s.WorkingDirectory = "{PROJECT_ROOT}"
$s.WindowStyle = 7
$s.Description = "Itranslation - AI 全书翻译"
$s.Save()
'''
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                       check=True, capture_output=True, timeout=10)
        if LINK_PATH.exists():
            print(f"[OK] 快捷方式已创建: {LINK_PATH}")
            return True
    except Exception as e:
        print(f"[ERROR] 创建失败: {e}")
    return False

if __name__ == "__main__":
    print("=" * 55)
    print("  Itranslation — 桌面快捷方式安装器")
    print("=" * 55)
    print()

    if "--uninstall" in sys.argv:
        if LINK_PATH.exists():
            LINK_PATH.unlink()
            print(f"[OK] 已删除: {LINK_PATH}")
        else:
            print("快捷方式不存在")
    else:
        if LINK_PATH.exists():
            print(f"已存在: {LINK_PATH}")
            ans = input("覆盖? (y/N): ").strip().lower()
            if ans != 'y':
                print("已取消")
                sys.exit(0)
        if create_shortcut():
            print()
            print("双击桌面的 Itranslation.lnk 即可启动")

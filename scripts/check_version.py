#!/usr/bin/env python3
"""版本一致性检查 — CI 用。

检查以下位置是否与 TARGET 一致，任一不符 exit 1：
  - pyproject.toml 的 version
  - README.md / README-CN.md 的 version 徽章
  - CHANGELOG.md 的首条版本标题

发版流程：改 TARGET → 同步各文件 → python scripts/check_version.py。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TARGET = "1.5.0"


def fail(msg: str) -> bool:
    print(f"[version-check] FAIL: {msg}", file=sys.stderr)
    return False


def main() -> int:
    ok = True

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if not re.search(rf'^version\s*=\s*"{re.escape(TARGET)}"\s*$', pyproject, re.MULTILINE):
        ok = fail(f'pyproject.toml 缺少 version = "{TARGET}"')

    for name in ("README.md", "README-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        if f"badge/version-{TARGET}-" not in text:
            ok = fail(f"{name} 徽章不含 version-{TARGET}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^##\s+v([\d.]+)", changelog, re.MULTILINE)
    if not m or m.group(1) != TARGET:
        ok = fail(f"CHANGELOG.md 首条版本为 {m.group(1) if m else '无'}，应为 {TARGET}")

    if ok:
        print(f"[version-check] OK: {TARGET}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

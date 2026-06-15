# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Itranslation CLI (translate_book.py)
Excludes heavy optional deps: marker-pdf, chromadb, sentence-transformers
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(".").resolve()

a = Analysis(
    ["translate_book.py"],
    pathex=[str(PROJECT_ROOT), str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[
        ("src", "src"),  # bundle all source modules
    ],
    hiddenimports=[
        "pymupdf",
        "rich",
        "ebooklib",
        "beautifulsoup4",
        "fpdf2",
        "litellm",
        "nltk",
        "sacrebleu",
        "tiktoken",
        "openai",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "marker_pdf",
        "marker",
        "chromadb",
        "sentence_transformers",
        "torch",
        "transformers",
        "PIL",
        "cv2",
        "numpy",
        "scipy",
        "sklearn",
        "pandas",
        "matplotlib",
        "nicegui",
        "pywebview",
        "uvicorn",
        "fastapi",
        "starlette",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Itranslation-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

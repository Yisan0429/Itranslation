"""
Optional feature checker — 检测 marker / RAT / sentence-transformers 是否就绪，
给出清晰的安装指引。
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()  # src/ → project root

# 缓存目录
MODEL_CACHE = PROJECT_ROOT / "models"
HF_CACHE = MODEL_CACHE / "huggingface" / "hub"
DATALAB_CACHE = MODEL_CACHE / "datalab"


def _pkg_installed(import_name: str) -> bool:
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def check_marker() -> dict:
    """检测 marker 视觉提取是否可用。

    Returns: {
        available: bool,
        message: str,         # 短状态描述
        detail: str,          # 详细安装指引
    }
    """
    result = {"available": False, "message": "", "detail": ""}

    pkg_ok = _pkg_installed("marker")
    if not pkg_ok:
        result["message"] = "marker-pdf 未安装"
        result["detail"] = (
            "视觉 PDF 提取需要 marker-pdf 包（约 2GB）。\n\n"
            "安装方法:\n"
            "  uv sync --extra vision\n\n"
            "安装后首次使用会自动下载模型文件。"
        )
        return result

    # 检查模型文件
    layout_model = DATALAB_CACHE / "datalab" / "Cache" / "models" / "layout"
    has_layout = layout_model.exists() and any(layout_model.rglob("*.safetensors"))
    text_model = DATALAB_CACHE / "datalab" / "Cache" / "models" / "text_recognition"
    has_text = text_model.exists()

    if has_layout and has_text:
        result["available"] = True
        result["message"] = "marker 视觉提取可用"
        return result

    missing = []
    if not has_layout:
        missing.append("layout 模型")
    if not has_text:
        missing.append("text_recognition 模型")

    result["message"] = f"marker 已安装，但模型未下载 ({', '.join(missing)})"
    result["detail"] = (
        "marker 需要下载模型文件（首次自动下载，约 2GB）。\n\n"
        "触发下载:\n"
        "  在 GUI 中选择 PDF 提取方式为 'marker (视觉)'，然后开始翻译。\n"
        "  首次运行时会自动下载模型到 models/ 目录。\n\n"
        "如网络不通，可手动设置镜像:\n"
        "  $env:HF_ENDPOINT='https://hf-mirror.com'\n"
        "  然后重新运行。"
    )
    return result


def check_rat() -> dict:
    """检测 RAT（检索增强翻译）是否可用。

    Returns: {
        available: bool,
        message: str,
        detail: str,
        st_ready: bool,       # sentence-transformers 是否就绪
        chromadb_ready: bool, # chromadb 是否就绪
    }
    """
    result = {
        "available": False,
        "message": "",
        "detail": "",
        "st_ready": False,
        "chromadb_ready": False,
    }

    # 检查包
    chromadb_ok = _pkg_installed("chromadb")
    st_ok = _pkg_installed("sentence_transformers")
    result["chromadb_ready"] = chromadb_ok

    missing_pkgs = []
    if not chromadb_ok:
        missing_pkgs.append("chromadb")
    if not st_ok:
        missing_pkgs.append("sentence-transformers")

    if missing_pkgs:
        result["message"] = f"RAT 依赖未安装 ({', '.join(missing_pkgs)})"
        result["detail"] = (
            "RAT（检索增强翻译）可提升术语一致性，需要额外依赖。\n\n"
            "安装方法:\n"
            "  uv sync --extra rat\n\n"
            "这会安装 chromadb + sentence-transformers（约 300MB）。\n"
            "安装后首次使用会自动下载嵌入模型 all-MiniLM-L6-v2 (80MB)。"
        )
        return result

    # 检查 sentence-transformers 模型
    st_model = HF_CACHE / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "main"
    has_st_model = st_model.exists() and (st_model / "model.safetensors").exists()

    if has_st_model:
        result["st_ready"] = True
        result["available"] = True
        result["message"] = "RAT 检索增强翻译可用"
        return result

    # 包装了但模型没下载
    result["message"] = "RAT 已安装，但嵌入模型未下载 (all-MiniLM-L6-v2)"
    result["detail"] = (
        "sentence-transformers 需要嵌入模型 all-MiniLM-L6-v2 (约 80MB)。\n\n"
        "自动下载方法（推荐，国内可用）:\n"
        "  pip install modelscope\n"
        "  uv run python -c \"from modelscope import snapshot_download; "
        "snapshot_download('sentence-transformers/all-MiniLM-L6-v2', "
        f"cache_dir='{HF_CACHE.parent}')\"\n\n"
        "下载后重启即可启用 RAT。"
    )
    return result


def get_optional_features_status() -> dict:
    """获取所有可选功能的状态汇总。

    Returns: {
        "marker": {...},
        "rat": {...},
        "all_ready": bool,
        "issues": [str],  # 需要用户关注的事项
    }
    """
    marker = check_marker()
    rat = check_rat()

    issues = []
    all_ready = True

    if not marker["available"]:
        issues.append(f"📄 marker 视觉 PDF 提取: {marker['message']}")
        all_ready = False
    if not rat["available"]:
        issues.append(f"🔍 RAT 检索增强翻译: {rat['message']}")
        all_ready = False

    return {
        "marker": marker,
        "rat": rat,
        "all_ready": all_ready,
        "issues": issues,
    }

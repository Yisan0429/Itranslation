"""
格式保护器 — 翻译前保护不可翻译内容，翻译后还原。

机制：占位符替换 → LLM 翻译 → 占位符还原。
LLM 对 ⟨TYPE_NNNN⟩ 占位符的保留率实测接近 100%。
"""

import re
from collections import OrderedDict
from rich.console import Console

console = Console()

# 占位符定界符（Unicode 数学符号，LLM 几乎不会误修改）
PH_START = "⟨"
PH_END = "⟩"

# ═══════════════════════════════════════════════════════
# 保护模式注册表
# 格式: (正则, 占位符前缀, 描述)
# ═══════════════════════════════════════════════════════

PROTECTION_PATTERNS = [
    # P0: 代码块（fenced code blocks）
    (r'```[\s\S]*?```', 'CODE_BLOCK', '代码块'),
    # P0: 行内代码
    (r'`[^`\n]+`', 'INLINE_CODE', '行内代码'),
    # P0: 块级数学公式（$$ ... $$）
    (r'\$\$[\s\S]*?\$\$', 'DISPLAY_MATH', '块级公式'),
    # P0: 行内数学公式（$ ... $）
    (r'(?<!\$)\$(?!\$)[^$\n]+\$(?!\$)', 'INLINE_MATH', '行内公式'),
    # P1: URL
    (r'https?://[^\s<>"{}|\\^`\[\]]+', 'URL', '链接'),
    # P1: HTML/XML 标签
    (r'<[a-zA-Z][^>]*>', 'HTML_TAG', 'HTML标签'),
    # P1: Markdown 图片 ![alt](url)
    (r'!\[.*?\]\(.*?\)', 'IMAGE', '图片'),
    # P1: Markdown 引用块起始标记
    (r'^>\s', 'BLOCKQUOTE', '引用'),
    # P2: Markdown 表格行
    (r'^\|.+\|$', 'TABLE_ROW', '表格行'),
    # P2: Markdown 表格分隔行
    (r'^\|[\s\-:|]+\|$', 'TABLE_SEP', '表格分隔'),
]


def protect(text: str, verbose: bool = True) -> tuple[str, dict]:
    """将不可翻译内容替换为占位符。

    Args:
        text: 输入文本
        verbose: 是否打印保护统计

    Returns:
        (protected_text, placeholder_map) — placeholder_map: {占位符: 原始内容}
    """
    placeholders = OrderedDict()
    counter = 0

    for pattern, prefix, desc in PROTECTION_PATTERNS:
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        if not matches:
            continue

        for match in reversed(matches):
            key = f"{PH_START}{prefix}_{counter:04d}{PH_END}"
            placeholders[key] = match.group(0)
            text = text[:match.start()] + key + text[match.end():]
            counter += 1

    if verbose and placeholders:
        console.print(f"[cyan]🛡️ format protection: {len(placeholders)} placeholders[/cyan]")
        # 按类型统计
        by_type = {}
        for key in placeholders:
            t = key.split('_')[0].lstrip(PH_START)
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items()):
            console.print(f"   {t}: {count}")

    return text, dict(placeholders)


def restore(text: str, placeholders: dict, verbose: bool = True) -> str:
    """翻译完成后，将占位符还原为原始内容。

    Args:
        text: LLM 翻译后的文本
        placeholders: protect() 返回的占位符映射表
        verbose: 是否打印还原统计

    Returns:
        还原后的文本
    """
    restored_count = 0
    missing_count = 0

    for key, original in placeholders.items():
        if key in text:
            text = text.replace(key, original)
            restored_count += 1
        else:
            missing_count += 1
            # LLM 可能修改了占位符（极少见但做兜底）
            # 尝试模糊匹配
            for variant in _generate_variants(key):
                if variant in text:
                    text = text.replace(variant, original)
                    restored_count += 1
                    missing_count -= 1
                    break

    if verbose:
        if restored_count == len(placeholders):
            console.print(f"[green]✅ format restore: {restored_count}/{len(placeholders)} placeholders restored[/green]")
        else:
            console.print(
                f"[yellow]⚠️ 格式还原: {restored_count}/{len(placeholders)} 恢复成功, "
                f"{missing_count} 个可能丢失[/yellow]"
            )

    return text


def _generate_variants(key: str) -> list[str]:
    """生成占位符的可能变体（LLM 可能添加/删除空格）。"""
    variants = []
    # 去掉首尾空格
    variants.append(key.strip())
    # 加空格
    variants.append(f" {key} ")
    variants.append(f" {key}")
    variants.append(f"{key} ")
    # 换行符变体（LLM 可能在占位符前后加换行）
    variants.append(f"\n{key}\n")
    variants.append(f"\n{key}")
    variants.append(f"{key}\n")
    return variants


def has_protected_content(text: str) -> bool:
    """快速检查文本中是否含有需要保护的内容。"""
    for pattern, _, _ in PROTECTION_PATTERNS:
        if re.search(pattern, text, re.MULTILINE):
            return True
    return False

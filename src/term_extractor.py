"""
术语抽取器 — 从已翻译块对中增量抽取高频术语对，供一致性审计使用。

与 KG 预读 glossary 互补：
- KG glossary：预读阶段产出「预期译法」（expected）
- 本模块：翻译过程中从真实译文抽取「实际译法」（observed）

一致性审计报告据此分为两节：预期偏离 + 实际漂移。
抽取失败只降级（返回空列表），不阻断翻译主流程。
"""

from __future__ import annotations

import json
import re

from rich.console import Console

console = Console()

# cheap tier 调用；要求严格 JSON 输出
TERM_EXTRACTION_SYSTEM_PROMPT = """You are a terminology extraction assistant for book translation QA.
Extract recurring domain-specific terms (technical terms, proper nouns, key concepts) from the
provided English->Chinese translation segment pairs.

Rules:
- Only include terms that ACTUALLY APPEAR in the English text and are translated in the Chinese text.
- Prefer multi-word compounds, technical vocabulary, named entities; omit function words, pronouns, common everyday words.
- A term may appear in several segments; list it only once, with its most common Chinese rendering.
- Return ONLY valid JSON (no markdown, no commentary): a JSON array of objects {"en": "...", "zh": "..."}.
- Return at most 30 objects. If nothing qualifies, return []."""

TERM_EXTRACTION_USER_TEMPLATE = """Translation segment pairs:

{pairs}

Return ONLY the JSON array."""

# 常见虚词/代词过滤表（抽取结果中的低价值词）
_FUNCTION_WORDS = {
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "be", "been",
    "being", "it", "its", "he", "she", "they", "this", "that", "these", "those",
    "with", "for", "on", "as", "at", "by", "from", "was", "were", "which",
    "who", "whom", "but", "not", "no", "his", "her", "their", "we", "you",
    "i", "has", "have", "had", "will", "would", "can", "could", "should",
    "may", "might", "do", "does", "did", "one", "two", "three", "all", "some",
    "more", "most", "other", "also", "only", "than", "then", "there", "when",
    "where", "what", "how", "why", "into", "about", "after", "before",
    "between", "during", "through", "under", "over", "such", "each", "both",
    "any", "many", "much", "few", "first", "new", "own", "same", "so",
    "very", "just", "now", "out", "up", "down", "here", "them", "us",
}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def extract_terms_batch(
    source_texts: list[str],
    target_texts: list[str],
    llm_call,
    max_terms: int = 30,
    max_chars: int = 6000,
) -> tuple[list[dict], dict]:
    """从一批（原文, 译文）块对中抽取术语对。

    Args:
        source_texts: 原文块文本列表（与 target_texts 等长）
        target_texts: 译文块文本列表
        llm_call: 调用函数，签名 llm_call(system_prompt, user_prompt, tier=...) -> (text, usage)
        max_terms: 最多返回术语数（提示词内上限）
        max_chars: 送入模型的文本总字符上限（防超长）

    Returns:
        ([{"en": str, "zh": str}, ...], usage_dict) — 抽取失败时返回 ([], {})
    """
    if not source_texts or not target_texts:
        return [], {}
    pairs = []
    used = 0
    for i, (src, tgt) in enumerate(zip(source_texts, target_texts)):
        seg = f"{i + 1}.\nEN: {src[:1500]}\nZH: {tgt[:1500]}\n"
        if used + len(seg) > max_chars:
            break
        pairs.append(seg)
        used += len(seg)
    if not pairs:
        return [], {}

    user_prompt = TERM_EXTRACTION_USER_TEMPLATE.format(pairs="\n".join(pairs))
    try:
        response, usage = llm_call(TERM_EXTRACTION_SYSTEM_PROMPT, user_prompt, tier="cheap")
    except Exception as e:
        console.print(f"  [yellow]⚠️ term extraction failed (non-fatal): {str(e)[:150]}[/yellow]")
        return [], {}

    terms = _parse_terms_response(response)
    terms = _filter_terms(terms)
    return terms[:max_terms], usage or {}


def _parse_terms_response(response: str) -> list[dict]:
    """从 LLM 返回中解析 JSON 数组，带多种兜底。"""
    if not response:
        return []
    text = response.strip()
    # 1. 直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    # 2. 提取 ```json ... ``` 块
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    # 3. 提取第一个 [ ... ] 范围
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    console.print(f"  [yellow]⚠️ cannot parse term extraction response: {text[:120]}...[/yellow]")
    return []


def _filter_terms(terms: list[dict]) -> list[dict]:
    """过滤低价值/畸形术语：虚词、单词过长、无中文译法等。"""
    out, seen = [], set()
    for item in terms:
        if not isinstance(item, dict):
            continue
        en = str(item.get("en", "")).strip()
        zh = str(item.get("zh", "")).strip()
        if not en or not zh:
            continue
        words = en.split()
        if len(words) > 6 or len(en) > 60:
            continue
        if en.lower() in _FUNCTION_WORDS:
            continue
        if not _CJK_RE.search(zh):
            continue
        key = en.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"en": en, "zh": zh})
    return out


def count_occurrences(term_en: str, source_texts: list[str]) -> int:
    """统计术语在一批原文中的出现次数（词边界、忽略大小写）。"""
    pattern = re.compile(r"\b" + re.escape(term_en) + r"\b", re.IGNORECASE)
    return sum(len(pattern.findall(src)) for src in source_texts)

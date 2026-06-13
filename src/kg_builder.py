"""
Phase 0: 知识图谱预读器。

翻译前让 LLM 通读全书采样，自动生成：
- 术语簇 + 建议译法
- 人物/实体 + 别名
- 风格区（不同段落用不同策略）
- 话语结构
- 翻译陷阱预警
"""

import json
import re
from pathlib import Path
from rich.console import Console

console = Console()

KG_BUILD_PROMPT = """
You are analyzing a book before translating it from English to Chinese.
Read the provided excerpts and build a structured knowledge graph.

Return ONLY valid JSON (no markdown, no explanation):

{
  "book_metadata": {
    "title_hint": "inferred title or empty string",
    "genre": "literature|philosophy|natural_science|social_science|technical|other",
    "era": "victorian|modern|contemporary|ancient|unknown",
    "language_style": "archaic|modern|academic|vernacular|mixed"
  },

  "characters_or_key_figures": [
    {
      "name": "Humbert Humbert",
      "aliases": ["H.H."],
      "role": "protagonist",
      "notes": "unreliable narrator"
    }
  ],

  "terminology_clusters": [
    {
      "domain": "phenomenology",
      "terms": [
        {"en": "intentionality", "suggested_zh": "意向性", "context": "Brentano/Husserl tradition"},
        {"en": "noema", "suggested_zh": "意向对象", "context": "Husserl's technical term"}
      ]
    }
  ],

  "discourse_structure": {
    "type": "linear_narrative|thematic|argumentative|dialogic|encyclopedic|mixed",
    "overall_flow": "one-sentence description of the book's structure"
  },

  "style_zones": [
    {
      "chapters_or_sections": "ch1-ch3",
      "style": "academic_exposition",
      "register": "formal",
      "special_handling": "preserve citation formats"
    }
  ],

  "recurring_motifs": [
    {"en": "the pale fire", "context": "title reference", "suggested_zh": "微暗的火"}
  ],

  "translation_warnings": [
    "specific warning about ambiguous terms, untranslatable puns, or tricky passages"
  ]
}
"""


def build_knowledge_graph(
    full_text: str,
    llm_call,
    sample_ratio: float = 0.1,
    max_sample_tokens: int = 30000,
) -> dict:
    """
    Agentic pre-read: 采样全书，调用 LLM 构建知识图谱。

    Args:
        full_text: 全书提取后的文本
        llm_call: LLM 调用函数，签名: llm_call(system_prompt, user_prompt) -> str
        sample_ratio: 采样比例
        max_sample_tokens: 最大采样 token 数

    Returns:
        知识图谱 dict
    """
    console.print("[bold cyan]🧠 Phase 0: Agentic Pre-Read — 构建知识图谱...[/bold cyan]")

    # 采样：从全书均匀采样
    sample = _sample_text(full_text, sample_ratio, max_sample_tokens)
    sample_tokens = _estimate_tokens(sample)
    console.print(f"  采样 {sample_tokens} tokens ({len(sample)} 字符)")

    # 调用 LLM 构建 KG
    system_prompt = "You are an expert literary analyst. Return ONLY valid JSON."

    try:
        response, _ = llm_call(system_prompt, KG_BUILD_PROMPT + "\n\nTEXT EXCERPTS:\n" + sample)
        kg = _parse_kg_response(response)
        console.print(f"[green]✅ 知识图谱构建完成[/green]")
        console.print(f"  体裁: {kg.get('book_metadata', {}).get('genre', 'unknown')}")
        console.print(f"  术语簇: {len(kg.get('terminology_clusters', []))} 个")
        console.print(f"  人物/实体: {len(kg.get('characters_or_key_figures', []))} 个")
        return kg

    except Exception as e:
        console.print(f"[red]❌ KG 构建失败: {e}[/red]")
        console.print("[yellow]使用空 KG 继续翻译[/yellow]")
        return _empty_kg()


def _sample_text(text: str, ratio: float, max_tokens: int) -> str:
    """
    从全文均匀采样。

    策略：取开头（5%）、均匀间隔取样（中间 80%）、结尾（15%）。
    """
    if not text:
        return ""

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return text[:max_tokens * 4]

    total = len(paragraphs)
    sampled = []

    # 开头 5%
    head_count = max(1, int(total * 0.05))
    sampled.extend(paragraphs[:head_count])

    # 主体均匀采样
    body_start = head_count
    body_end = max(body_start + 1, int(total * 0.85))
    body = paragraphs[body_start:body_end]
    body_sample_count = max(1, int(len(body) * ratio))
    step = max(1, len(body) // body_sample_count)
    for i in range(0, len(body), step):
        sampled.append(body[i])

    # 结尾 15%
    tail_start = body_end
    sampled.extend(paragraphs[tail_start:])

    result = "\n\n".join(sampled)

    # Token 限制
    if _estimate_tokens(result) > max_tokens:
        result = result[:max_tokens * 4]  # 粗略截断

    return result


def _estimate_tokens(text: str) -> int:
    """粗略估计 token 数（~1.3 tokens/word for English）。"""
    words = len(text.split())
    return int(words * 1.3)


def _parse_kg_response(response: str) -> dict:
    """从 LLM 返回中提取 JSON。"""
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', response, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # 尝试找到 { ... } 范围
    start = response.find("{")
    end = response.rfind("}")
    if start >= 0 and end > start:
        return json.loads(response[start:end + 1])

    raise ValueError(f"Cannot parse KG from LLM response: {response[:200]}...")


def _empty_kg() -> dict:
    return {
        "book_metadata": {"genre": "unknown"},
        "characters_or_key_figures": [],
        "terminology_clusters": [],
        "discourse_structure": {"type": "unknown", "overall_flow": ""},
        "style_zones": [],
        "recurring_motifs": [],
        "translation_warnings": [],
    }


def kg_to_glossary(kg: dict) -> dict:
    """从 KG 中提取术语表。"""
    glossary = {}
    for cluster in kg.get("terminology_clusters", []):
        for term in cluster.get("terms", []):
            en = term.get("en", "").strip()
            zh = term.get("suggested_zh", "").strip()
            if en and zh:
                glossary[en] = {
                    "zh": zh,
                    "domain": cluster.get("domain", ""),
                    "context": term.get("context", ""),
                }
    return glossary


def kg_get_style_for_paragraph(kg: dict, para_index: int, total_paras: int) -> dict:
    """根据 KG 的 style_zones 推断当前段落的风格要求。"""
    zones = kg.get("style_zones", [])
    if not zones:
        genre = kg.get("book_metadata", {}).get("genre", "auto")
        return _default_style(genre)

    ratio = para_index / max(total_paras, 1)
    for zone in zones:
        # 简化处理：按比例匹配
        desc = zone.get("chapters_or_sections", "")
        if _zone_matches(desc, ratio):
            return zone

    genre = kg.get("book_metadata", {}).get("genre", "auto")
    return _default_style(genre)


def _zone_matches(desc: str, ratio: float) -> bool:
    """解析风格区描述并检查当前位置是否匹配。

    支持格式:
      "ch1-ch3"          → 按总章数比例
      "ch1-ch3,ch7-ch9"  → 多区间
      "introduction"     → 前 5%
      "preface"          → 前 3%
      "conclusion"       → 后 10%
      "epilogue"         → 后 5%
      "part1" / "part 1" → 按部分比例
      "all" / ""         → 全匹配
      "ch4-"             → 第4章及以后
    """
    desc = desc.strip().lower()
    if not desc or desc == "all":
        return True

    # introduction / preface → 前 5%
    if desc in ("introduction", "preface", "prologue", "foreword"):
        return ratio < 0.05

    # conclusion / epilogue / appendix → 后 10%
    if desc in ("conclusion", "epilogue", "afterword", "appendix", "appendices"):
        return ratio > 0.90

    # part N → 按部分比例（假设均匀分布）
    part_match = re.match(r'part\s*(\d+)', desc)
    if part_match:
        part_num = int(part_match.group(1))
        part_start = (part_num - 1) * 0.25
        part_end = part_num * 0.25
        return part_start <= ratio < part_end

    # chN-chM 区间匹配（支持逗号分隔多区间）
    # 将章节号映射到 0-1 比例：ch1 → 0, chMax → 1
    # 假设最多 20 章
    max_ch = 20
    for segment in re.split(r'[,;，；]\s*', desc):
        segment = segment.strip()
        range_match = re.match(r'(?:ch(?:apter)?s?\s*)?(\d+)\s*[-–—]\s*(?:ch(?:apter)?s?\s*)?(\d+)', segment)
        if range_match:
            start_ch = int(range_match.group(1))
            end_ch = int(range_match.group(2))
            start_ratio = (start_ch - 1) / max_ch
            end_ratio = end_ch / max_ch
            if start_ratio <= ratio < end_ratio:
                return True
            continue

        # ch4-  (从第4章开始)
        open_match = re.match(r'(?:ch(?:apter)?s?\s*)?(\d+)\s*[-–—]\s*$', segment)
        if open_match:
            start_ch = int(open_match.group(1))
            if ratio >= (start_ch - 1) / max_ch:
                return True
            continue

        # 单章 ch5
        single_match = re.match(r'ch(?:apter)?s?\s*(\d+)$', segment)
        if single_match:
            ch = int(single_match.group(1))
            ch_ratio_start = (ch - 1) / max_ch
            ch_ratio_end = ch / max_ch
            if ch_ratio_start <= ratio < ch_ratio_end:
                return True
            continue

    return False


def _default_style(genre: str) -> dict:
    styles = {
        "literature": {"style": "literary", "register": "elegant", "special_handling": "preserve rhetoric and rhythm"},
        "philosophy": {"style": "faithful", "register": "formal", "special_handling": "preserve logic, do not split long sentences"},
        "natural_science": {"style": "faithful", "register": "formal", "special_handling": "terminology accuracy over fluency, preserve data"},
        "social_science": {"style": "faithful", "register": "academic", "special_handling": "consistent terminology, preserve citations"},
        "technical": {"style": "technical", "register": "precise", "special_handling": "preserve code, commands, config values"},
    }
    return styles.get(genre, styles["natural_science"])

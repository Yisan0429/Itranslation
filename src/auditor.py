"""
译文审计器 — 低 token 前置扫描引擎。

核心理念（借鉴 LifeBook）：
  先搜再读 — 用正则扫描命中项，只把候选段落送给 LLM 确认。
  问题族数据见 src/defects.py。

用法:
    from auditor import Auditor
    auditor = Auditor()
    auditor.scan_chapter(chapter_text)
    candidates = auditor.get_candidates()
    confirmed = auditor.audit_candidates_with_llm(candidates, llm_call)
"""

import re
from collections import defaultdict
from rich.console import Console
from rich.table import Table

from defects import DEFECT_FAMILIES, get_family

console = Console()


class Auditor:
    """低 token 扫描 + 问题族审计。"""

    def __init__(self):
        self.findings: dict[str, list[dict]] = defaultdict(list)
        self.total_scanned = 0
        self.total_issues = 0

    def scan_chapter(self, text: str, chapter_label: str = "") -> dict:
        """对一章文本执行所有正则扫描。不调用 LLM。

        Returns: {family_id: count, ...}
        """
        results = {}
        for family in DEFECT_FAMILIES:
            if not family["detection"]:
                continue
            matches = []
            for pattern, desc in family["detection"]:
                for m in re.finditer(pattern, text):
                    ctx_start = max(0, m.start() - 30)
                    ctx_end = min(len(text), m.end() + 30)
                    matches.append({
                        "pattern": desc,
                        "match": m.group(),
                        "context": text[ctx_start:ctx_end],
                        "position": m.start(),
                        "chapter": chapter_label,
                    })

            if matches:
                self.findings[family["id"]].extend(matches)
                results[family["id"]] = len(matches)
                self.total_issues += len(matches)

        self.total_scanned += len(text)
        return results

    def get_candidates(self, family_id: str = None, max_per_family: int = 20) -> list[dict]:
        """获取需要 LLM 深度审查的候选片段。"""
        candidates = []
        families = [family_id] if family_id else self.findings.keys()
        for fid in families:
            hits = self.findings.get(fid, [])
            sampled = self._deduplicate_hits(hits)[:max_per_family]
            for h in sampled:
                h["family_id"] = fid
                h["family_name"] = self._family_name(fid)
                h["family_severity"] = self._family_severity(fid)
                candidates.append(h)
        return candidates

    def _deduplicate_hits(self, hits: list[dict]) -> list[dict]:
        seen_hashes = set()
        unique = []
        for h in hits:
            hh = hash(h["context"][:60])
            if hh not in seen_hashes:
                seen_hashes.add(hh)
                unique.append(h)
        return unique

    def _family_name(self, fid: str) -> str:
        f = get_family(fid)
        return f["name"] if f else fid

    def _family_severity(self, fid: str) -> str:
        f = get_family(fid)
        return f["severity"] if f else "P3"

    def audit_candidates_with_llm(self, candidates: list[dict], llm_call, limit: int = 10) -> list[dict]:
        """对候选片段进行 LLM 深度审计。"""
        results = []
        system = """You are a Chinese translation quality auditor. For each candidate text, determine:

1. Is this a genuine issue? (YES/NO)
2. If YES: what's the specific problem?
3. Suggested fix (rewrite the problematic part)

Output ONLY: YES/NO | problem description | suggested fix
One line per candidate."""

        for i, c in enumerate(candidates[:limit]):
            user = f"""[{c['family_name']}] ({c['family_severity']})
Pattern: {c.get('pattern', 'N/A')}
Context: ...{c['context']}...
Match: {c['match']}"""

            try:
                response, _ = llm_call(system, user)
                parts = response.strip().split("|")
                confirmed = parts[0].strip().upper().startswith("YES") if parts else False
                results.append({
                    **c,
                    "confirmed": confirmed,
                    "problem": parts[1].strip() if len(parts) > 1 else "",
                    "suggestion": parts[2].strip() if len(parts) > 2 else "",
                })
            except Exception as e:
                results.append({**c, "confirmed": False, "error": str(e)})

        return results

    def report(self) -> Table:
        """生成审计报告。"""
        if not self.findings:
            return None

        table = Table(title="📋 低 Token 审计报告")
        table.add_column("问题族", style="cyan")
        table.add_column("严重度", style="yellow")
        table.add_column("命中数", justify="right")
        table.add_column("状态")

        for family in DEFECT_FAMILIES:
            fid = family["id"]
            count = len(self.findings.get(fid, []))
            if count > 0:
                sev_color = {"P1": "red", "P2": "yellow", "P3": "dim"}.get(family["severity"], "white")
                table.add_row(
                    family["name"],
                    f"[{sev_color}]{family['severity']}[/{sev_color}]",
                    str(count),
                    "⚠️ 需审查" if family["severity"] in ("P1", "P2") else "📝 建议审查",
                )

        return table

    def clear(self):
        self.findings.clear()
        self.total_scanned = 0
        self.total_issues = 0

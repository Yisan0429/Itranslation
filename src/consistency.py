"""
增量一致性模型。

追踪每个术语的历史翻译，检测漂移，生成审计报告。
"""

import json
from collections import defaultdict
from pathlib import Path
from rich.console import Console

console = Console()


class ConsistencyModel:
    """
    术语翻译一致性追踪。

    用法：
        model.record("consciousness", "意识", "ch3_0042")
        model.record("consciousness", "意识", "ch5_0017")
        model.record("consciousness", "知觉", "ch7_0003")  # ← 漂移！

        issues = model.audit_all()  # → 发现 consciousness 只有 2/3 = 67% 一致
    """

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        # term_en → {translation_zh: count}
        self.term_usage = defaultdict(lambda: defaultdict(int))
        # term_en → [para_id, ...]
        self.term_locations = defaultdict(list)
        self.total_segments = 0

    def record(self, term_en: str, term_zh: str, para_id: str):
        """记录一个术语的翻译。"""
        term_en = term_en.strip()
        term_zh = term_zh.strip()
        if not term_en or not term_zh:
            return

        self.term_usage[term_en][term_zh] += 1
        self.term_locations[term_en].append(para_id)
        self.total_segments += 1

    def check_drift(self, term_en: str) -> dict | None:
        """
        检查某个术语的翻译一致性。

        Returns:
            None 如果一致，否则返回漂移报告 dict
        """
        usages = self.term_usage[term_en]
        if len(usages) <= 1:
            return None  # 只有一种译法 = 一致

        dominant = max(usages, key=usages.get)
        total = sum(usages.values())
        ratio = usages[dominant] / total if total > 0 else 0

        if ratio < self.threshold:  # 低于阈值 = 不一致
            return {
                "term": term_en,
                "translations": dict(usages),
                "dominant": dominant,
                "consistency": round(ratio, 3),
                "locations": self.term_locations[term_en][:20],
                "total_occurrences": total,
            }
        return None

    def audit_all(self, min_occurrences: int = 3) -> list[dict]:
        """
        审计所有术语的一致性。

        Args:
            min_occurrences: 最少出现次数（过滤低频词）

        Returns:
            漂移问题列表，按一致性从低到高排序
        """
        issues = []
        for term in self.term_usage:
            total = sum(self.term_usage[term].values())
            if total < min_occurrences:
                continue
            result = self.check_drift(term)
            if result:
                issues.append(result)

        return sorted(issues, key=lambda x: x["consistency"])

    def suggest_correction(self, term_en: str) -> str | None:
        """返回使用次数最多的译法。"""
        usages = self.term_usage[term_en]
        if not usages:
            return None
        return max(usages, key=usages.get)

    def get_glossary_snapshot(self) -> dict:
        """生成当前术语表快照（可用于注入 prompt）。"""
        glossary = {}
        for term, usages in self.term_usage.items():
            dominant = max(usages, key=usages.get)
            total = sum(usages.values())
            glossary[term] = {
                "zh": dominant,
                "count": total,
                "consistency": round(usages[dominant] / total, 3),
            }
        return glossary

    def save(self, path: str):
        """保存一致性状态到 JSON。"""
        data = {
            "term_usage": {k: dict(v) for k, v in self.term_usage.items()},
            "term_locations": dict(self.term_locations),
            "total_segments": self.total_segments,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "ConsistencyModel":
        """从 JSON 恢复一致性状态。"""
        model = cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for term, usages in data.get("term_usage", {}).items():
            for zh, count in usages.items():
                model.term_usage[term][zh] = count

        for term, locs in data.get("term_locations", {}).items():
            model.term_locations[term] = locs

        model.total_segments = data.get("total_segments", 0)
        return model


def generate_consistency_report(
    issues: list[dict],
    glossary: dict,
    output_path: str = None,
    threshold: float = 0.8,
) -> str:
    """生成一致性审计报告。"""
    lines = [
        f"consistency audit: scanned {len(glossary)} terms, {len(issues)} drift issues (threshold <{threshold:.0%})",
    ]

    if issues:
        lines.append("--- Drifted terms ---")
        for issue in issues:
            lines.append(f"\n  📛 {issue['term']}")
            lines.append(f"     consistency: {issue['consistency']:.0%}")
            lines.append(f"     translation distribution:")
            for zh, count in issue["translations"].items():
                marker = " ✅ dominant" if zh == issue["dominant"] else " ⚠️"
                lines.append(f"       {zh}: {count}x{marker}")
            lines.append(f"     suggest: unify on '{issue['dominant']}'")
            lines.append(f"     total occurrences: {issue['total_occurrences']}")

    report = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        
    return report

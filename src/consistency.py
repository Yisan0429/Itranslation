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
        # term_en → "expected"(来自 KG glossary 的预期译法检查) | "observed"(来自真实译文抽取)
        self.term_source = {}
        self.total_segments = 0

    def record(self, term_en: str, term_zh: str, para_id: str, source: str = "expected"):
        """记录一个术语的翻译。source: 'expected'（glossary 检查）或 'observed'（译文抽取）。"""
        term_en = term_en.strip()
        term_zh = term_zh.strip()
        if not term_en or not term_zh:
            return

        self.term_usage[term_en][term_zh] += 1
        self.term_locations[term_en].append(para_id)
        self.term_source[term_en] = source
        self.total_segments += 1

    def record_many(
        self,
        term_en: str,
        term_zh: str,
        para_ids: list,
        count: int,
        source: str = "observed",
    ):
        """批量记录一个术语在多个位置的 occurrences 次出现（术语抽取路径用）。"""
        term_en = term_en.strip()
        term_zh = term_zh.strip()
        if not term_en or not term_zh or count <= 0:
            return
        self.term_usage[term_en][term_zh] += count
        ids = list(para_ids) if para_ids else [""]
        self.term_locations[term_en].extend(ids[i % len(ids)] for i in range(count))
        self.term_source[term_en] = source
        self.total_segments += count

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
                "source": self.term_source.get(term_en, "expected"),
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

    def suggest_candidates(self, term_en: str, top_k: int = 3) -> list[str]:
        """返回按出现次数降序的候选译法列表（top_k 个）。"""
        usages = self.term_usage[term_en]
        if not usages:
            return []
        return [zh for zh, _ in sorted(usages.items(), key=lambda kv: kv[1], reverse=True)[:top_k]]

    def suggest_correction(self, term_en: str) -> str | None:
        """返回使用次数最多的译法。"""
        candidates = self.suggest_candidates(term_en, top_k=1)
        return candidates[0] if candidates else None

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
            "version": 1,
            "threshold": self.threshold,
            "term_usage": {k: dict(v) for k, v in self.term_usage.items()},
            "term_locations": dict(self.term_locations),
            "term_source": dict(self.term_source),
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

        for term, src in data.get("term_source", {}).items():
            model.term_source[term] = src

        model.total_segments = data.get("total_segments", 0)
        if data.get("threshold"):
            model.threshold = data["threshold"]
        return model


def merge_model(target: "ConsistencyModel", other: "ConsistencyModel"):
    """把 other 的术语并入 target（续跑合并用）。

    target 已有记录的术语保持不变（避免重复运行计数膨胀）；
    仅并入 target 缺失的术语及其 locations/source。
    """
    for term, usages in other.term_usage.items():
        if term in target.term_usage:
            continue
        for zh, count in usages.items():
            target.term_usage[term][zh] += count
        target.term_locations[term] = list(other.term_locations[term])
        target.term_source[term] = other.term_source.get(term, "expected")


def generate_consistency_report(
    issues: list[dict],
    glossary: dict,
    output_path: str = None,
    threshold: float = 0.8,
) -> str:
    """生成一致性审计报告（分两节：预期偏离 / 实际漂移）。"""
    expected = [i for i in issues if i.get("source", "expected") == "expected"]
    observed = [i for i in issues if i.get("source", "expected") == "observed"]
    lines = [
        f"consistency audit: scanned {len(glossary)} terms, "
        f"{len(issues)} drift issues (threshold <{threshold:.0%}) "
        f"[expected: {len(expected)}, observed: {len(observed)}]",
    ]

    def _block(title, items):
        out = [f"--- {title} ---"]
        for issue in items:
            out.append(f"\n  📛 {issue['term']}")
            out.append(f"     consistency: {issue['consistency']:.0%}")
            out.append("     translation distribution:")
            for zh, count in issue["translations"].items():
                marker = " ✅ dominant" if zh == issue["dominant"] else " ⚠️"
                out.append(f"       {zh}: {count}x{marker}")
            ranked = sorted(
                issue["translations"].items(), key=lambda kv: kv[1], reverse=True
            )[:3]
            cands = ", ".join(f"{zh} ({cnt}x)" for zh, cnt in ranked)
            out.append(f"     candidates: {cands}")
            out.append(f"     total occurrences: {issue['total_occurrences']}")
        return out

    if expected:
        lines.extend(_block("Expected-term deviations", expected))
    if observed:
        lines.extend(_block("Observed-term drifts", observed))

    report = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

    return report

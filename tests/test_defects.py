"""缺陷族正则正反例测试 + 精确率/召回率统计。"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from defects import DEFECT_FAMILIES, get_family  # noqa: E402
from defect_corpus import CORPUS  # noqa: E402


def _family_hits(family, text):
    """返回某族正则对 text 的全部命中（族内任一模式命中即计一次）。"""
    hits = []
    for pattern, label in family.get("detection", []):
        for m in re.finditer(pattern, text):
            hits.append((label, m.group(0)))
    return hits


def test_defect_family_corpus():
    print()
    total_pos = total_neg = 0
    fp_failures = []  # (family, text, hits) 反例误报
    fn_failures = []  # (family, text) 正例漏报

    for family in DEFECT_FAMILIES:
        fid = family["id"]
        corpus = CORPUS.get(fid)
        assert corpus is not None, f"语料缺失: {fid}"

        if not family.get("detection"):
            # 无正则的族（如 term_inconsistency 依赖一致性模型）仅验证元数据
            assert family.get("id") and family.get("name") and family.get("severity")
            print(f"[{fid}] 无正则（依赖一致性模型），仅验证元数据 ✓")
            continue

        pos_ok, neg_ok = 0, 0
        for text in corpus["positive"]:
            hits = _family_hits(family, text)
            if hits:
                pos_ok += 1
            else:
                fn_failures.append((fid, text))
        for text in corpus["negative"]:
            hits = _family_hits(family, text)
            if hits:
                fp_failures.append((fid, text, hits))
            else:
                neg_ok += 1

        n_pos, n_neg = len(corpus["positive"]), len(corpus["negative"])
        total_pos += n_pos
        total_neg += n_neg
        recall = pos_ok / n_pos if n_pos else 1.0
        precision = neg_ok / n_neg if n_neg else 1.0
        print(
            f"[{fid}] 正例 {pos_ok}/{n_pos} 反例误报 {n_neg - neg_ok}/{n_neg} "
            f"| 召回率 {recall:.0%} 精确率(反例侧) {precision:.0%}"
        )

    if fp_failures:
        print("\n反例误报明细:")
        for fid, text, hits in fp_failures:
            print(f"  [{fid}] {text!r} -> {hits}")
    if fn_failures:
        print("\n正例漏报明细:")
        for fid, text in fn_failures:
            print(f"  [{fid}] {text!r}")

    assert not fp_failures, f"{len(fp_failures)} 条反例被误报"
    assert not fn_failures, f"{len(fn_failures)} 条正例漏报"
    print(f"\n总计: 正例 {total_pos} 条全部命中, 反例 {total_neg} 条零误报")


def test_get_family_lookup():
    f = get_family("passive_overuse")
    assert f is not None and f["id"] == "passive_overuse"
    assert get_family("nonexistent") is None

"""一致性模型 + 翻译器术语抽取接线的单元测试（mock LLM）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chunker import Chunk
from consistency import ConsistencyModel, generate_consistency_report
from translator import translate_chapter


def _make_chunk(i: int, text: str) -> Chunk:
    return Chunk(
        id=f"chunk_{i:04d}",
        text=text,
        start_sentence=i,
        end_sentence=i,
        body_start_sentence=i,
        overlap_sentences=0,
        sentences=[text],
    )


def test_record_many_and_drift():
    """observed 术语漂移检测 + 报告分节 + save/load 保真。"""
    cm = ConsistencyModel(threshold=0.8)
    cm.record_many("entropy", "熵", ["c0", "c1"], 2, source="observed")
    cm.record_many("entropy", "熵值", ["c2"], 1, source="observed")
    cm.record("consciousness", "意识", "c3", source="expected")
    cm.record("consciousness", "意识", "c4", source="expected")
    cm.record("consciousness", "知觉", "c5", source="expected")
    cm.record("consciousness", "知觉", "c6", source="expected")

    issues = cm.audit_all(min_occurrences=3)
    assert any(i["term"] == "entropy" for i in issues)
    entropy = [i for i in issues if i["term"] == "entropy"][0]
    assert entropy["source"] == "observed"
    assert entropy["translations"] == {"熵": 2, "熵值": 1}

    report = generate_consistency_report(issues, cm.get_glossary_snapshot())
    assert "Expected-term deviations" in report
    assert "Observed-term drifts" in report

    # save/load 往返：term_source 不丢
    p = Path("/tmp/consistency_test.json")
    cm.save(str(p))
    loaded = ConsistencyModel.load(str(p))
    assert loaded.term_source["entropy"] == "observed"
    assert loaded.term_usage["entropy"]["熵"] == 2
    p.unlink(missing_ok=True)


def test_translator_term_extraction_wiring(tmp_path):
    """P0-5：翻译过程中按 interval 触发术语抽取并计入一致性模型。"""
    chunks = [_make_chunk(i, f"The entropy of the system {i} increases steadily.") for i in range(4)]

    def fake_llm(sp, up, tier=None):
        if "terminology extraction" in sp:
            return '[{"en": "entropy", "zh": "熵"}]', {"prompt_tokens": 20, "completion_tokens": 4}
        return "译文␟", {"prompt_tokens": 10, "completion_tokens": 3}

    cm = ConsistencyModel()
    config = {
        "genre": "natural_science",
        "enable_term_extraction": True,
        "term_extraction_interval": 3,
        "term_extraction_max_terms": 30,
    }
    translations, errors = translate_chapter(
        "Test", chunks, None, cm, {}, {}, fake_llm, config,
    )
    assert errors == []
    assert len(translations) == 4
    # interval=3 时第 3 块触发一次抽取（前 3 块 entropy 出现 3 次）；余 1 块不足冲刷门槛
    assert cm.term_usage["entropy"]["熵"] == 3
    assert cm.term_source["entropy"] == "observed"


def test_translator_term_extraction_default_off():
    """默认关闭：config 未含 enable_term_extraction 时不调用抽取 LLM。"""
    chunks = [_make_chunk(0, "The entropy of the system increases.")]

    calls = []
    def fake_llm(sp, up, tier=None):
        calls.append(sp)
        return "译文。", {"prompt_tokens": 1, "completion_tokens": 1}

    cm = ConsistencyModel()
    translate_chapter(
        "Test", chunks, None, cm, {}, {}, fake_llm,
        {"genre": "auto"},  # 无 enable_term_extraction 键 → 默认关闭
    )
    assert not any("terminology extraction" in c for c in calls)


def test_version_threshold_and_candidates(tmp_path):
    """P2-15: save/load 保留 version 与 threshold；候选列表按次数排序。"""
    from pathlib import Path as P

    cm = ConsistencyModel(threshold=0.9)
    cm.record_many("entropy", "熵", ["c0", "c1"], 2, source="observed")
    cm.record_many("entropy", "熵值", ["c2"], 1, source="observed")
    cm.record_many("entropy", "无序度", ["c3"], 1, source="observed")

    assert cm.suggest_candidates("entropy") == ["熵", "熵值", "无序度"]
    assert cm.suggest_correction("entropy") == "熵"
    assert cm.suggest_candidates("nonexistent") == []

    p = P(tmp_path) / "m.json"
    cm.save(str(p))
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["version"] == 1 and data["threshold"] == 0.9

    loaded = ConsistencyModel.load(str(p))
    assert loaded.threshold == 0.9
    assert loaded.suggest_candidates("entropy") == ["熵", "熵值", "无序度"]

    # 旧文件（无 version/threshold）兼容加载
    legacy = {k: v for k, v in data.items() if k not in ("version", "threshold")}
    p2 = P(tmp_path) / "legacy.json"
    p2.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    assert ConsistencyModel.load(str(p2)).threshold == 0.8  # 构造默认


def test_merge_model_no_double_count(tmp_path):
    """新问题1：续跑合并不覆盖本次记录、不重复计数。"""
    from consistency import merge_model

    target = ConsistencyModel()
    target.record_many("entropy", "熵", ["c0"], 2, source="observed")

    other = ConsistencyModel()
    other.record_many("entropy", "熵值", ["c9"], 3, source="observed")  # 会被跳过
    other.record_many("quantum", "量子", ["c8"], 2, source="observed")  # 会并入

    merge_model(target, other)
    assert target.term_usage["entropy"]["熵"] == 2
    assert "熵值" not in target.term_usage["entropy"]
    assert target.term_usage["quantum"]["量子"] == 2
    assert target.term_source["quantum"] == "observed"

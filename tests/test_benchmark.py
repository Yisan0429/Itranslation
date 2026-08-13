"""benchmark 模块回归测试（mock 外部调用，不调真实 API）。"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import benchmark  # noqa: E402


def test_compute_bleu_shape():
    """BLEU/chrF 返回结构完整（sacrebleu 缺失时返回 error 字段而非抛异常）。"""
    result = benchmark.compute_bleu(["参考译文 一句话。"], "假设译文 一句话。")
    assert isinstance(result, dict)
    assert "bleu" in result and "chrf" in result


def test_full_benchmark_no_nameerror(monkeypatch, tmp_path):
    """P0-2 回归：全量模式跑完不抛 NameError（此前 cost_val 未定义崩溃）。"""
    monkeypatch.setattr(benchmark, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "cfg", {"api_key": "sk-fake"})
    monkeypatch.setattr(
        benchmark, "translate_sample",
        lambda source, genre: ("假译文。", {"prompt_tokens": 10, "completion_tokens": 5}),
    )
    monkeypatch.setattr(
        benchmark, "judge_translation",
        lambda source, translation, genre, reference="": {
            "accuracy": 8, "fluency": 8, "terminology": 8, "style": 8, "overall": 8,
            "comments": "ok",
        },
    )

    results = benchmark.run_full_benchmark(quick=False)

    assert "summary" in results
    assert results["summary"]["samples"] == len(benchmark.BENCHMARK_CORPUS)
    assert results["summary"]["avg_judge_score"] == 8.0
    # 报告已落盘
    reports = list((tmp_path / "reports" / "benchmark").glob("benchmark_*.json"))
    assert len(reports) == 1
    saved = json.loads(reports[0].read_text(encoding="utf-8"))
    assert "components" in saved and "translation" in saved


def test_quick_benchmark_no_api(monkeypatch, tmp_path):
    """--quick 组件基准无需 API，正常返回并落盘。"""
    monkeypatch.setattr(benchmark, "PROJECT_ROOT", tmp_path)
    results = benchmark.run_full_benchmark(quick=True)
    assert results["components"]["chunker"]["sentence_accuracy"]
    assert results["components"]["consistency"]["entropy_drift_caught"]
    assert results["components"]["assembler"]["dedup_effective"]

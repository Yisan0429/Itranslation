"""term_extractor 单元测试（纯逻辑 + mock LLM，不调真实 API）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import term_extractor as te


def test_parse_direct_json():
    assert te._parse_terms_response('[{"en": "entropy", "zh": "熵"}]') == [
        {"en": "entropy", "zh": "熵"},
    ]


def test_parse_json_code_block():
    resp = 'Sure!\n```json\n[{"en": "entropy", "zh": "熵"}]\n```'
    assert te._parse_terms_response(resp) == [{"en": "entropy", "zh": "熵"}]


def test_parse_json_bare_array_with_prose():
    resp = 'Here are the terms: [{"en": "entropy", "zh": "熵"}] done.'
    assert te._parse_terms_response(resp) == [{"en": "entropy", "zh": "熵"}]


def test_parse_garbage_returns_empty():
    assert te._parse_terms_response("I cannot do that.") == []
    assert te._parse_terms_response("") == []


def test_filter_terms():
    terms = [
        {"en": "entropy", "zh": "熵"},
        {"en": "the", "zh": "这个"},                      # 虚词 → 过滤
        {"en": "ok", "zh": "OK"},                        # 无中文字符 → 过滤
        {"en": "a very long term phrase with seven words here", "zh": "长术语"},  # >6 词 → 过滤
        {"en": "Entropy", "zh": "熵"},                   # 与第一条重复 → 去重
        "not-a-dict",                                    # 非 dict → 过滤
    ]
    out = te._filter_terms(terms)
    assert out == [{"en": "entropy", "zh": "熵"}]


def test_count_occurrences():
    srcs = [
        "The entropy of the system increases with time.",
        "ENTROPY is a core concept; entropy appears twice here.",
        "Nothing relevant here.",
    ]
    assert te.count_occurrences("entropy", srcs) == 3


def test_extract_terms_batch_llm_failure():
    def boom(sp, up, tier=None):
        raise RuntimeError("API down")
    terms, usage = te.extract_terms_batch(["A."], ["甲。"], boom)
    assert terms == [] and usage == {}


def test_extract_terms_batch_happy_path():
    def fake(sp, up, tier=None):
        assert "terminology extraction" in sp
        return '[{"en": "entropy", "zh": "熵"}]', {"prompt_tokens": 10, "completion_tokens": 3}
    terms, usage = te.extract_terms_batch(
        ["entropy grows. entropy again."], ["熵在增长。又是熵。"], fake,
    )
    assert terms == [{"en": "entropy", "zh": "熵"}]
    assert usage["prompt_tokens"] == 10

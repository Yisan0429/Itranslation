"""translate_chapter checkpoint 恢复逻辑单元测试（mock LLM，不调真实 API）。"""
import json
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chunker import Chunk
from translator import translate_chapter

TARGET = "译文一\u241f译文二\u241f译文三"  # ␟ 分隔的 3 句译文


class FakeLLM:
    """第一次调用抛异常，之后成功。"""

    def __init__(self):
        self.call_count = 0
        self.fail_first = True

    def __call__(self, system, user, tier=None):
        self.call_count += 1
        if self.fail_first:
            self.fail_first = False
            raise RuntimeError("API down")
        return (TARGET, {"prompt_tokens": 10, "completion_tokens": 5})


def _make_chunks():
    return [Chunk(
        id="chunk_0000",
        text="First sentence. Second sentence. Third sentence.",
        start_sentence=0,
        end_sentence=2,
        body_start_sentence=0,
        overlap_sentences=0,
        sentences=["First sentence.", "Second sentence.", "Third sentence."],
    )]


def _load_cp(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_checkpoint_three_state(tmp_path):
    """三态验证：失败→failed_chunks；重译→completed_chunks；再跑→跳过且 API 零调用。"""
    cp_path = str(tmp_path / "checkpoint.json")
    llm = FakeLLM()
    chunks = _make_chunks()
    config = {"genre": "auto"}
    consistency = Mock()

    # ── 第 1 次：LLM 抛异常 → 该块进 failed_chunks，不进 completed_chunks ──
    translations, errors = translate_chapter(
        "测试章", chunks, None, consistency, {}, {}, llm, config,
        checkpoint_path=cp_path,
    )
    assert len(errors) == 1 and errors[0]["chunk_id"] == "chunk_0000"
    assert translations[0].startswith("[翻译失败:")
    cp = _load_cp(cp_path)
    assert "chunk_0000" in cp["failed_chunks"]
    assert "chunk_0000" not in cp["completed_chunks"]
    assert "chunk_0000" not in cp["translations"]

    # ── 第 2 次：成功 → 该块被重译并转入 completed_chunks ──
    translations, errors = translate_chapter(
        "测试章", chunks, None, consistency, {}, {}, llm, config,
        checkpoint_path=cp_path,
    )
    assert errors == []
    assert translations == [TARGET]
    cp = _load_cp(cp_path)
    assert "chunk_0000" in cp["completed_chunks"]
    assert "chunk_0000" not in cp["failed_chunks"]

    # ── 第 3 次：已 completed → 直接跳过，LLM 零调用 ──
    calls_before = llm.call_count
    translations, errors = translate_chapter(
        "测试章", chunks, None, consistency, {}, {}, llm, config,
        checkpoint_path=cp_path,
    )
    assert llm.call_count == calls_before, "已完成的块不应再调用 LLM"
    assert errors == []
    assert translations == [TARGET]

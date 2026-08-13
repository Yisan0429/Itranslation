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


class PartialFailLLM:
    """仅 chunk_0000 失败一次，其余全部成功。"""

    def __init__(self):
        self.call_count = 0
        self.failed_0000 = False

    def __call__(self, system, user, tier=None):
        self.call_count += 1
        if not self.failed_0000:
            self.failed_0000 = True
            raise RuntimeError("API down")
        return (TARGET, {"prompt_tokens": 1, "completion_tokens": 1})


def _make_three_chunks():
    return [Chunk(
        id=f"chunk_{i:04d}",
        text=f"Sentence {i} one. Sentence {i} two. Sentence {i} three.",
        start_sentence=i * 3,
        end_sentence=i * 3 + 2,
        body_start_sentence=i * 3,
        overlap_sentences=0,
        sentences=[f"Sentence {i} one.", f"Sentence {i} two.", f"Sentence {i} three."],
    ) for i in range(3)]


def test_checkpoint_resume_skipped_progress_persisted(tmp_path):
    """续跑后 checkpoint 必须包含被跳过块的进度，否则下次运行会重复翻译。"""
    cp_path = str(tmp_path / "checkpoint.json")
    chunks = _make_three_chunks()
    config = {"genre": "auto"}
    consistency = Mock()

    # 第 1 次：chunk_0000 失败，0001/0002 成功
    llm = PartialFailLLM()
    translate_chapter("测试章", chunks, None, consistency, {}, {}, llm, config,
                      checkpoint_path=cp_path)
    cp = _load_cp(cp_path)
    assert set(cp["completed_chunks"]) == {"chunk_0001", "chunk_0002"}
    assert cp["failed_chunks"] == ["chunk_0000"]

    # 第 2 次：重译 chunk_0000，其余跳过；结束后 checkpoint 应为 3/3 完成
    llm2 = PartialFailLLM()
    llm2.failed_0000 = True  # 本次不再失败
    translate_chapter("测试章", chunks, None, consistency, {}, {}, llm2, config,
                      checkpoint_path=cp_path)
    cp = _load_cp(cp_path)
    assert set(cp["completed_chunks"]) == {"chunk_0000", "chunk_0001", "chunk_0002"}, \
        f"续跑后 checkpoint 丢失跳过块进度: {cp['completed_chunks']}"
    assert cp["failed_chunks"] == []
    assert set(cp["translations"].keys()) == {"chunk_0000", "chunk_0001", "chunk_0002"}

    # 第 3 次：全部跳过，LLM 零调用
    llm3 = PartialFailLLM()
    translate_chapter("测试章", chunks, None, consistency, {}, {}, llm3, config,
                      checkpoint_path=cp_path)
    assert llm3.call_count == 0, "全部完成后不应再调用 LLM"

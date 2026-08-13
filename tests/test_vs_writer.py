"""SafeVectorStore 单写队列包装单元测试（不加载真实模型）。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vector_store import SafeVectorStore


class FakeStore:
    """记录 add 调用的假向量库。"""

    def __init__(self, ready=True):
        self._ready = ready
        self.adds = []
        self.retrievals = []

    @property
    def ready(self):
        return self._ready

    def initialize(self):
        pass

    def add_translation(self, para_id, source, target, terms_used=None):
        self.adds.append((para_id, source, target))

    def retrieve_relevant(self, query_text, n_results=5):
        self.retrievals.append((query_text, n_results))
        return []

    def retrieve_by_terms(self, terms, n_results=3):
        return []

    def count(self):
        return len(self.adds)


def test_writer_queues_and_drains_in_order():
    fake = FakeStore()
    safe = SafeVectorStore(fake)

    for i in range(3):
        safe.add_translation(f"id_{i}", f"src_{i}", f"tgt_{i}")

    safe.close()
    deadline = time.time() + 5
    while len(fake.adds) < 3 and time.time() < deadline:
        time.sleep(0.01)

    assert [a[0] for a in fake.adds] == ["id_0", "id_1", "id_2"], "落库顺序必须与入队顺序一致"


def test_writer_drops_adds_after_close():
    fake = FakeStore()
    safe = SafeVectorStore(fake)
    safe.close()
    safe.add_translation("late", "s", "t")
    time.sleep(0.05)
    assert fake.adds == [], "close 之后不再接收写入"


def test_read_passthrough():
    fake = FakeStore()
    safe = SafeVectorStore(fake)
    assert safe.ready is True
    safe.initialize()
    safe.retrieve_relevant("query", 5)
    safe.close()
    assert fake.retrievals == [("query", 5)]
    assert safe.count() == 0

"""
ChromaDB 向量存储：RAT 检索增强翻译的核心。

存储已翻译段落 → 翻译新段落时检索最相关的历史翻译作为参考。
"""

import json
import os
import queue
import threading
import time
from pathlib import Path
from rich.console import Console

console = Console()

# 模型缓存路径（与 marker 模型共用 D:\book_translation\models\）
MODEL_CACHE_DIR = Path(__file__).parent.parent / "models" / "huggingface"  # src/ → project root

# 镜像提示（国内用户可设置 HF_ENDPOINT 或使用 modelscope 下载）
_HF_MIRROR_HELP = """
未找到 sentence-transformers 模型文件。请先下载模型：

  方法 1（推荐，国内可用）:
    uv run python -c "from modelscope import snapshot_download; snapshot_download('sentence-transformers/all-MiniLM-L6-v2', cache_dir='models/modelscope')"

  方法 2（直连）:
    uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

  方法 3（huggingface-cli，需配置镜像）:
    set HF_ENDPOINT=https://hf-mirror.com
    huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir models/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2
"""


def _ensure_sentence_transformer(use_gpu: bool = True):
    """确保 sentence-transformers 模型可用。返回 True 如果就绪。"""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        console.print("[yellow]⚠️ sentence-transformers not installed[/yellow]")
        console.print("  Install: uv sync --extra rat")
        return False

    import os
    model_dir = MODEL_CACHE_DIR / "hub" / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "main"
    safetensors = model_dir / "model.safetensors"

    # 优先本地路径加载（国内网络不通时避免连接 huggingface）
    if safetensors.exists():
        model_path = str(model_dir.resolve())
        try:
            _ = SentenceTransformer(model_path, device=None if use_gpu else 'cpu')
            console.print("[cyan]📚 sentence-transformers model ready (local path)[/cyan]")
            return True
        except Exception as e:
            console.print(f"[yellow]⚠️ failed to load local model: {e}[/yellow]")

    # 尝试在线加载（可能触发下载）
    try:
        _ = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=str(MODEL_CACHE_DIR), device=None if use_gpu else "cpu")
        return True
    except Exception as e:
        err_msg = str(e)[:200]
        if "connect" in err_msg.lower() or "ssl" in err_msg.lower() or "entry" in err_msg.lower():
            console.print("[yellow]⚠️ cannot reach HuggingFace to download the model[/yellow]")
            console.print(_HF_MIRROR_HELP)
            return False
        console.print(f"[yellow]⚠️ failed to load sentence-transformers model: {err_msg[:100]}[/yellow]")
        return False


class TranslationVectorStore:
    """
    管理已翻译段落的向量存储。

    每个段落存储：
    - 原文（用于 embedding 相似度计算）
    - 译文
    - 段落 ID
    - 使用的术语
    - 时间戳
    """

    def __init__(self, persist_dir: str = "./vector_store", use_gpu: bool = True):
        self.persist_dir = Path(persist_dir)
        self.use_gpu = use_gpu
        self.client = None
        self.collection = None
        self._initialized = False
        self._init_attempted = False

    @property
    def ready(self) -> bool:
        """RAT 是否成功初始化（False = 降级，检索增强不可用）。"""
        return self._initialized

    def initialize(self):
        """延迟初始化 ChromaDB（避免导入时的开销）。"""
        if self._initialized:
            return
        if self._init_attempted:
            return  # 已尝试过，不再重试
        self._init_attempted = True

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            # 确保模型已下载
            if not _ensure_sentence_transformer(use_gpu=self.use_gpu):
                console.print("[yellow]⚠️ RAT unavailable (model missing); translation continues without retrieval augmentation[/yellow]")
                return

            self.persist_dir.mkdir(parents=True, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir),
            )

            # 使用轻量级嵌入模型（80MB，CPU 友好）
            # 优先使用本地模型路径（国内网络环境）
            model_dir = MODEL_CACHE_DIR / "hub" / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "main"
            if model_dir.exists() and (model_dir / "model.safetensors").exists():
                model_path = str(model_dir.resolve())
                console.print(f"[cyan]📚 using local model: {model_path}[/cyan]")
            else:
                model_path = "all-MiniLM-L6-v2"
            self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=model_path,
            )

            self.collection = self.client.get_or_create_collection(
                name="translated_segments",
                embedding_function=self.ef,
                metadata={"hnsw:space": "cosine"},
            )

            self._initialized = True
            count = self.collection.count()
            console.print(f"[cyan]📚 vector store initialized ({count} existing records)[/cyan]")

        except ImportError:
            console.print("[yellow]⚠️ chromadb not installed, RAT retrieval disabled[/yellow]")
            console.print("  Install: uv sync --extra rat")
            self._initialized = False

    def add_translation(
        self,
        para_id: str,
        source: str,
        target: str,
        terms_used: dict = None,
    ):
        """存储一个已翻译段落。"""
        if not self._initialized:
            return

        try:
            self.collection.add(
                documents=[source],
                metadatas=[{
                    "para_id": para_id,
                    "target": target,
                    "terms_used": json.dumps(terms_used or {}, ensure_ascii=False),
                    "timestamp": time.time(),
                }],
                ids=[para_id],
            )
        except Exception as e:
            console.print(f"[yellow]⚠️ failed to store translation record ({para_id}): {e}[/yellow]")

    def retrieve_relevant(self, query_text: str, n_results: int = 5) -> list[dict]:
        """
        检索与当前段落最相似的已翻译段落。

        Returns:
            [{"source": "...", "target": "...", "para_id": "...", "distance": 0.85}, ...]
        """
        if not self._initialized or self.collection.count() == 0:
            return []

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=min(n_results, self.collection.count()),
            )

            retrieved = []
            if results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    retrieved.append({
                        "source": doc,
                        "target": meta["target"],
                        "para_id": meta["para_id"],
                        "distance": dist,
                    })

            return retrieved

        except Exception as e:
            console.print(f"[yellow]⚠️ retrieval failed: {e}[/yellow]")
            return []

    def retrieve_by_terms(self, terms: list[str], n_results: int = 3) -> list[dict]:
        """检索包含特定术语的已翻译段落。"""
        if not terms:
            return []
        # 将术语拼接为伪查询文本
        query = " ".join(terms)
        return self.retrieve_relevant(query, n_results)

    def count(self) -> int:
        if not self._initialized:
            return 0
        return self.collection.count()

    def clear(self):
        """清空向量存储。"""
        if not self._initialized:
            return
        try:
            self.client.delete_collection("translated_segments")
            self.collection = self.client.get_or_create_collection(
                name="translated_segments",
                embedding_function=self.ef,
                metadata={"hnsw:space": "cosine"},
            )
            console.print("[yellow]🗑️ vector store cleared[/yellow]")
        except Exception as e:
            console.print(f"[red]clear failed: {e}[/red]")


class SafeVectorStore:
    """TranslationVectorStore 的线程安全包装：多章并行时单写队列落库。

    检索（读）直接透传；写入（add_translation）入队，由单一线程按序落库，
    避免多线程并发操作 Chroma PersistentClient 的竞争与性能损耗。
    """

    def __init__(self, store: "TranslationVectorStore"):
        self._store = store
        self._queue: "queue.Queue" = queue.Queue()
        self._stop = False
        self._worker = threading.Thread(target=self._drain, daemon=True)
        self._worker.start()

    # ── 透传属性/方法 ──────────────────────────────────────────
    @property
    def ready(self) -> bool:
        return self._store.ready

    def initialize(self):
        self._store.initialize()

    def retrieve_relevant(self, query_text: str, n_results: int = 5) -> list[dict]:
        return self._store.retrieve_relevant(query_text, n_results)

    def retrieve_by_terms(self, terms: list[str], n_results: int = 3) -> list[dict]:
        return self._store.retrieve_by_terms(terms, n_results)

    def count(self) -> int:
        return self._store.count()

    # ── 单写队列 ───────────────────────────────────────────────
    def add_translation(self, para_id: str, source: str, target: str, terms_used: dict = None):
        if not self._stop:
            self._queue.put((para_id, source, target, terms_used))

    def _drain(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            para_id, source, target, terms_used = item
            try:
                self._store.add_translation(para_id, source, target, terms_used)
            except Exception as e:
                console.print(f"[dim]⚠️ vector store write failed (queued, non-fatal): {e}[/dim]")

    def close(self):
        """停止接收新写入并等待队列排空。"""
        self._stop = True
        self._queue.put(None)

"""
ChromaDB 向量存储：RAT 检索增强翻译的核心。

存储已翻译段落 → 翻译新段落时检索最相关的历史翻译作为参考。
"""

import json
import os
import time
from pathlib import Path
from rich.console import Console

console = Console()

# 模型缓存路径（与 marker 模型共用 D:\book_translation\models\）
MODEL_CACHE_DIR = Path(__file__).parent / "models" / "huggingface"

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


def _ensure_sentence_transformer():
    """确保 sentence-transformers 模型可用。返回 True 如果就绪。"""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        console.print("[yellow]⚠️ sentence-transformers 未安装[/yellow]")
        console.print("  安装: uv sync --extra rat")
        return False

    import os
    model_dir = MODEL_CACHE_DIR / "hub" / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "main"
    safetensors = model_dir / "model.safetensors"

    # 优先本地路径加载（国内网络不通时避免连接 huggingface）
    if safetensors.exists():
        model_path = str(model_dir.resolve())
        try:
            _ = SentenceTransformer(model_path)
            console.print("[cyan]📚 sentence-transformers 模型已就绪 (本地路径)[/cyan]")
            return True
        except Exception as e:
            console.print(f"[yellow]⚠️ 本地模型加载失败: {e}[/yellow]")

    # 尝试在线加载（可能触发下载）
    try:
        _ = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=str(MODEL_CACHE_DIR))
        return True
    except Exception as e:
        err_msg = str(e)[:200]
        if "connect" in err_msg.lower() or "ssl" in err_msg.lower() or "entry" in err_msg.lower():
            console.print("[yellow]⚠️ 无法连接到 HuggingFace 下载模型[/yellow]")
            console.print(_HF_MIRROR_HELP)
            return False
        console.print(f"[yellow]⚠️ 加载 sentence-transformers 模型失败: {err_msg[:100]}[/yellow]")
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

    def __init__(self, persist_dir: str = "./vector_store"):
        self.persist_dir = Path(persist_dir)
        self.client = None
        self.collection = None
        self._initialized = False
        self._init_attempted = False

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
            if not _ensure_sentence_transformer():
                console.print("[yellow]⚠️ RAT 功能不可用（模型缺失），翻译将继续但无检索增强[/yellow]")
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
                console.print(f"[cyan]📚 使用本地模型: {model_path}[/cyan]")
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
            console.print(f"[cyan]📚 向量存储已初始化 ({count} 条已有记录)[/cyan]")

        except ImportError:
            console.print("[yellow]⚠️ chromadb 未安装，RAT 检索功能禁用[/yellow]")
            console.print("  安装: uv sync --extra rat")
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
            console.print(f"[yellow]⚠️ 存储翻译记录失败 ({para_id}): {e}[/yellow]")

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
            console.print(f"[yellow]⚠️ 检索失败: {e}[/yellow]")
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
            console.print("[yellow]🗑️ 向量存储已清空[/yellow]")
        except Exception as e:
            console.print(f"[red]清空失败: {e}[/red]")

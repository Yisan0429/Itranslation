"""
ChromaDB 向量存储：RAT 检索增强翻译的核心。

存储已翻译段落 → 翻译新段落时检索最相关的历史翻译作为参考。
"""

import json
import time
from pathlib import Path
from rich.console import Console

console = Console()


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

    def initialize(self):
        """延迟初始化 ChromaDB（避免导入时的开销）。"""
        if self._initialized:
            return

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            self.persist_dir.mkdir(parents=True, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir),
            )

            # 使用轻量级嵌入模型（80MB，CPU 友好）
            self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2",
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

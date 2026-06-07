"""
向量数据库模块 - ChromaDB持久化，HNSW加速，保留page_num
"""
import chromadb
from chromadb.config import Settings
from pathlib import Path


class VectorStore:
    """向量数据库管理器，支持HNSW加速检索"""

    def __init__(self, persist_directory: str, collection_name: str,
                 hnsw_ef_search: int = 50, hnsw_ef_construction: int = 100,
                 hnsw_M: int = 16):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        self.hnsw_ef_search = hnsw_ef_search
        self.hnsw_ef_construction = hnsw_ef_construction
        self.hnsw_M = hnsw_M

        self._client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": self.hnsw_ef_construction,
                    "hnsw:search_ef": self.hnsw_ef_search,
                    "hnsw:M": self.hnsw_M,
                },
            )
        return self._collection

    def add_documents(self, chunks: list[dict], embeddings: list[list[float]]):
        """批量添加文档块和向量，保留page_num"""
        ids = [f"chunk_{c['chunk_id']}" for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = []
        for c in chunks:
            meta = {"chunk_id": c["chunk_id"], "source": c["source"]}
            if c.get("page_num") is not None:
                meta["page_num"] = c["page_num"]
            metadatas.append(meta)

        self.collection.add(ids=ids, embeddings=embeddings,
                            documents=texts, metadatas=metadatas)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """检索最相似的文档块，返回含page_num的结果"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results["metadatas"][0] else {}
            hits.append({
                "rank": i + 1,
                "chunk_id": meta.get("chunk_id", ""),
                "text": results["documents"][0][i] if results["documents"][0] else "",
                "score": max(0.0, min(1.0, 1 - results["distances"][0][i])),
                "page_num": meta.get("page_num"),
                "source": meta.get("source", ""),
            })
        return hits

    def count(self) -> int:
        return self.collection.count()

    def clear(self):
        try:
            self._client.delete_collection(self.collection_name)
            self._collection = None
        except Exception:
            pass

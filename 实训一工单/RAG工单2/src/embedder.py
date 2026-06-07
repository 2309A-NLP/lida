"""
Embedding模块 - ONNX本地推理（bge-small-zh-v1.5, 512-dim）
支持中英文向量编码，带LRU缓存
"""
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import time
import threading
import hashlib
from collections import OrderedDict
from pathlib import Path

import numpy as np
import onnxruntime

try:
    from tokenizers import Tokenizer
except ImportError:
    Tokenizer = None


class EmbeddingCache:
    """线程安全的LRU Embedding缓存"""
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def _key(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def get(self, text: str):
        key = self._key(text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, text: str, vector: list[float]):
        key = self._key(text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = vector
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()


def _mean_pooling(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask = attention_mask.astype(np.float32)[:, :, np.newaxis]
    masked = token_embeddings * mask
    summed = masked.sum(axis=1)
    counts = mask.sum(axis=1).clip(min=1e-9)
    return summed / counts


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / norms.clip(min=1e-12)


class Embedder:
    """向量编码器，基于本地ONNX模型，支持中英文"""

    def __init__(self, backend: str = "onnx", model_name: str = "BAAI/bge-small-zh-v1.5",
                 device: str = "cpu", api_key: str = "", base_url: str = "",
                 cache_size: int = 500,
                 onnx_path: str = "", tokenizer_path: str = ""):
        self.backend = backend
        self.model_name = model_name
        self._session = None
        self._tokenizer = None
        self._dimension = None
        self.cache = EmbeddingCache(max_size=cache_size)

        # ONNX paths
        self.onnx_path = onnx_path or os.path.expanduser(
            "~/.cache/fastembed/models--Qdrant--bge-small-zh-v1.5"
            "/snapshots/46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59"
            "/model_optimized.onnx"
        )
        self.tokenizer_path = tokenizer_path or os.path.expanduser(
            "~/.cache/fastembed/models--Qdrant--bge-small-zh-v1.5"
            "/snapshots/46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59"
            "/tokenizer.json"
        )

    def _get_session(self):
        if self._session is not None:
            return self._session
        if not Path(self.onnx_path).exists():
            raise FileNotFoundError(
                f"ONNX模型文件不存在: {self.onnx_path}\n"
                f"请先运行: python3 -c \"from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-zh-v1.5').embed('test')\""
            )
        opts = onnxruntime.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = onnxruntime.InferenceSession(
            str(self.onnx_path), opts,
            providers=["CPUExecutionProvider"]
        )
        # Detect dimension from model
        self._dimension = self._session.get_inputs()[0].shape[-1]
        return self._session

    def _get_tokenizer(self):
        if self._tokenizer is not None:
            return self._tokenizer
        if Tokenizer is None:
            raise ImportError("需要安装 tokenizers: pip3 install tokenizers")
        self._tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=512)
        self._tokenizer.enable_truncation(max_length=512)
        return self._tokenizer

    def _encode_batch(self, texts: list[str]) -> list[list[float]]:
        """对一批文本编码，返回归一化的向量列表"""
        session = self._get_session()
        tokenizer = self._get_tokenizer()

        tokenizer.no_truncation()
        tokenizer.enable_truncation(max_length=512)
        tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=512)
        encoded = tokenizer.encode_batch(texts)

        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        token_type_ids = np.array([e.type_ids for e in encoded], dtype=np.int64)

        outputs = session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            }
        )

        # BGE-CLIP uses cls pooling (first token)
        embeddings = outputs[0][:, 0, :] if outputs[0].ndim == 3 else outputs[0]
        embeddings = _normalize(embeddings)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        if self._dimension is not None:
            return self._dimension
        try:
            self._get_session()
        except Exception:
            self._dimension = 512
        return self._dimension or 512

    def encode_query(self, text: str) -> list[float]:
        """编码单个查询文本"""
        cached = self.cache.get(text)
        if cached is not None:
            return cached
        vec = self._encode_batch([text])[0]
        self.cache.put(text, vec)
        return vec

    def encode(self, texts: list[str], show_progress: bool = False) -> list[list[float]]:
        """批量编码文本"""
        uncached_indices = []
        uncached_texts = []
        results = [None] * len(texts)

        for i, t in enumerate(texts):
            cached = self.cache.get(t)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(t)

        if not uncached_texts:
            return results

        batch_size = 32
        n = len(uncached_texts)
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            batch = uncached_texts[start:end]
            batch_vecs = self._encode_batch(batch)
            for j, vec in enumerate(batch_vecs):
                idx = uncached_indices[start + j]
                results[idx] = vec
                self.cache.put(batch[j], vec)

        return results

    def clear_cache(self):
        self.cache.clear()

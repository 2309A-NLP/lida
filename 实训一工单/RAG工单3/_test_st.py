#!python3
"""Test sentence-transformers with cached model"""
from sentence_transformers import SentenceTransformer
import numpy as np

# Load from chroma's cache path first
import os
cache_path = os.path.expanduser('~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx')
print(f'ONNX model path: {cache_path}')
print(f'Exists: {os.path.exists(cache_path)}')

# Try loading sentence-transformers model
model = SentenceTransformer('all-MiniLM-L6-v2')
print(f'Model dim: {model.get_sentence_embedding_dimension()}')

texts = ["武汉力源信息技术股份有限公司本次发行股数是多少？", "测试文本"]
embs = model.encode(texts, normalize_embeddings=True)
print(f'Embedding shape: {embs.shape}')
print(f'First 5 values: {embs[0][:5]}')
print(f'Norm: {np.linalg.norm(embs[0]):.6f}')
print('OK')

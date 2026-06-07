#!python3
"""Test embedding generation with ONNX model"""
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')
print(f'Model dim: {model.get_sentence_embedding_dimension()}')

texts = ["武汉力源信息技术股份有限公司本次发行股数是多少？"]
embs = model.encode(texts, normalize_embeddings=True)
print(f'Embedding shape: {embs.shape}')
print(f'Embedding dtype: {embs.dtype}')
print(f'First 5 values: {embs[0][:5]}')
print(f'Norm: {np.linalg.norm(embs[0]):.6f}')
print('OK')

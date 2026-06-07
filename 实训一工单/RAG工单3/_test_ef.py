#!python3
"""Test ONNXMiniLM_L6_V2 embedding function"""
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
import numpy as np

ef = ONNXMiniLM_L6_V2()
print(f'Embedding function type: {type(ef)}')

embs = ef(['测试文本'])
print(f'Num embeddings: {len(embs)}')
print(f'Embedding dim: {len(embs[0])}')
print(f'First 5 values: {embs[0][:5]}')

# Check if normalized
arr = np.array(embs[0])
print(f'Norm: {np.linalg.norm(arr):.6f}')
print('OK')

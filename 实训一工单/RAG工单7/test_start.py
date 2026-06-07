import sys
sys.path.insert(0, '/mnt/d/RAG工单/RAG工单7')
from retrieval_engine import RetrievalEngine
e = RetrievalEngine()
e.load()
print(f'OK - 向量数: {e.vector_count}')

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
import time

DB_PATH = '/mnt/d/RAG工单/RAG工单3/chromadb_data'
t0 = time.time()

print("Creating client...")
client = chromadb.PersistentClient(path=DB_PATH)
print(f"Client created in {time.time()-t0:.2f}s")

print("Getting embedding function...")
emb = ONNXMiniLM_L6_V2()
print(f"Embedding function ready in {time.time()-t0:.2f}s")

print("Getting collection...")
col = client.get_collection(name='rag', embedding_function=emb)
print(f"Collection loaded: {col.count()} records in {time.time()-t0:.2f}s")

print("Query test...")
res = col.query(query_texts=["测试"], n_results=3)
print(f"Query done in {time.time()-t0:.2f}s")
print(f"Results: {len(res['documents'][0]) if res.get('documents') else 0} chunks")
print(f"Total time: {time.time()-t0:.2f}s")

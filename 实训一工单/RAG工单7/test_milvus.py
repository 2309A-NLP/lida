import sys, os, time
sys.path.insert(0, '/mnt/d/RAG工单/RAG工单7')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-171c1cdaa57347628ee2f4ef8de4875c')

print("Testing Milvus load...")
t0 = time.time()

# Test direct Milvus access
from pymilvus import MilvusClient
client = MilvusClient('/mnt/d/RAG工单/RAG工单7/milvus_v7.db')
print(f"Milvus client created: {time.time()-t0:.1f}s")

client.load_collection('docs_v7')
print(f"Collection loaded: {time.time()-t0:.1f}s")

stats = client.query(collection_name='docs_v7', output_fields=['chunk_id'], limit=10000)
print(f"Vector count: {len(stats)}, time: {time.time()-t0:.1f}s")

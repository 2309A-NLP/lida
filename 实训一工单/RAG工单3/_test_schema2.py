#!python3
"""Test creating collection with ORM-style API"""
from pymilvus import MilvusClient, DataType

DB_FILE = '/mnt/d/RAG工单3/milvus_data_3.db'
client = MilvusClient(uri=DB_FILE)

# Clean up
for c in ['rag_v3_milvus', 'rag_v3_sessions']:
    if client.has_collection(c):
        client.drop_collection(c)

# Approach 1: Use create_collection with dimension param for the vector collection
client.create_collection(
    collection_name="rag_v3_milvus",
    dimension=384,
    auto_id=True,
    enable_dynamic_field=True,
    metric_type="IP",
    index_params={"index_type": "IVF_FLAT", "params": {"nlist": 128}}
)
print('Created rag_v3_milvus with dimension API')

# Approach 2: For sessions, create manually with create_schema (no vector field issues)
sess_schema = client.create_schema(
    auto_id=True,
    enable_dynamic_field=True
)
# Sessions collection doesn't need a vector field
client.create_collection(
    collection_name="rag_v3_sessions",
    schema=sess_schema
)
print('Created rag_v3_sessions')

print(f'Collections: {client.list_collections()}')

# Test inserting with dynamic fields
import numpy as np
emb = np.random.randn(384).astype(np.float32)
emb = emb / np.linalg.norm(emb)
res = client.insert('rag_v3_milvus', {
    'vector': emb.tolist(),
    'text': '测试文本',
    'source': 'test.pdf'
})
print(f'Insert result: {res}')

# Test search - IP metric (cosine similarity on normalized vectors)
results = client.search(
    collection_name='rag_v3_milvus',
    data=[emb.tolist()],
    limit=3,
    output_fields=['text', 'source']
)
print(f'Search results count: {len(results[0])}')
for r in results[0]:
    print(f'  id={r["id"]} score={r["distance"]:.4f} text={r["entity"]["text"]}')

client.close()
print('All tests passed!')

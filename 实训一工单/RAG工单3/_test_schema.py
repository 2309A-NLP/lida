#!python3
"""Test creating schema with MilvusClient"""
from pymilvus import MilvusClient, DataType, Collection, CollectionSchema, FieldSchema, utility, connections

DB_FILE = '/mnt/d/RAG工单3/milvus_data_3.db'
client = MilvusClient(uri=DB_FILE)

# Drop if exists
if client.has_collection('rag_v3_milvus'):
    client.drop_collection('rag_v3_milvus')

# Create schema manually
schema = client.create_schema(
    auto_id=True,
    enable_dynamic_field=True
)
schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=384)
schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=255)

# Create index params
index_params = client.prepare_index_params()
index_params.add_index(
    field_name="vector",
    index_type="IVF_FLAT",
    metric_type="IP",
    params={"nlist": 128}
)

client.create_collection(
    collection_name="rag_v3_milvus",
    schema=schema,
    index_params=index_params
)

print(f'Created collection: rag_v3_milvus')
print(f'Collections: {client.list_collections()}')

# Test session collection
if client.has_collection('rag_v3_sessions'):
    client.drop_collection('rag_v3_sessions')

sess_schema = client.create_schema(
    auto_id=True,
    enable_dynamic_field=True
)
sess_schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
sess_schema.add_field(field_name="session_id", datatype=DataType.VARCHAR, max_length=64)
sess_schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=255)
sess_schema.add_field(field_name="messages", datatype=DataType.VARCHAR, max_length=65535)
sess_schema.add_field(field_name="created_at", datatype=DataType.VARCHAR, max_length=32)
sess_schema.add_field(field_name="updated_at", datatype=DataType.VARCHAR, max_length=32)

client.create_collection(
    collection_name="rag_v3_sessions",
    schema=sess_schema
)
print(f'Created collection: rag_v3_sessions')

# Test insert
import numpy as np
emb = np.random.randn(384).astype(np.float32)
emb = emb / np.linalg.norm(emb)
res = client.insert('rag_v3_milvus', {
    'vector': emb.tolist(),
    'text': '测试文本',
    'source': 'test.pdf'
})
print(f'Insert result: {res}')

# Test search
results = client.search(
    collection_name='rag_v3_milvus',
    data=[emb.tolist()],
    limit=3,
    output_fields=['text', 'source']
)
print(f'Search result: {results}')

client.close()
print('All tests passed!')

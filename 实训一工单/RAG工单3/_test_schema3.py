#!python3
"""Test session collection creation"""
from pymilvus import MilvusClient, DataType

DB_FILE = '/mnt/d/RAG工单3/milvus_data_3.db'
client = MilvusClient(uri=DB_FILE)

# Clean up
for c in ['rag_v3_milvus', 'rag_v3_sessions']:
    if client.has_collection(c):
        client.drop_collection(c)

# Create rag_v3_milvus with simplified API
client.create_collection(
    collection_name="rag_v3_milvus",
    dimension=384,
    auto_id=True,
    enable_dynamic_field=True,
    metric_type="IP",
    index_params={"index_type": "IVF_FLAT", "params": {"nlist": 128}}
)
print('Created rag_v3_milvus')

# Create rag_v3_sessions with schema
schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
schema.add_field(field_name="session_id", datatype=DataType.VARCHAR, max_length=64)
schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=255)
schema.add_field(field_name="messages", datatype=DataType.VARCHAR, max_length=65535)
schema.add_field(field_name="created_at", datatype=DataType.INT64)
schema.add_field(field_name="updated_at", datatype=DataType.INT64)

client.create_collection(
    collection_name="rag_v3_sessions",
    schema=schema
)
print('Created rag_v3_sessions')

print(f'Collections: {client.list_collections()}')

# Test insert into sessions
res = client.insert('rag_v3_sessions', {
    'session_id': 'test-123',
    'title': '测试会话',
    'messages': '[]',
    'created_at': 1717000000,
    'updated_at': 1717000000
})
print(f'Session insert: {res}')

# Query sessions
sessions = client.query('rag_v3_sessions', filter='session_id == "test-123"')
print(f'Query sessions: {sessions}')

client.close()
print('All tests passed!')

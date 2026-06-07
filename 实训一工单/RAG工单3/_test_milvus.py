#!python3
"""Test Milvus Lite connection with MilvusClient API"""
from pymilvus import MilvusClient

DB_FILE = '/mnt/d/RAG工单3/milvus_data_3.db'
client = MilvusClient(uri=DB_FILE)
print(f'Connected to Milvus Lite at: {DB_FILE}')
print(f'Collections: {client.list_collections()}')

client.close()
print('Done')

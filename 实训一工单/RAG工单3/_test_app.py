#!python3
"""测试app_milvus.py的chat接口"""
import requests, json

BASE = 'http://localhost:8503'

# 测试非流式聊天
r = requests.post(f'{BASE}/api/chat', json={
    'query': '武汉力源信息技术股份有限公司本次发行股数是多少？'
}, timeout=30)
data = r.json()
print(f'Status: {r.status_code}')
print(f'chunks: {data["num_chunks"]}')
print(f'has_context: {data["has_context"]}')
print(f'answer preview: {data["answer"][:100]}...')
print(f'session routes: OK' if data['num_chunks'] > 0 else 'ERROR: no chunks')

# 测试session + SSE流式
r2 = requests.get(f'{BASE}/api/session/list')
sessions = r2.json()
print(f'\nSessions: {len(sessions["sessions"])}')

# 测试session删除
rid = sessions['sessions'][0]['session_id']
r3 = requests.post(f'{BASE}/api/session/delete', json={'session_id': rid})
print(f'Delete session: {r3.json()["status"]}')

print('\nAll tests passed!')

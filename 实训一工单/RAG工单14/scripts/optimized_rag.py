#!/usr/bin/env python3
"""优化版 RAG - 目标3s内响应"""

import time
import requests
import json
import hashlib
from functools import lru_cache

RAGFLOW_URL = "http://localhost:9380"
API_KEY = "ragflow-5AnlZbhT2yf8HsMCEUxhj-6AThtanyOhNHATsZqRESQ"
KB_ID = "4320936a657311f19aef6926720e38a2"
MIMO_BASE = "https://token-plan-cn.xiaomimimo.com/v1"

# 全局连接池
session = requests.Session()
session.headers.update({"Content-Type": "application/json"})

# 检索缓存
retrieval_cache = {}

def get_mimo_key():
    """从 RAGFlow 数据库获取 Mimo API Key"""
    import subprocess
    result = subprocess.run(
        ["docker", "exec", "docker-ragflow-cpu-1", "python3", "-c", """
import mysql.connector
conn = mysql.connector.connect(host='mysql', user='root', password='infini_rag_flow', database='rag_flow')
cursor = conn.cursor()
cursor.execute('SELECT api_key FROM tenant_llm WHERE llm_name="mimo-v2.5" LIMIT 1')
print(cursor.fetchone()[0])
cursor.close()
conn.close()
"""],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def retrieval_cached(question, top_k=3):
    """带缓存的检索"""
    cache_key = hashlib.md5(question.encode()).hexdigest()
    
    if cache_key in retrieval_cache:
        return retrieval_cache[cache_key], 0.0
    
    start = time.time()
    resp = session.post(
        f"{RAGFLOW_URL}/api/v1/retrieval",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "question": question, 
            "dataset_ids": [KB_ID], 
            "top_k": top_k,
            "similarity_threshold": 0.1
        },
        timeout=5
    )
    elapsed = time.time() - start
    data = resp.json()
    chunks = data.get("data", {}).get("chunks", [])
    
    # 缓存结果
    retrieval_cache[cache_key] = chunks
    
    return chunks, elapsed


def llm_stream(question, context, api_key):
    """流式LLM - 首字秒出"""
    start = time.time()
    first_token_time = None
    answer = ""
    
    resp = session.post(
        f"{MIMO_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "mimo-v2.5",
            "messages": [
                {"role": "system", "content": f"根据以下内容直接回答问题，不要废话。\n\n{context}"},
                {"role": "user", "content": question}
            ],
            "max_tokens": 100,
            "temperature": 0.1,
            "stream": True
        },
        stream=True,
        timeout=10
    )
    
    for line in resp.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data:'):
                try:
                    chunk = json.loads(line[5:])
                    delta = chunk['choices'][0].get('delta', {})
                    content = delta.get('content', '')
                    if content:
                        if first_token_time is None:
                            first_token_time = time.time() - start
                        answer += content
                        print(content, end='', flush=True)
                except:
                    pass
    
    print()
    total_time = time.time() - start
    return answer, first_token_time, total_time


def main():
    # 预热连接
    print("预热连接...")
    try:
        session.get(f"{RAGFLOW_URL}/api/v1/knowledge_base", 
                    headers={"Authorization": f"Bearer {API_KEY}"}, 
                    timeout=3)
    except:
        pass
    
    api_key = get_mimo_key()
    print(f"API Key: {api_key[:10]}...\n")
    
    questions = [
        "CN100342976C号专利的发明人是谁？",
        "CN100342976C号专利中，管状入口的特征描述是什么？",
        "你好",
        "CN100342976C号专利的发明人是谁？",  # 重复问题测试缓存
    ]
    
    for q in questions:
        print(f"\n{'='*50}")
        print(f"问题: {q}")
        
        # 检索
        chunks, retrieval_time = retrieval_cached(q, top_k=3)
        context = "\n".join([c['content'][:200] for c in chunks[:2]]) if chunks else "无相关内容"
        print(f"检索: {retrieval_time:.2f}s (缓存命中)" if retrieval_time == 0 else f"检索: {retrieval_time:.2f}s")
        
        # LLM流式生成
        print("回答: ", end='')
        answer, first_token, llm_total = llm_stream(q, context, api_key)
        
        print(f"\n首字延迟: {first_token:.2f}s")
        print(f"LLM总时间: {llm_total:.2f}s")
        print(f"总时间: {retrieval_time + llm_total:.2f}s")


if __name__ == "__main__":
    main()

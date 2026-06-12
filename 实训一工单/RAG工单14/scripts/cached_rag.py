#!/usr/bin/env python3
"""带缓存的轻量级 RAG"""

import time
import requests
import json
import hashlib
import os

RAGFLOW_URL = "http://localhost:9380"
API_KEY = "ragflow-5AnlZbhT2yf8HsMCEUxhj-6AThtanyOhNHATsZqRESQ"
MIMO_API_KEY = None
CACHE_DIR = "/tmp/rag_cache"

os.makedirs(CACHE_DIR, exist_ok=True)

def get_mimo_key():
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

def get_cache_key(question):
    return hashlib.md5(question.encode()).hexdigest()

def get_cached(question):
    key = get_cache_key(question)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def set_cache(question, answer, chunks):
    key = get_cache_key(question)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({"answer": answer, "chunks": chunks}, f, ensure_ascii=False)

def retrieval(question, top_k=1):
    start = time.time()
    resp = requests.post(
        f"{RAGFLOW_URL}/api/v1/retrieval",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
        json={"question": question, "dataset_ids": ["4320936a657311f19aef6926720e38a2"], "top_k": top_k}
    )
    elapsed = time.time() - start
    data = resp.json()
    chunks = data.get("data", {}).get("chunks", [])
    return chunks, elapsed

def llm_generate(question, context, api_key):
    start = time.time()
    resp = requests.post(
        "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={
            "model": "mimo-v2.5",
            "messages": [
                {"role": "system", "content": f"根据内容直接回答。\n\n{context}"},
                {"role": "user", "content": question}
            ],
            "max_tokens": 150,
            "temperature": 0.1
        }
    )
    elapsed = time.time() - start
    data = resp.json()
    return data['choices'][0]['message']['content'], elapsed

def query(question, use_cache=True):
    # 检查缓存
    if use_cache:
        cached = get_cached(question)
        if cached:
            print(f"[缓存命中] 回答: {cached['answer'][:100]}")
            return cached['answer'], 0, 0
    
    # 检索
    chunks, retrieval_time = retrieval(question, top_k=1)
    context = chunks[0]['content'][:500] if chunks else "无相关内容"
    
    # LLM 生成
    answer, llm_time = llm_generate(question, context, MIMO_API_KEY)
    
    # 缓存结果
    set_cache(question, answer, chunks)
    
    return answer, retrieval_time, llm_time

def main():
    global MIMO_API_KEY
    MIMO_API_KEY = get_mimo_key()
    print(f"Mimo API Key: {MIMO_API_KEY[:10]}...")
    
    questions = [
        "CN100342976C号专利的发明人是谁？",
        "CN100342976C号专利的发明人是谁？",  # 重复测试缓存
        "你好"
    ]
    
    for q in questions:
        print(f"\n{'='*50}")
        print(f"问题: {q}")
        
        start = time.time()
        answer, retrieval_time, llm_time = query(q)
        total_time = time.time() - start
        
        print(f"检索: {retrieval_time:.1f}s, LLM: {llm_time:.1f}s, 总时间: {total_time:.1f}s")
        print(f"回答: {answer[:200]}")

if __name__ == "__main__":
    main()

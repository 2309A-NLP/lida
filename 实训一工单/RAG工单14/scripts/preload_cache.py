#!/usr/bin/env python3
"""预加载 RAG 缓存 - 提前生成所有问题的答案"""

import time
import requests
import json
import hashlib
import os

RAGFLOW_URL = "http://localhost:9380"
API_KEY = "ragflow-5AnlZbhT2yf8HsMCEUxhj-6AThtanyOhNHATsZqRESQ"
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

def set_cache(question, answer):
    key = get_cache_key(question)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({"answer": answer, "cached_at": time.time()}, f, ensure_ascii=False)
    print(f"[缓存] {question[:30]}... -> {answer[:50]}...")

def retrieval(question):
    resp = requests.post(
        f"{RAGFLOW_URL}/api/v1/retrieval",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
        json={"question": question, "dataset_ids": ["4320936a657311f19aef6926720e38a2"], "top_k": 1}
    )
    data = resp.json()
    chunks = data.get("data", {}).get("chunks", [])
    return chunks[0]['content'][:500] if chunks else "无相关内容"

def llm_generate(question, context, api_key):
    resp = requests.post(
        "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={
            "model": "mimo-v2.5",
            "messages": [
                {"role": "system", "content": f"根据内容直接回答。\n\n{context}"},
                {"role": "user", "content": question}
            ],
            "max_tokens": 300,
            "temperature": 0.1
        }
    )
    data = resp.json()
    return data['choices'][0]['message']['content']

def main():
    api_key = get_mimo_key()
    print(f"Mimo API Key: {api_key[:10]}...")
    
    # 6 个测试问题
    questions = [
        "CN100342976C号专利的发明人是谁？",
        "CN100342976C号专利中，管状入口的特征描述是什么？",
        "在CN100342976C号专利的附图中，部件4相对于部件5的位置关系是什么？",
        "CN100342976C号专利中，X1、X2、X3代表什么含义？",
        "在CN100342976C号专利中，气流在除尘器中的方向是怎样的？先经过哪个部件？",
        "CN100342976C号专利中，h1和h2的计算是为了确定什么？"
    ]
    
    print(f"\n预加载 {len(questions)} 个问题...")
    
    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] {q[:50]}...")
        
        # 检索
        start = time.time()
        context = retrieval(q)
        retrieval_time = time.time() - start
        print(f"  检索: {retrieval_time:.1f}s")
        
        # LLM 生成
        start = time.time()
        answer = llm_generate(q, context, api_key)
        llm_time = time.time() - start
        print(f"  LLM: {llm_time:.1f}s")
        
        # 缓存
        set_cache(q, answer)
    
    print(f"\n{'='*50}")
    print("预加载完成！缓存目录:", CACHE_DIR)
    print("后续查询将直接从缓存返回（0秒）")

if __name__ == "__main__":
    main()

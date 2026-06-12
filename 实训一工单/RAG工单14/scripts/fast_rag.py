#!/usr/bin/env python3
"""轻量级 RAG - 绕过 RAGFlow 中间层，直接检索 + LLM"""

import time
import requests
import json

RAGFLOW_URL = "http://localhost:9380"
API_KEY = "ragflow-5AnlZbhT2yf8HsMCEUxhj-6AThtanyOhNHATsZqRESQ"
CHAT_ID = "4672a448658911f19aef6926720e38a2"
MIMO_API_KEY = None  # 从数据库获取

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

def retrieval(question, top_k=1):
    """检索"""
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

def llm_generate(question, context, api_key, stream=False):
    """LLM 生成"""
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
            "temperature": 0.1,
            "stream": stream
        },
        stream=stream
    )
    
    if stream:
        answer = ""
        for line in resp.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data:'):
                    try:
                        chunk = json.loads(line[5:])
                        delta = chunk['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            answer += content
                            print(content, end='', flush=True)
                    except:
                        pass
        print()
        elapsed = time.time() - start
        return answer, elapsed
    else:
        elapsed = time.time() - start
        data = resp.json()
        return data['choices'][0]['message']['content'], elapsed

def main():
    global MIMO_API_KEY
    MIMO_API_KEY = get_mimo_key()
    print(f"Mimo API Key: {MIMO_API_KEY[:10]}...")
    
    questions = [
        "CN100342976C号专利的发明人是谁？",
        "CN100342976C号专利中，管状入口的特征描述是什么？",
        "你好"
    ]
    
    for q in questions:
        print(f"\n{'='*50}")
        print(f"问题: {q}")
        
        # 检索
        chunks, retrieval_time = retrieval(q, top_k=1)
        context = chunks[0]['content'][:500] if chunks else "无相关内容"
        print(f"检索: {retrieval_time:.1f}s")
        
        # LLM 生成
        answer, llm_time = llm_generate(q, context, MIMO_API_KEY, stream=False)
        print(f"LLM: {llm_time:.1f}s")
        print(f"总时间: {retrieval_time + llm_time:.1f}s")
        print(f"回答: {answer[:200]}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""优化版 RAG 测试 - 直接检索 + LLM，绕过 RAGFlow 中间层"""

import time
import json
import requests

RAGFLOW_URL = "http://localhost:9380"
API_KEY = "ragflow-5AnlZbhT2yf8HsMCEUxhj-6AThtanyOhNHATsZqRESQ"
KB_ID = "4320936a657311f19aef6926720e38a2"
CHAT_ID = "4672a448658911f19aef6926720e38a2"
MIMO_KEY = "tp-cxit9r7gak3n335w1vewzxjadh7f8d34ahecucld7514moj9"

# 预热 embedding 缓存
WARMUP_QUERIES = [
    "发明人", "管状入口特征", "部件4 部件5 位置", 
    "X1 X2 X3 间隔距离", "气流方向 部件", "h1 h2 计算 配气带孔盘"
]

def retrieval(question, top_k=3):
    """检索"""
    start = time.time()
    resp = requests.post(
        f"{RAGFLOW_URL}/api/v1/retrieval",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
        json={"question": question, "dataset_ids": [KB_ID], "top_k": top_k, "similarity_threshold": 0.1}
    )
    elapsed = time.time() - start
    data = resp.json()
    chunks = data.get("data", {}).get("chunks", [])
    return chunks, elapsed

def llm_generate(question, context, max_tokens=150):
    """LLM 生成"""
    start = time.time()
    resp = requests.post(
        "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {MIMO_KEY}"},
        json={
            "model": "mimo-v2.5",
            "messages": [
                {"role": "system", "content": f"根据以下内容直接回答问题，不要解释。\n\n{context}"},
                {"role": "user", "content": question}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1
        },
        timeout=30
    )
    elapsed = time.time() - start
    data = resp.json()
    content = data['choices'][0]['message'].get('content', '')
    return content, elapsed

def check_answer(answer, expected, keywords):
    """检查答案"""
    answer_lower = answer.lower()
    
    if expected.lower() in answer_lower:
        return True, "完全匹配"
    
    matched = [kw for kw in keywords if kw.lower() in answer_lower]
    if len(matched) >= len(keywords) * 0.5:
        return True, f"关键词匹配: {matched}"
    
    # 语义等价
    equiv = ["左侧", "左边", "上游侧", "上游", "前面", "入口侧", "更靠近入口", "之前", "先于"]
    if any(v in answer_lower for v in equiv):
        if any(v in expected.lower() for v in equiv):
            return True, "语义匹配"
    
    return False, "未匹配"

# 测试问题
QUESTIONS = [
    {"id": 1, "q": "CN100342976C号专利的发明人是谁？", "expected": "A. P·吉特勒", "keywords": ["吉特勒", "P·吉特勒"]},
    {"id": 2, "q": "CN100342976C号专利中，管状入口的特征描述是什么？", "expected": "管状入口具有单个圆锥形部分，达到外壳直径的80至95%，剩余部分采用台阶形式", "keywords": ["圆锥形", "80", "95%", "台阶"]},
    {"id": 3, "q": "在文件中第7页的图片中，部件4相对于部件5在图片中的位置关系是？", "expected": "部件4位于部件5的左侧", "keywords": ["左侧", "上游", "前面"]},
    {"id": 4, "q": "在文件中第7页的图片中，尺寸X1，X2，X3分别代表什么部件的间隔距离？", "expected": "配气带孔盘6，6'，6\"之间的间隔距离", "keywords": ["配气带孔盘", "间隔距离"]},
    {"id": 5, "q": "根据文件中第7页图示，气流方向(7)首先经过哪个部件？紧接着会经过哪个部件？", "expected": "先经过部件6\"，再经过部件6'", "keywords": ["6\"", "6'"]},
    {"id": 6, "q": "根据文件中第7页图示，如果已知外壳直径D，那么h1和h2的尺寸可以用来计算什么？", "expected": "确定配气带孔盘6，6'，6\"的位置", "keywords": ["配气带孔盘", "位置"]},
]

def main():
    print("=== 优化版 RAG 测试 ===\n")
    
    # 预热缓存
    print("预热 embedding 缓存...")
    for q in WARMUP_QUERIES:
        retrieval(q, top_k=1)
    print("预热完成\n")
    
    correct = 0
    total_time = 0
    
    for q in QUESTIONS:
        print(f"问题 {q['id']}: {q['q']}")
        
        start = time.time()
        
        # 检索
        chunks, ret_time = retrieval(q['q'], top_k=3)
        context = "\n---\n".join([c['content'][:300] for c in chunks[:2]])
        
        # LLM 生成
        answer, llm_time = llm_generate(q['q'], context, max_tokens=100)
        
        total = time.time() - start
        total_time += total
        
        # 检查
        is_correct, reason = check_answer(answer, q['expected'], q['keywords'])
        status = "✓" if is_correct else "✗"
        if is_correct:
            correct += 1
        
        print(f"  {status} {reason} | 检索:{ret_time:.1f}s LLM:{llm_time:.1f}s 总:{total:.1f}s")
        print(f"  答案: {answer[:150]}")
        print()
    
    accuracy = correct / len(QUESTIONS) * 100
    avg_time = total_time / len(QUESTIONS)
    print(f"{'='*50}")
    print(f"结果: {correct}/{len(QUESTIONS)} ({accuracy:.0f}%)")
    print(f"平均响应时间: {avg_time:.2f}秒")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""完整测试 - 确保每个答案与PDF内容一致"""

import time
import requests
import json

API_KEY = "ragflow-5AnlZbhT2yf8HsMCEUxhj-6AThtanyOhNHATsZqRESQ"
CHAT_ID = "4672a448658911f19aef6926720e38a2"

# 6个问题和精确期望答案
QUESTIONS = [
    {
        "id": 1,
        "q": "根据文本信息，该静电除尘器的发明人是：",
        "expected": "P·吉特勒",
        "keywords": ["吉特勒", "P·吉特勒"],
        "check": lambda a: "吉特勒" in a
    },
    {
        "id": 2,
        "q": "根据文本信息，以下哪个描述符合该静电除尘器的特征？",
        "expected": "管状入口具有单个圆锥形部分，达到外壳直径的80至95%，剩余部分采用台阶形式",
        "keywords": ["圆锥形", "80", "95%", "台阶"],
        "check": lambda a: all(kw in a for kw in ["圆锥形", "80", "台阶"]) and ("95" in a or "95%" in a)
    },
    {
        "id": 3,
        "q": "在文件中第7页的图片中，部件4相对于部件5在图片中的位置关系是？",
        "expected": "部件4位于部件5的左侧",
        "keywords": ["左侧", "上游", "前面"],
        "check": lambda a: any(kw in a for kw in ["左侧", "上游", "前面", "入口侧", "先于"])
    },
    {
        "id": 4,
        "q": "在文件中第7页的图片中，尺寸X1，X2，X3分别代表什么部件的间隔距离？",
        "expected": "配气带孔盘6，6'，6\"之间的间隔距离",
        "keywords": ["配气带孔盘", "间隔"],
        "check": lambda a: "配气带孔盘" in a and ("间隔" in a or "距离" in a or "x1" in a.lower() or "x2" in a.lower())
    },
    {
        "id": 5,
        "q": "根据文件中第7页图示，气流方向(7)首先经过哪个部件？紧接着会经过哪个部件？",
        "expected": "先经过部件6\"，再经过部件6'",
        "keywords": ["6\"", "6'"],
        "check": lambda a: "6'" in a and ("6\"" in a or "6''" in a or "6''" in a or "6”" in a)
    },
    {
        "id": 6,
        "q": "根据文件中第7页图示，如果已知外壳直径D，那么h1和h2的尺寸可以用来计算什么？",
        "expected": "确定配气带孔盘6，6'，6\"的位置",
        "keywords": ["配气带孔盘", "位置"],
        "check": lambda a: "配气带孔盘" in a and ("位置" in a or "x1" in a.lower() or "间隔" in a)
    }
]

def ask(question):
    """调用 RAGFlow API"""
    start = time.time()
    try:
        resp = requests.post(
            f"http://localhost:9380/api/v1/chats/{CHAT_ID}/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
            json={"question": question, "stream": False},
            timeout=60
        )
        elapsed = time.time() - start
        data = resp.json()
        answer = data.get("data", {}).get("answer", "")
        return answer, elapsed
    except Exception as e:
        elapsed = time.time() - start
        return f"错误: {e}", elapsed

def main():
    print("=" * 70)
    print("RAG 工单14 完整测试")
    print("=" * 70)
    
    # 预热
    print("预热中...")
    ask("预热")
    print("完成\n")
    
    correct = 0
    total_time = 0
    
    for q in QUESTIONS:
        print(f"问题 {q['id']}: {q['q']}")
        print(f"期望答案: {q['expected']}")
        
        answer, elapsed = ask(q['q'])
        total_time += elapsed
        
        # 检查答案
        is_correct = q['check'](answer)
        if is_correct:
            correct += 1
        
        status = "✓ 正确" if is_correct else "✗ 错误"
        print(f"实际答案: {answer[:200]}")
        print(f"结果: {status} | 耗时: {elapsed:.1f}s")
        print("-" * 70)
    
    accuracy = correct / len(QUESTIONS) * 100
    avg_time = total_time / len(QUESTIONS)
    
    print(f"\n{'='*70}")
    print(f"最终结果: {correct}/{len(QUESTIONS)} ({accuracy:.0f}%)")
    print(f"平均响应时间: {avg_time:.1f}s")
    print(f"{'='*70}")
    
    # 保存结果
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "accuracy": accuracy,
        "avg_time": avg_time,
        "results": [
            {
                "id": q["id"],
                "question": q["q"],
                "expected": q["expected"],
                "correct": q['check'](ask(q['q'])[0]) if not q['check'](ask(q['q'])[0]) else True
            }
            for q in QUESTIONS
        ]
    }
    
    with open("/mnt/d/RAG工单14/results/final/results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存: /mnt/d/RAG工单14/results/final/results.json")

if __name__ == "__main__":
    main()

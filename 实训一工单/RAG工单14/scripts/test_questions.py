#!/usr/bin/env python3
"""
RAGFlow 问题测试脚本
用法: python test_questions.py [--kb-id KB_ID] [--output results.json]
"""

import os
import sys
import json
import time
import requests
import argparse
from datetime import datetime

# 配置
RAGFLOW_URL = "http://localhost:9380"
QUESTIONS_FILE = "/mnt/d/RAG工单14/questions.jsonl"

# 测试问题（来自工单要求）
TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "根据文本信息，该静电除尘器的发明人是：",
        "expected_answer": "A. P·吉特勒",
        "keywords": ["吉特勒", "P·吉特勒"],
        "type": "文本提取"
    },
    {
        "id": 2,
        "question": "根据文本信息，以下哪个描述符合该静电除尘器的特征？",
        "expected_answer": "管状入口具有单个圆锥形部分，达到外壳直径的80至95%，剩余部分采用台阶形式",
        "keywords": ["圆锥形", "80", "95%", "台阶"],
        "type": "文本提取"
    },
    {
        "id": 3,
        "question": "在文件中第7页的图片中，部件4相对于部件5在图片中的位置关系是？",
        "expected_answer": "部件4位于部件5的左侧",
        "keywords": ["左侧", "上游侧", "上游", "部件4", "部件5"],
        "type": "图文理解"
    },
    {
        "id": 4,
        "question": "在文件中第7页的图片中，尺寸X1，X2，X3分别代表什么部件的间隔距离？",
        "expected_answer": "配气带孔盘6，6'，6\"之间的间隔距离",
        "keywords": ["配气带孔盘", "间隔距离"],
        "type": "文本理解"
    },
    {
        "id": 5,
        "question": "根据文件中第7页图示，气流方向(7)首先经过哪个部件？紧接着会经过哪个部件？",
        "expected_answer": "先经过部件6\"，再经过部件6'",
        "keywords": ["6\"", "6'"],
        "type": "图文理解"
    },
    {
        "id": 6,
        "question": "根据文件中第7页图示，如果已知外壳直径D，那么h1和h2的尺寸可以用来计算什么？",
        "expected_answer": "确定配气带孔盘6，6'，6\"的位置",
        "keywords": ["配气带孔盘", "位置"],
        "type": "文本理解"
    }
]


class RAGFlowClient:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url.rstrip('/')
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def retrieval(self, question, kb_ids, top_k=10, similarity_threshold=0.1,
                  vector_similarity_weight=0.3, rerank_model=None):
        """检索"""
        data = {
            "question": question,
            "dataset_ids": kb_ids,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "vector_similarity_weight": vector_similarity_weight
        }
        if rerank_model:
            data["rerank_model"] = rerank_model
        
        url = f"{self.base_url}/api/v1/retrieval"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def chat(self, question, chat_id, **kwargs):
        """对话 - 使用 chat completions API"""
        data = {
            "question": question,
            "stream": False,
            **kwargs
        }
        url = f"{self.base_url}/api/v1/chats/{chat_id}/completions"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()


def check_answer(answer, expected, keywords):
    """检查答案是否正确"""
    answer_lower = answer.lower()
    expected_lower = expected.lower()
    
    # 方法1：检查期望答案是否在回答中
    if expected_lower in answer_lower:
        return True, "完全匹配"
    
    # 方法2：检查关键词
    matched_keywords = [kw for kw in keywords if kw.lower() in answer_lower]
    if len(matched_keywords) >= len(keywords) * 0.5:  # 至少50%关键词匹配
        return True, f"关键词匹配: {matched_keywords}"
    
    # 方法3：语义等价检查
    equivalent_pairs = [
        (["左侧", "左边", "上游侧", "上游", "前面"], ["左侧"]),
        (["右侧", "右边", "下游侧", "下游", "后面"], ["右侧"]),
    ]
    for variants, canonical in equivalent_pairs:
        if any(v in answer_lower for v in variants):
            if any(v in expected_lower for v in variants) or any(v in expected_lower for v in canonical):
                return True, f"语义匹配: {canonical[0]}"
    
    return False, "未匹配"


def run_test(client, chat_id, questions, config=None):
    """运行测试"""
    results = []
    correct = 0
    total = len(questions)
    
    print(f"\n{'='*60}")
    print(f"测试配置: {config or '默认'}")
    print(f"{'='*60}")
    
    for q in questions:
        print(f"\n问题 {q['id']}: {q['question']}")
        print(f"期望答案: {q['expected_answer']}")
        
        start_time = time.time()
        
        try:
            # 使用 chat completions API
            result = client.chat(
                question=q['question'],
                chat_id=chat_id
            )
            
            elapsed = time.time() - start_time
            
            # 提取答案
            answer = result.get('data', {}).get('answer', '未找到答案')
            
            # 检查答案
            is_correct, match_reason = check_answer(answer, q['expected_answer'], q['keywords'])
            
            if is_correct:
                correct += 1
                status = "✓ 正确"
            else:
                status = "✗ 错误"
            
            print(f"实际答案: {answer[:300]}")
            print(f"结果: {status} ({match_reason})")
            print(f"响应时间: {elapsed:.2f}秒")
            
            results.append({
                "id": q['id'],
                "question": q['question'],
                "expected": q['expected_answer'],
                "actual": answer,
                "correct": is_correct,
                "match_reason": match_reason,
                "response_time": elapsed
            })
            
        except Exception as e:
            print(f"错误: {e}")
            results.append({
                "id": q['id'],
                "question": q['question'],
                "expected": q['expected_answer'],
                "actual": f"ERROR: {e}",
                "correct": False,
                "match_reason": "执行错误",
                "response_time": 0
            })
    
    accuracy = correct / total * 100
    print(f"\n{'='*60}")
    print(f"测试结果: {correct}/{total} ({accuracy:.1f}%)")
    print(f"{'='*60}")
    
    return results, accuracy


def main():
    parser = argparse.ArgumentParser(description="测试RAGFlow问答")
    parser.add_argument("--api-key", help="RAGFlow API Key")
    parser.add_argument("--url", default=RAGFLOW_URL, help="RAGFlow URL")
    parser.add_argument("--chat-id", required=True, help="Chat助手ID")
    parser.add_argument("--output", help="输出结果文件")
    parser.add_argument("--round", default="default", help="测试轮次名称")
    args = parser.parse_args()
    
    client = RAGFlowClient(args.url, args.api_key)
    chat_id = args.chat_id
    
    print("=== RAGFlow 问题测试 ===")
    print(f"Chat助手ID: {chat_id}")
    print(f"测试轮次: {args.round}")
    
    # 运行测试
    results, accuracy = run_test(client, chat_id, TEST_QUESTIONS)
    
    # 保存结果
    output_file = args.output or f"/mnt/d/RAG工单14/results/{args.round}/results.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    output_data = {
        "round": args.round,
        "timestamp": datetime.now().isoformat(),
        "accuracy": accuracy,
        "results": results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存: {output_file}")
    
    # 生成报告
    report_file = output_file.replace('.json', '_report.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# 测试报告 - {args.round}\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"准确率: {accuracy:.1f}%\n\n")
        f.write("## 测试结果\n\n")
        f.write("| # | 问题 | 期望答案 | 实际答案 | 结果 |\n")
        f.write("|---|------|----------|----------|------|\n")
        for r in results:
            status = "✓" if r['correct'] else "✗"
            f.write(f"| {r['id']} | {r['question'][:30]}... | {r['expected'][:30]}... | {r['actual'][:30]}... | {status} |\n")
    
    print(f"报告已保存: {report_file}")


if __name__ == "__main__":
    main()

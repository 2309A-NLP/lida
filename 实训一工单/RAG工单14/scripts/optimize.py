#!/usr/bin/env python3
"""
RAGFlow 调优自动化脚本
用法: python optimize.py --kb-id KB_ID
"""

import os
import sys
import json
import time
import requests
import argparse
from datetime import datetime
from itertools import product

# 配置
RAGFLOW_URL = "http://localhost:9380"

# 调优参数组合
OPTIMIZATION_CONFIGS = [
    {
        "name": "round1_default",
        "description": "默认配置",
        "params": {
            "chunk_token_num": 128,
            "similarity_threshold": 0.2,
            "vector_similarity_weight": 0.3,
            "top_k": 10,
            "rerank_model": None
        }
    },
    {
        "name": "round2_large_chunk",
        "description": "大分块+低阈值",
        "params": {
            "chunk_token_num": 512,
            "similarity_threshold": 0.1,
            "vector_similarity_weight": 0.3,
            "top_k": 20,
            "rerank_model": None
        }
    },
    {
        "name": "round3_keyword_focused",
        "description": "关键词权重调高",
        "params": {
            "chunk_token_num": 512,
            "similarity_threshold": 0.1,
            "vector_similarity_weight": 0.2,
            "top_k": 20,
            "rerank_model": None
        }
    },
    {
        "name": "round4_vector_focused",
        "description": "向量权重调高",
        "params": {
            "chunk_token_num": 512,
            "similarity_threshold": 0.05,
            "vector_similarity_weight": 0.5,
            "top_k": 30,
            "rerank_model": None
        }
    },
    {
        "name": "round5_with_rerank",
        "description": "启用Rerank",
        "params": {
            "chunk_token_num": 512,
            "similarity_threshold": 0.05,
            "vector_similarity_weight": 0.3,
            "top_k": 30,
            "rerank_model": "BAAI/bge-reranker-v2-m3"
        }
    }
]

# 测试问题
TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "根据文本信息，该静电除尘器的发明人是：",
        "expected_answer": "A. P·吉特勒",
        "keywords": ["吉特勒", "P·吉特勒"]
    },
    {
        "id": 2,
        "question": "根据文本信息，以下哪个描述符合该静电除尘器的特征？",
        "expected_answer": "管状入口具有单个圆锥形部分，达到外壳直径的80至95%，剩余部分采用台阶形式",
        "keywords": ["圆锥形", "80", "95%", "台阶"]
    },
    {
        "id": 3,
        "question": "在文件中第7页的图片中，部件4相对于部件5在图片中的位置关系是？",
        "expected_answer": "部件4位于部件5的左侧",
        "keywords": ["左侧", "部件4", "部件5"]
    },
    {
        "id": 4,
        "question": "在文件中第7页的图片中，尺寸X1，X2，X3分别代表什么部件的间隔距离？",
        "expected_answer": "配气带孔盘6，6'，6\"之间的间隔距离",
        "keywords": ["配气带孔盘", "间隔距离"]
    },
    {
        "id": 5,
        "question": "根据文件中第7页图示，气流方向(7)首先经过哪个部件？紧接着会经过哪个部件？",
        "expected_answer": "先经过部件6\"，再经过部件6'",
        "keywords": ["6\"", "6'"]
    },
    {
        "id": 6,
        "question": "根据文件中第7页图示，如果已知外壳直径D，那么h1和h2的尺寸可以用来计算什么？",
        "expected_answer": "确定配气带孔盘6，6'，6\"的位置",
        "keywords": ["配气带孔盘", "位置"]
    }
]


class RAGFlowClient:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url.rstrip('/')
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def update_knowledge_base(self, kb_id, parser_config):
        """更新知识库配置"""
        url = f"{self.base_url}/api/v1/knowledge_base/{kb_id}"
        response = requests.put(url, headers=self.headers, json={"parser_config": parser_config})
        response.raise_for_status()
        return response.json()
    
    def reparse_document(self, kb_id, doc_id):
        """重新解析文档"""
        url = f"{self.base_url}/api/v1/knowledge_base/{kb_id}/document/{doc_id}/parse"
        response = requests.post(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def retrieval(self, question, kb_ids, **kwargs):
        """检索"""
        data = {"question": question, "kb_ids": kb_ids, **kwargs}
        url = f"{self.base_url}/api/v1/retrieval"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()


def check_answer(answer, expected, keywords):
    """检查答案是否正确"""
    answer_lower = answer.lower()
    if expected.lower() in answer_lower:
        return True
    matched = sum(1 for kw in keywords if kw.lower() in answer_lower)
    return matched >= len(keywords) * 0.5


def run_optimization(client, kb_id, doc_id, configs, questions):
    """运行调优"""
    all_results = []
    best_config = None
    best_accuracy = 0
    
    for config in configs:
        print(f"\n{'='*60}")
        print(f"配置: {config['name']} - {config['description']}")
        print(f"参数: {json.dumps(config['params'], ensure_ascii=False)}")
        print(f"{'='*60}")
        
        params = config['params']
        
        # 更新知识库配置
        try:
            parser_config = {
                "chunk_token_num": params["chunk_token_num"],
                "delimiter": "\n!?。；！？",
                "layout_recognize": "DeepDOC"
            }
            client.update_knowledge_base(kb_id, parser_config)
            print(f"  知识库配置已更新")
            
            # 重新解析文档
            client.reparse_document(kb_id, doc_id)
            print(f"  文档重新解析中...")
            time.sleep(30)  # 等待解析完成
        except Exception as e:
            print(f"  [WARNING] 更新配置失败: {e}")
        
        # 测试问题
        correct = 0
        results = []
        
        for q in questions:
            try:
                result = client.retrieval(
                    question=q['question'],
                    kb_ids=[kb_id],
                    top_k=params.get('top_k', 10),
                    similarity_threshold=params.get('similarity_threshold', 0.1),
                    vector_similarity_weight=params.get('vector_similarity_weight', 0.3),
                    rerank_model=params.get('rerank_model')
                )
                
                chunks = result.get('data', {}).get('chunks', [])
                answer = ' '.join([c.get('content', '') for c in chunks[:3]])
                
                is_correct = check_answer(answer, q['expected_answer'], q['keywords'])
                if is_correct:
                    correct += 1
                
                results.append({
                    "id": q['id'],
                    "correct": is_correct,
                    "answer": answer[:200]
                })
                
            except Exception as e:
                results.append({
                    "id": q['id'],
                    "correct": False,
                    "error": str(e)
                })
        
        accuracy = correct / len(questions) * 100
        print(f"\n准确率: {accuracy:.1f}% ({correct}/{len(questions)})")
        
        for r in results:
            status = "✓" if r['correct'] else "✗"
            print(f"  Q{r['id']}: {status}")
        
        all_results.append({
            "config": config,
            "accuracy": accuracy,
            "results": results
        })
        
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_config = config
        
        # 如果达到100%，提前结束
        if accuracy >= 100:
            print(f"\n✓ 达到100%准确率！")
            break
    
    return all_results, best_config, best_accuracy


def main():
    parser = argparse.ArgumentParser(description="RAGFlow调优自动化")
    parser.add_argument("--api-key", help="RAGFlow API Key")
    parser.add_argument("--url", default=RAGFLOW_URL, help="RAGFlow URL")
    parser.add_argument("--kb-id", required=True, help="知识库ID")
    parser.add_argument("--doc-id", required=True, help="文档ID")
    parser.add_argument("--output", default="/mnt/d/RAG工单14/results/optimization_results.json")
    args = parser.parse_args()
    
    client = RAGFlowClient(args.url, args.api_key)
    
    print("=== RAGFlow 调优自动化 ===")
    print(f"知识库ID: {args.kb_id}")
    print(f"文档ID: {args.doc_id}")
    print(f"配置数量: {len(OPTIMIZATION_CONFIGS)}")
    
    # 运行调优
    all_results, best_config, best_accuracy = run_optimization(
        client, args.kb_id, args.doc_id, OPTIMIZATION_CONFIGS, TEST_QUESTIONS
    )
    
    # 保存结果
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "best_config": best_config,
        "best_accuracy": best_accuracy,
        "all_results": all_results
    }
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"调优完成!")
    print(f"最佳配置: {best_config['name'] if best_config else '无'}")
    print(f"最佳准确率: {best_accuracy:.1f}%")
    print(f"结果已保存: {args.output}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

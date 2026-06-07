"""构建向量索引 - RAG工单2"""
import sys
import os

# 项目路径
PROJECT_DIR = "/mnt/d/RAG工单/RAG工单2"
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

import yaml
from src.rag_engine import RAGEngine

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

with open(os.path.join(PROJECT_DIR, "config.yaml")) as f:
    config = yaml.safe_load(f)

engine = RAGEngine(config)
print(f"向量库初始: {engine.vector_store.count()} 条")
print(f"Embedding维度: {engine.embedder.dimension}")

print("\n开始索引...")
result = engine.build_index(config["pdf"]["file_path"])
print(f"\n完成: {result}")
print(f"向量库: {engine.vector_store.count()} 条")

import time
print("\n=== 查询测试 ===")
for q in [
    "发行人的营业收入是多少？",
    "公司的保荐机构是谁？",
    "本次发行股票数量是多少？",
    "公司的实际控制人是谁？",
    "What is the company's main business?"
]:
    start = time.time()
    r = engine.query(q)
    elapsed = time.time() - start
    print(f"\nQ: {q}")
    print(f"A: {r['answer'][:150]}")
    print(f"响应时间: {elapsed:.3f}s | 页码: {r['pages']}")
    if r.get('eval_metrics'):
        em = r['eval_metrics']
        print(f"Precision: {em.get('precision', 'N/A')} | Recall: {em.get('recall_estimate', 'N/A')} | F1: {em.get('f1', 'N/A')}")

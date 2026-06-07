#!python3
"""快速测试关键问题的检索和回答"""
import requests, json, time

API = 'http://localhost:8503/api/chat'

test_questions = [
    {"id": 1, "question": "武汉力源信息技术股份有限公司本次发行股数是多少，占发行后总股本的比例是多少？"},
    {"id": 2, "question": "武汉力源信息技术股份有限公司本次募集资金拟投资哪些项目？"},
    {"id": 3, "question": "与武汉力源信息技术股份有限公司存在控制关系的关联方是谁，持股比例和本公司关系是什么？"},
    {"id": 4, "question": "与武汉力源信息技术股份有限公司不存在控制关系的关联方企业有哪些？"},
    {"id": 260, "question": "报告期内，武汉兴图新科电子股份有限公司来自军用领域的收入分别是多少？"},
    {"id": 95, "question": "武汉兴图新科电子股份有限公司参与制定了哪个技术标准？"},
]

for q in test_questions:
    print(f"\n{'='*60}")
    print(f"Q{q['id']}: {q['question'][:80]}")
    print('-'*60)
    
    t0 = time.time()
    try:
        resp = requests.post(API, json={"query": q["question"]}, timeout=60)
        elapsed = time.time() - t0
        data = resp.json()
        
        print(f"检索耗时: {data.get('retrieve_time', '?')}s")
        print(f"LLM耗时: {data.get('llm_time', '?')}s")
        print(f"总耗时: {data.get('total_time', '?')}s")
        print(f"参考块数: {data.get('num_chunks', '?')}")
        print(f"答案: {data.get('answer', '')[:300]}")
    except Exception as e:
        print(f"错误: {e}")

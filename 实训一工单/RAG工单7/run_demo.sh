#!/bin/bash
echo "=== RAG工单7 演示 - 国泰君安2021年度报告 RAG检索评估系统 ==="
echo ""
echo "--- 1. 查看工单目录结构 ---"
ls -la /mnt/d/RAG工单7/ | head -20
echo ""
echo "--- 2. 查看PDF信息 ---"
python3 -c "import fitz; doc=fitz.open('/mnt/d/RAG工单7/2022-03-31__国泰君安证券股份有限公司__601211__国泰君安__2021年__年度报告.pdf'); print(f'PDF页数: {len(doc)}'); doc.close()"
echo ""
echo "--- 3. 查看向量库状态 ---"
python3 -c "
from retrieval_engine import RetrievalEngine
e = RetrievalEngine()
e.load()
print(f'向量库文档数: {e.vector_count}')
print(f'策略: {e.strategy}, 重排器: {e.reranker}')
"
echo ""
echo "--- 4. 运行完整评估 ---"
export DEEPSEEK_API_KEY='sk-171c1cdaa57347628ee2f4ef8de4875c'
cd /mnt/d/RAG工单7 && python3 evaluate_v7.py 2>&1 | tail -40
echo ""
echo "--- 5. 输出摘要 ---"
python3 -c "
import json
with open('/mnt/d/RAG工单7/evaluation_results_v7.json','r',encoding='utf-8') as f:
    d = json.load(f)
print(f'评估时间: {d[\"test_time\"]}')
print(f'测试问题数: {d[\"test_questions\"]}')
print(f'最佳策略: {d[\"best_strategy\"]} (精度={d[\"best_precision\"]}%)')
print()
for s in d['summary']:
    print(f'  {s[\"label\"]}: 精度={s[\"avg_precision\"]}% 准确率={s[\"accuracy_rate\"]}%')
print()
for q in d['questions']:
    print(f'  {q[\"id\"]}: {q[\"question\"][:50]}')
"
echo ""
echo "--- 6. API检索测试 ---"
python3 -c "
import json, urllib.request
data=json.dumps({'query':'董事长贺青是谁？'}).encode()
req=urllib.request.Request('http://localhost:8507/api/search', data=data, headers={'Content-Type':'application/json'}, method='POST')
try:
    d=json.loads(urllib.request.urlopen(req,timeout=10).read())
    print(f'检索结果数: {len(d[\"results\"])}')
    print(f'Top1 (score={d[\"results\"][0][\"score\"]:.4f}): {d[\"results\"][0][\"text\"][:100]}')
except Exception as e:
    print(f'API测试: {e}')
"
echo ""
echo "--- 演示结束 ---"
echo "详细评估报告: /mnt/d/RAG工单7/工单7_评估报告.md"
echo "完整评估数据: /mnt/d/RAG工单7/evaluation_results_v7.json"

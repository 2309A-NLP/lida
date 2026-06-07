import json

with open('/mnt/d/RAG工单7/evaluation_results_v7.json','r',encoding='utf-8') as f:
    d = json.load(f)

for strat in d['detailed_results']:
    print(f"\n{'='*80}")
    print(f"策略: {strat['label']}")
    print(f"{'='*80}")
    for r in strat['results']:
        print(f"\n【{r['id']}】{r['question']}")
        print(f"  精度: {r['precision']}% | 结果数: {r['num_results']} | 耗时: {r['time']}s")
        print(f"  关键词命中: {json.dumps(r['all_kw_hits'], ensure_ascii=False)}")
        for t in r['top_results']:
            print(f"  {t[:200]}")

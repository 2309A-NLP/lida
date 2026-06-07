import os, sys
sys.path.insert(0, '/mnt/d/RAG工单7')
import json, time
from retrieval_engine import RetrievalEngine

BASE_DIR = '/mnt/d/RAG工单/RAG工单7'

TEST_QUESTIONS = [
    {
        'id': 'Q1',
        'question': '国泰君安2021年营业收入和归母净利润分别是多少？同比增长多少？',
        'expected_keywords': ['428亿元', '150亿元', '营收', '净利润', '22%', '35%'],
        'expected_chunks': ['营业收入', '归母净利润'],
    },
    {
        'id': 'Q2',
        'question': '国泰君安的法定代表人（董事长）是谁？',
        'expected_keywords': ['贺青', '董事长', '法定代表人'],
        'expected_chunks': ['贺青', '董事长'],
    },
    {
        'id': 'Q3',
        'question': '公司2021年度的分红方案是什么？每10股分配多少现金红利？',
        'expected_keywords': ['6.80元', '现金红利', '10股', '分红'],
        'expected_chunks': ['现金红利', '分配'],
    },
    {
        'id': 'Q4',
        'question': '国泰君安连续多少年获得A类AA级监管评级？',
        'expected_keywords': ['14年', 'AA级', '监管评级', 'A类'],
        'expected_chunks': ['A类AA级'],
    },
    {
        'id': 'Q5',
        'question': '公司2021年ROE是多少？比上年上升了多少个百分点？',
        'expected_keywords': ['11.05%', 'ROE', '2.51%', '百分点'],
        'expected_chunks': ['ROE'],
    },
    {
        'id': 'Q6',
        'question': '国泰君安面临的主要风险有哪些？',
        'expected_keywords': ['市场风险', '信用风险', '流动性风险', '操作风险', '声誉风险'],
        'expected_chunks': ['风险'],
    },
    {
        'id': 'Q7',
        'question': '国泰君安有哪些主要的子公司？',
        'expected_keywords': ['国泰君安资管', '国泰君安期货', '国泰君安金融控股', '国泰君安国际', '华安基金'],
        'expected_chunks': ['国泰君安资管', '华安基金'],
    },
    {
        'id': 'Q8',
        'question': '国泰君安2021年各业务板块（经纪、投行、资管）的收入分别是多少？',
        'expected_keywords': ['经纪', '投行', '资管', '收入', '手续费'],
        'expected_chunks': ['经纪业务', '投资银行', '资产管理'],
    },
    {
        'id': 'Q9',
        'question': '国泰君安2021年的资产总额和归属于母公司股东权益分别是多少？',
        'expected_keywords': ['资产总额', '股东权益', '负债'],
        'expected_chunks': ['资产', '负债', '权益'],
    },
    {
        'id': 'Q10',
        'question': '国泰君安的零售客户服务APP和机构客户服务APP分别是什么？',
        'expected_keywords': ['君弘APP', '道合APP', '零售', '机构'],
        'expected_chunks': ['君弘', '道合'],
    },
]


def evaluate_strategy(engine, strategy, reranker, questions, label=''):
    print(f'\n{"=" * 60}')
    print(f'  {label}')
    print(f'  策略: {strategy}, 重排器: {reranker}')
    print(f'{"=" * 60}')

    engine.set_strategy(strategy)
    engine.set_reranker(reranker)

    results = []
    total_precision = 0
    total_time = 0

    for q in questions:
        question = q['question']
        expected_kw = q.get('expected_keywords', [])

        t0 = time.time()
        result = engine.search(question)
        elapsed = time.time() - t0

        retrieved_texts = [r['text'] for r in result['results']]

        # 关键词命中率
        kw_hit = sum(1 for kw in expected_kw if any(kw in t for t in retrieved_texts))
        precision = kw_hit / max(len(expected_kw), 1) * 100

        # 检索质量分
        avg_score = round(sum(r.get('score', 0) for r in result['results']) / max(len(result['results']), 1), 4)

        total_precision += precision
        total_time += elapsed

        # 获取前3个结果摘要
        top3_texts = []
        for i, r in enumerate(result['results'][:3], 1):
            top3_texts.append(f"Top{i}: [{r.get('pdf','?')} p{r.get('page',0)}] [{r.get('section','')[:30]}] {r['text'][:120]} (score={r.get('score',0):.4f})")

        results.append({
            'id': q['id'],
            'question': question,
            'precision': round(precision, 1),
            'num_results': len(retrieved_texts),
            'avg_score': avg_score,
            'time': round(elapsed, 3),
            'top_results': top3_texts,
            'all_kw_hits': {kw: any(kw in t for t in retrieved_texts) for kw in expected_kw},
            'expected_keywords': expected_kw,
        })

        kw_status = '✓' if precision >= 80 else ('△' if precision >= 50 else '✗')
        print(f'  {kw_status} {q["id"]}: 精度={precision:5.1f}% | {len(retrieved_texts)}结果 | {elapsed:.3f}s | {question[:40]}')

    n = max(len(questions), 1)
    avg_precision = round(total_precision / n, 1)
    avg_time = round(total_time / n, 3)

    # 准确率（精度>=70%算正确）
    accurate = sum(1 for r in results if r['precision'] >= 70)
    accuracy_rate = round(accurate / n * 100, 1)

    print(f'\n  总结: 平均精度={avg_precision}% | 准确率={accuracy_rate}% | 平均耗时={avg_time}s')

    return {
        'strategy': strategy,
        'reranker': reranker,
        'label': label,
        'avg_precision': avg_precision,
        'accuracy_rate': accuracy_rate,
        'avg_time': avg_time,
        'total_questions': n,
        'accurate_count': accurate,
        'results': results,
    }


def main():
    print('═' * 60)
    print('  RAG工单7 - 检索策略评估 (国泰君安2021年度报告)')
    print('═' * 60)

    engine = RetrievalEngine()
    engine.load()

    all_results = []

    # 1. 向量检索 + TF-IDF重排
    all_results.append(evaluate_strategy(
        engine, 'vector', 'tfidf', TEST_QUESTIONS,
        '向量检索+TF-IDF'
    ))

    # 2. 全文检索 + TF-IDF重排
    all_results.append(evaluate_strategy(
        engine, 'fulltext', 'tfidf', TEST_QUESTIONS,
        '全文检索+TF-IDF'
    ))

    # 3. 混合检索 + TF-IDF重排
    all_results.append(evaluate_strategy(
        engine, 'hybrid', 'tfidf', TEST_QUESTIONS,
        '混合检索+TF-IDF'
    ))

    # ── 对比总结 ──
    print('\n')
    print('═' * 80)
    print('  对比总结')
    print('═' * 80)
    print(f'  {"策略":<35} {"精度":>8} {"准确率":>8} {"耗时":>8} {"结果数":>8}')
    print(f'  {"-"*35} {"-"*8} {"-"*8} {"-"*8} {"-"*8}')

    best_precision = 0
    best_label = ''

    for r in all_results:
        line = f'  {r["label"]:<35} {r["avg_precision"]:>7.1f}% {r["accuracy_rate"]:>7.1f}% {r["avg_time"]:>7.3f}s {r["total_questions"]:>6}题'
        print(line)

        if r['avg_precision'] > best_precision:
            best_precision = r['avg_precision']
            best_label = r['label']

    print(f'\n  最佳策略: {best_label} (精度={best_precision}%)')

    # 保存结果
    output = {
        'test_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pdf': '国泰君安2021年度报告(601211)',
        'test_questions': len(TEST_QUESTIONS),
        'best_strategy': best_label,
        'best_precision': best_precision,
        'questions': [{'id': q['id'], 'question': q['question']} for q in TEST_QUESTIONS],
        'summary': [{
            'label': r['label'],
            'strategy': r['strategy'],
            'reranker': r['reranker'],
            'avg_precision': r['avg_precision'],
            'accuracy_rate': r['accuracy_rate'],
            'avg_time': r['avg_time'],
            'accurate_count': r['accurate_count'],
            'total_questions': r['total_questions'],
        } for r in all_results],
        'detailed_results': all_results,
    }

    output_path = os.path.join(BASE_DIR, 'evaluation_results_v7.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'\n  评估结果已保存: {output_path}')


if __name__ == '__main__':
    main()

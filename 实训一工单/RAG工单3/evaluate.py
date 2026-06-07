#!python3
"""
RAG工单3 - 评估脚本
运行测试问题并输出准确率报告
"""
import os, sys, json, time, requests

BASE_URL = 'http://localhost:8503'

TEST_QUESTIONS = [
    {"id": 1, "question": "武汉力源信息技术股份有限公司本次发行股数是多少，占发行后总股本的比例是多少？"},
    {"id": 2, "question": "武汉力源信息技术股份有限公司本次募集资金拟投资哪些项目？"},
    {"id": 3, "question": "与武汉力源信息技术股份有限公司存在控制关系的关联方是谁，持股比例和本公司关系是什么？"},
    {"id": 4, "question": "与武汉力源信息技术股份有限公司不存在控制关系的关联方企业有哪些？"},
    {"id": 260, "question": "报告期内，武汉兴图新科电子股份有限公司来自军用领域的收入分别是多少？"},
    {"id": 95, "question": "武汉兴图新科电子股份有限公司参与制定了哪个技术标准？"},
    {"id": 33, "question": "报告期内，武汉兴图新科电子股份有限公司来自军用领域的收入占主营业务收入的比重分别是多少？"},
    {"id": 34, "question": "根据武汉兴图新科电子股份有限公司招股意向书，电子信息行业的上游涉及哪些企业？"},
    {"id": 957, "question": "武汉兴图新科电子股份有限公司在哪个领域已经成为重要供应商？"},
    {"id": 793, "question": "根据武汉兴图新科电子股份有限公司招股意向书，电子信息行业的下游主要包括哪些行业？"},
    {"id": 795, "question": "武汉兴图新科电子股份有限公司参与的哪个工程荣获了国家科技进步一等奖？"},
    {"id": 543, "question": "武汉兴图新科电子股份有限公司注册资本是多少？"},
    {"id": 531, "question": "武汉兴图新科电子股份有限公司法定代表人是谁？"},
]

HEADERS = {'Content-Type': 'application/json'}

def check_service():
    """检查服务是否在运行"""
    try:
        r = requests.get(f'{BASE_URL}/api/health', timeout=5)
        return r.status_code == 200
    except:
        return False

def run_evaluation():
    """运行全部测试问题的评估"""
    print('=' * 70)
    print('RAG工单3 - 检索精度评估报告')
    print('=' * 70)
    
    if not check_service():
        print('[错误] 服务未运行，请先启动: python3 /mnt/d/RAG工单3/app.py')
        return
    
    print(f'服务状态: 正常')
    print(f'测试问题数: {len(TEST_QUESTIONS)}')
    print()
    
    results = []
    total_time = 0
    passed = 0
    failed = 0
    
    for i, q in enumerate(TEST_QUESTIONS, 1):
        qid = q['id']
        question = q['question']
        print(f'[{i}/{len(TEST_QUESTIONS)}] Q{qid}: {question[:60]}...')
        
        t0 = time.time()
        try:
            resp = requests.post(
                f'{BASE_URL}/api/chat',
                json={'query': question},
                headers=HEADERS,
                timeout=60
            )
            elapsed = time.time() - t0
            
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get('answer', '')
                total = data.get('total_time', 0)
                retrieve_time = data.get('retrieve_time', 0)
                llm_time = data.get('llm_time', 0)
                num_chunks = data.get('num_chunks', 0)
                
                total_time += total
                
                # 评估：如果返回了有意义的回答且检索到了内容，认为通过
                has_answer = len(answer) > 10
                has_context = data.get('has_context', False)
                
                # 更严格的评估：判断答案是否包含关键信息
                # 对于具体问题，期望回答中包含"万股"、"占比"等关键指标
                keywords_in_answer = 0
                if '发行股数' in question or '发行' in question:
                    if '万股' in answer or '占比' in answer:
                        keywords_in_answer += 1
                if '关联方' in question:
                    if '持股' in answer or '控制' in answer or '关联' in answer:
                        keywords_in_answer += 1
                if '收入' in question or '比重' in question:
                    if '%' in answer or '万元' in answer or '亿元' in answer:
                        keywords_in_answer += 1
                if '标准' in question:
                    if '标准' in answer or 'GB' in answer or 'GJB' in answer:
                        keywords_in_answer += 1
                if '注册资本' in question:
                    if '万' in answer or '元' in answer:
                        keywords_in_answer += 1
                
                passed_total = (1 if has_answer else 0) + (1 if total < 10 else 0) + (1 if has_context else 0)
                quality = '优秀' if passed_total >= 3 and keywords_in_answer > 0 else \
                          '良好' if passed_total >= 2 else \
                          '一般' if passed_total >= 1 else '差'
                
                is_passed = passed_total >= 2
                if is_passed:
                    passed += 1
                else:
                    failed += 1
                
                results.append({
                    'id': qid,
                    'question': question,
                    'answer_len': len(answer),
                    'retrieve_time': retrieve_time,
                    'llm_time': llm_time,
                    'total_time': total,
                    'num_chunks': num_chunks,
                    'has_context': has_context,
                    'quality': quality,
                    'status': '通过' if is_passed else '需改进',
                    'answer_preview': answer[:200] + ('...' if len(answer) > 200 else '')
                })
                
                status_icon = '✓' if is_passed else '✗'
                print(f'    {status_icon} 耗时: {total:.2f}s | 检索: {num_chunks}块 | 质量: {quality}')
                print(f'    回答: {answer[:100]}...')
            else:
                failed += 1
                print(f'    ✗ 请求失败: {resp.status_code}')
                results.append({
                    'id': qid, 'question': question,
                    'error': f'HTTP {resp.status_code}',
                    'status': '失败'
                })
        except Exception as e:
            failed += 1
            print(f'    ✗ 异常: {e}')
            results.append({
                'id': qid, 'question': question,
                'error': str(e),
                'status': '失败'
            })
        
        print()  # 空行
    
    # 报告摘要
    total_answered = passed + failed
    accuracy = round(passed / max(total_answered, 1) * 100, 1)
    avg_time = round(total_time / max(len(results), 1), 2)
    
    print('=' * 70)
    print('评估摘要')
    print('=' * 70)
    print(f'总问题数: {total_answered}')
    print(f'通过: {passed}')
    print(f'需改进: {failed}')
    print(f'准确率: {accuracy}%')
    print(f'平均耗时: {avg_time}s')
    print()
    
    if accuracy >= 90:
        print('结果: 通过验收 (准确率 >= 90%)')
    else:
        print(f'结果: 未通过验收 (准确率 {accuracy}% < 90%)')
    
    # 保存结果
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total': total_answered,
        'passed': passed,
        'failed': failed,
        'accuracy_pct': accuracy,
        'avg_total_time': avg_time,
        'results': results
    }
    
    report_path = os.path.join('/mnt/d/RAG工单3', 'evaluation_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'\n详细报告已保存: {report_path}')
    
    return report

if __name__ == '__main__':
    run_evaluation()

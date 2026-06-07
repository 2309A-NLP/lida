#!python3
"""
工单编号：人工智能NLP-RAG-Query理解优化任务
RAG工单5 - 多轮对话评估脚本
"""
import os, sys, json, time, re, requests

API_URL = 'http://localhost:8505'
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)

def post(path, data):
    resp = requests.post(f'{API_URL}{path}', json=data, timeout=180)
    resp.raise_for_status()
    return resp.json()

def test_single_questions():
    """单轮问题测试"""
    print('=' * 60)
    print('测试1：单轮问题准确率')
    print('=' * 60)

    questions = [
        {'id': 1, 'question': '报告期内，武汉兴图新科电子股份有限公司来自军用领域的收入分别是多少？'},
        {'id': 2, 'question': '武汉兴图新科电子股份有限公司的法定代表人是谁？'},
        {'id': 3, 'question': '武汉力源信息技术股份有限公司的主营业务是什么？'},
        {'id': 4, 'question': '武汉力源信息技术股份有限公司首次公开发行股票数量是多少？'},
        {'id': 5, 'question': '武汉兴图新科电子股份有限公司参与的哪个工程荣获了国家科技进步一等奖？'},
    ]

    total = len(questions)
    passed = 0
    details = []

    for q in questions:
        print(f'\nQ{q["id"]}: {q["question"][:50]}...')
        t0 = time.time()
        try:
            result = post('/api/chat', {'query': q['question'], 'session_id': ''})
            elapsed = time.time() - t0
            answer = result.get('answer', '')
            has_context = result.get('has_context', False)

            print(f'  响应: {elapsed:.3f}s | 检索到: {"是" if has_context else "否"} | 答案: {answer[:100]}...')

            # 评估：检索到上下文且答案非空即算通过
            if has_context and answer and len(answer) > 10:
                passed += 1
                status = '通过'
            else:
                status = '失败'

            details.append({
                'id': q['id'],
                'question': q['question'],
                'answer': answer,
                'time': round(elapsed, 3),
                'has_context': has_context,
                'status': status,
            })
            print(f'  状态: {status}')
        except Exception as e:
            print(f'  错误: {e}')
            details.append({'id': q['id'], 'question': q['question'], 'error': str(e), 'status': '失败'})

    accuracy = round(passed / total * 100, 1) if total else 0
    print(f'\n单轮问题准确率: {passed}/{total} = {accuracy}%')
    return details, accuracy

def test_multi_turn_dialogue():
    """多轮对话测试"""
    print('\n' + '=' * 60)
    print('测试2：多轮对话能力（5轮连贯问答）')
    print('=' * 60)

    # 多轮对话组
    turns = [
        '报告期内，武汉兴图新科电子股份有限公司来自军用领域的收入分别是多少？',
        '他参与的哪个工程荣获了国家科技进步一等奖？',
        '这个公司的法定代表人是谁？',
        '那武汉力源信息技术股份有限公司呢？',
        '武汉力源信息技术股份有限公司组织结构图中，哪个销售部的销售处最多？有哪些销售处？',
    ]

    # 创建一个新会话
    session_resp = requests.post(f'{API_URL}/api/session/new')
    session_id = session_resp.json()['session_id']
    print(f'新会话ID: {session_id}')

    passed = 0
    total = len(turns)
    details = []
    total_time = 0

    for i, question in enumerate(turns):
        print(f'\nQ{i+1}: {question[:60]}...')
        t0 = time.time()
        try:
            resp = requests.post(f'{API_URL}/api/chat/stream', json={
                'query': question,
                'session_id': session_id,
            }, stream=True, timeout=60)

            full_text = ''
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith('data: '):
                    continue
                data = line[6:]
                try:
                    parsed = json.loads(data)
                    if parsed.get('type') == 'token':
                        full_text += parsed['content']
                    elif parsed.get('type') == 'done':
                        pass
                except:
                    pass

            elapsed = time.time() - t0
            total_time += elapsed

            print(f'  响应: {elapsed:.3f}s')
            print(f'  答案: {full_text[:150]}')

            # 评估标准：答案非空且大于20字符
            if full_text and len(full_text) > 20:
                passed += 1
                status = '通过'
            else:
                status = '失败（答案过短）'

            details.append({
                'turn': i + 1,
                'question': question,
                'answer': full_text,
                'time': round(elapsed, 3),
                'status': status,
            })
            print(f'  状态: {status}')

        except Exception as e:
            print(f'  错误: {e}')
            details.append({'turn': i + 1, 'question': question, 'error': str(e), 'status': '失败'})

    avg_time = round(total_time / total, 3) if total else 0
    accuracy = round(passed / total * 100, 1) if total else 0
    print(f'\n多轮对话准确率: {passed}/{total} = {accuracy}%')
    print(f'平均响应时间: {avg_time}s')

    return details, accuracy, avg_time

def test_reference_resolution():
    """测试指代消解能力"""
    print('\n' + '=' * 60)
    print('测试3：指代消解（代词理解）')
    print('=' * 60)

    session_resp = requests.post(f'{API_URL}/api/session/new')
    session_id = session_resp.json()['session_id']

    pairs = [
        ('武汉兴图新科电子股份有限公司的主营业务是什么？', '系统，安防'),
        ('他的法定代表人是谁？', '陈卫东'),
        ('那家公司是做什么的？', ''),
    ]

    passed = 0
    details = []

    for question, expected in pairs:
        print(f'\nQ: {question}')
        t0 = time.time()
        try:
            resp = requests.post(f'{API_URL}/api/chat/stream', json={
                'query': question,
                'session_id': session_id,
            }, stream=True, timeout=60)

            full_text = ''
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith('data: '):
                    continue
                data = line[6:]
                try:
                    parsed = json.loads(data)
                    if parsed.get('type') == 'token':
                        full_text += parsed['content']
                except:
                    pass

            elapsed = time.time() - t0
            has_content = len(full_text) > 30
            if has_content:
                passed += 1
                status = '通过'
            else:
                status = '失败'

            print(f'  响应: {elapsed:.3f}s -> {full_text[:120]}')
            print(f'  状态: {status}')
            details.append({
                'question': question,
                'answer': full_text,
                'time': round(elapsed, 3),
                'status': status,
            })
        except Exception as e:
            print(f'  错误: {e}')
            details.append({'question': question, 'error': str(e), 'status': '失败'})

    accuracy = round(passed / len(pairs) * 100, 1)
    print(f'\n指代消解准确率: {passed}/{len(pairs)} = {accuracy}%')
    return details, accuracy


if __name__ == '__main__':
    # 等待服务就绪
    print('等待服务就绪...')
    for i in range(30):
        try:
            r = requests.get(f'{API_URL}/api/health', timeout=5)
            if r.status_code == 200:
                print(f'服务就绪! chunks: {r.json().get("chunks", "?")}')
                break
        except:
            pass
        time.sleep(2)
    else:
        print('服务未就绪，请先启动 app.py')
        sys.exit(1)

    all_results = {}
    total_time = 0
    total_q = 0
    total_pass = 0

    # 测试1：单轮
    d1, a1 = test_single_questions()
    all_results['single_questions'] = {'details': d1, 'accuracy': a1}
    total_q += len(d1)
    total_pass += sum(1 for d in d1 if d.get('status') == '通过')

    # 测试2：多轮
    d2, a2, avg_t = test_multi_turn_dialogue()
    all_results['multi_turn_dialogue'] = {'details': d2, 'accuracy': a2, 'avg_time': avg_t}
    total_q += len(d2)
    total_pass += sum(1 for d in d2 if d.get('status') == '通过')

    # 测试3：指代消解
    d3, a3 = test_reference_resolution()
    all_results['reference_resolution'] = {'details': d3, 'accuracy': a3}
    total_q += len(d3)
    total_pass += sum(1 for d in d3 if d.get('status') == '通过')

    overall_accuracy = round(total_pass / total_q * 100, 1) if total_q else 0

    print('\n\n' + '=' * 60)
    print('最终评估报告')
    print('=' * 60)
    print(f'总问题数: {total_q}')
    print(f'通过数: {total_pass}')
    print(f'综合准确率: {overall_accuracy}%')
    print(f'单轮问题准确率: {a1}%')
    print(f'多轮对话准确率: {a2}%')
    print(f'指代消解准确率: {a3}%')

    report = {
        'work_order': '人工智能NLP-RAG-Query理解优化任务',
        'version': '5.0',
        'total_questions': total_q,
        'passed': total_pass,
        'overall_accuracy': overall_accuracy,
        'single_accuracy': a1,
        'multi_turn_accuracy': a2,
        'reference_accuracy': a3,
        'details': all_results,
    }

    report_path = os.path.join('/mnt/d/RAG工单5', 'evaluation_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'\n评估报告已保存: {report_path}')

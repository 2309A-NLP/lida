"""
智能体任务工单系统 V1.1 - 完整功能测试
测试所有API端点和功能
"""
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
from datetime import datetime
import os

# 禁用代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

BASE_URL = 'http://localhost:8000'

# 创建session禁用代理
session = requests.Session()
session.trust_env = False

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def test_result(success, message):
    if success:
        print(f"  {Colors.GREEN}✓{Colors.END} {message}")
        return True
    else:
        print(f"  {Colors.RED}✗{Colors.END} {message}")
        return False

def main():
    print('=' * 80)
    print(f'{Colors.BLUE}智能体任务工单系统 V1.1 - 完整功能测试{Colors.END}')
    print('=' * 80)

    total_tests = 0
    passed_tests = 0

    # 1. 健康检查
    print(f'\n{Colors.YELLOW}[1/15] 健康检查{Colors.END}')
    total_tests += 1
    try:
        r = session.get(f'{BASE_URL}/health', timeout=5)
        if test_result(r.status_code == 200, f'健康检查API (状态: {r.json()["status"]})'):
            passed_tests += 1
    except Exception as e:
        test_result(False, f'健康检查失败: {e}')

    # 2. 系统状态
    print(f'\n{Colors.YELLOW}[2/15] 系统状态{Colors.END}')
    total_tests += 1
    try:
        r = session.get(f'{BASE_URL}/api/status', timeout=5)
        if r.status_code == 200:
            data = r.json()
            if test_result(True, f'系统状态API (版本: {data["version"]}, 工单数: {data["total_work_orders"]})'):
                passed_tests += 1
    except Exception as e:
        test_result(False, f'系统状态失败: {e}')

    # 3. 统计信息
    print(f'\n{Colors.YELLOW}[3/15] 统计信息{Colors.END}')
    total_tests += 1
    try:
        r = session.get(f'{BASE_URL}/api/stats', timeout=5)
        if r.status_code == 200:
            stats = r.json()
            if test_result(True, f'统计API (总数: {stats["total"]}, 待处理: {stats["pending"]}, 处理中: {stats["processing"]})'):
                passed_tests += 1
    except Exception as e:
        test_result(False, f'统计信息失败: {e}')

    # 4. NLP分析
    print(f'\n{Colors.YELLOW}[4/15] NLP分析{Colors.END}')
    total_tests += 1
    try:
        r = session.post(f'{BASE_URL}/api/nlp/analyze', json={
            'text': '我的服务器出现严重故障需要紧急处理'
        }, timeout=5)
        if r.status_code == 200:
            nlp = r.json()
            if test_result(True, f'NLP分析 (意图: {nlp["intent"]}, 情感: {nlp["sentiment"]})'):
                passed_tests += 1
    except Exception as e:
        test_result(False, f'NLP分析失败: {e}')

    # 5. 创建工单
    print(f'\n{Colors.YELLOW}[5/15] 创建工单{Colors.END}')
    total_tests += 1
    test_wo_id = None
    try:
        r = session.post(f'{BASE_URL}/api/workorders', json={
            'title': '完整测试工单',
            'description': '这是系统完整测试创建的工单',
            'category': '技术支持',
            'priority': '高',
            'creator_name': '自动化测试',
            'creator_contact': 'test@test.com'
        }, timeout=5)
        if r.status_code == 201:
            wo = r.json()
            test_wo_id = wo['id']
            if test_result(True, f'创建工单 (ID: {test_wo_id}, 编号: {wo["order_number"]})'):
                passed_tests += 1
    except Exception as e:
        test_result(False, f'创建工单失败: {e}')

    # 6. 查询工单列表
    print(f'\n{Colors.YELLOW}[6/15] 查询工单列表{Colors.END}')
    total_tests += 1
    try:
        r = session.get(f'{BASE_URL}/api/workorders', timeout=5)
        if r.status_code == 200:
            workorders = r.json()
            if test_result(True, f'查询工单列表 (总数: {len(workorders)})'):
                passed_tests += 1
    except Exception as e:
        test_result(False, f'查询工单列表失败: {e}')

    # 7. 搜索工单
    print(f'\n{Colors.YELLOW}[7/15] 搜索工单{Colors.END}')
    total_tests += 1
    try:
        r = session.get(f'{BASE_URL}/api/workorders?search=测试', timeout=5)
        if r.status_code == 200:
            results = r.json()
            if test_result(True, f'搜索工单 (找到: {len(results)} 个)'):
                passed_tests += 1
    except Exception as e:
        test_result(False, f'搜索工单失败: {e}')

    # 8. 按状态筛选
    print(f'\n{Colors.YELLOW}[8/15] 按状态筛选{Colors.END}')
    total_tests += 1
    try:
        r = session.get(f'{BASE_URL}/api/workorders?status=待处理', timeout=5)
        if r.status_code == 200:
            results = r.json()
            if test_result(True, f'状态筛选 (待处理: {len(results)} 个)'):
                passed_tests += 1
    except Exception as e:
        test_result(False, f'状态筛选失败: {e}')

    # 9. 获取工单详情
    if test_wo_id:
        print(f'\n{Colors.YELLOW}[9/15] 获取工单详情{Colors.END}')
        total_tests += 1
        try:
            r = session.get(f'{BASE_URL}/api/workorders/{test_wo_id}', timeout=5)
            if r.status_code == 200:
                wo = r.json()
                if test_result(True, f'工单详情 (标题: {wo["title"]}, 状态: {wo["status"]})'):
                    passed_tests += 1
        except Exception as e:
            test_result(False, f'获取工单详情失败: {e}')

    # 10. 更新工单
    if test_wo_id:
        print(f'\n{Colors.YELLOW}[10/15] 更新工单{Colors.END}')
        total_tests += 1
        try:
            r = session.put(f'{BASE_URL}/api/workorders/{test_wo_id}', json={
                'status': '处理中',
                'assigned_to': '技术支持团队'
            }, timeout=5)
            if r.status_code == 200:
                wo = r.json()
                if test_result(True, f'更新工单 (新状态: {wo["status"]}, 负责人: {wo["assigned_to"]})'):
                    passed_tests += 1
        except Exception as e:
            test_result(False, f'更新工单失败: {e}')

    # 11. 添加消息
    if test_wo_id:
        print(f'\n{Colors.YELLOW}[11/15] 添加工单消息{Colors.END}')
        total_tests += 1
        try:
            r = session.post(f'{BASE_URL}/api/workorders/{test_wo_id}/messages', json={
                'sender': '测试人员',
                'content': '这是一条测试消息'
            }, timeout=5)
            if test_result(r.status_code == 200, '添加消息'):
                passed_tests += 1
        except Exception as e:
            test_result(False, f'添加消息失败: {e}')

    # 12. 查询消息列表
    if test_wo_id:
        print(f'\n{Colors.YELLOW}[12/15] 查询消息列表{Colors.END}')
        total_tests += 1
        try:
            r = session.get(f'{BASE_URL}/api/workorders/{test_wo_id}/messages', timeout=5)
            if r.status_code == 200:
                messages = r.json()
                if test_result(True, f'查询消息 (共 {len(messages)} 条)'):
                    passed_tests += 1
        except Exception as e:
            test_result(False, f'查询消息失败: {e}')

    # 13. 查询操作日志
    if test_wo_id:
        print(f'\n{Colors.YELLOW}[13/15] 查询操作日志{Colors.END}')
        total_tests += 1
        try:
            r = session.get(f'{BASE_URL}/api/workorders/{test_wo_id}/logs', timeout=5)
            if r.status_code == 200:
                logs = r.json()
                if test_result(True, f'查询日志 (共 {len(logs)} 条)'):
                    passed_tests += 1
        except Exception as e:
            test_result(False, f'查询日志失败: {e}')

    # 14. Agent自动处理
    if test_wo_id:
        print(f'\n{Colors.YELLOW}[14/15] Agent自动处理{Colors.END}')
        total_tests += 1
        try:
            r = session.post(f'{BASE_URL}/api/workorders/{test_wo_id}/process', timeout=5)
            if r.status_code == 200:
                result = r.json()
                if test_result(result['success'], f'Agent处理 (消息: {result["message"]})'):
                    passed_tests += 1
        except Exception as e:
            test_result(False, f'Agent处理失败: {e}')

    # 15. 导出CSV
    print(f'\n{Colors.YELLOW}[15/15] 导出CSV{Colors.END}')
    total_tests += 1
    try:
        r = session.get(f'{BASE_URL}/api/workorders/export/csv', timeout=5)
        if r.status_code == 200:
            if test_result(True, f'导出CSV (大小: {len(r.content)} 字节)'):
                passed_tests += 1
    except Exception as e:
        test_result(False, f'导出CSV失败: {e}')

    # 测试总结
    print('\n' + '=' * 80)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    if passed_tests == total_tests:
        print(f'{Colors.GREEN}✓✓✓ 所有测试通过！({passed_tests}/{total_tests}) - 成功率: {success_rate:.1f}%{Colors.END}')
    else:
        print(f'{Colors.YELLOW}测试完成: {passed_tests}/{total_tests} 通过 - 成功率: {success_rate:.1f}%{Colors.END}')
    print('=' * 80)

    return 0 if passed_tests == total_tests else 1

if __name__ == '__main__':
    sys.exit(main())

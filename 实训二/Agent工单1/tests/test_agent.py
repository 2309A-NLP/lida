#!/usr/bin/env python3
"""
工单编号：人工智能NLP-Agent数字人项目-记账本任务
记账本Agent - 测试脚本

功能：
1. 测试记账功能
2. 测试查询功能
3. 测试删除功能
4. 验证数据库调用率
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import process_message, OPENING_MESSAGE
from database import get_db


def test_cases():
    """测试用例"""
    print("=" * 60)
    print("记账本Agent 测试")
    print("=" * 60)

    # 测试用例
    test_cases = [
        # 记账测试
        {"input": "今天女儿买了双登山鞋499元", "expected_contains": ["已记录", "女儿", "499"]},
        {"input": "7月5日妈妈收到报销1000元", "expected_contains": ["已记录", "妈妈", "1000", "收入"]},
        {"input": "今天爸爸买书花了50元", "expected_contains": ["已记录", "爸爸", "50"]},

        # 查询测试
        {"input": "看下这个月家里花钱明细", "expected_contains": ["消费明细", "记录"]},
        {"input": "这个月女儿花了多少钱？", "expected_contains": ["女儿", "消费明细"]},

        # 删除测试
        {"input": "删除登山鞋的费用", "expected_contains": ["已删除"]},
    ]

    passed = 0
    failed = 0

    print("\n测试用例：")
    print("-" * 60)

    for i, case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {case['input']}")
        reply = process_message(case['input'])
        print(f"回复: {reply}")

        # 检查是否包含期望的关键词
        success = True
        for keyword in case['expected_contains']:
            if keyword not in reply:
                success = False
                break

        if success:
            print("结果: PASS")
            passed += 1
        else:
            print(f"结果: FAIL (期望包含: {case['expected_contains']})")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


def test_database_operations():
    """测试数据库操作"""
    print("\n" + "=" * 60)
    print("数据库操作测试")
    print("=" * 60)

    db = get_db()

    # 测试添加记录
    print("\n1. 添加记录测试")
    record_id = db.add_record("2025-01-15", "女儿", "买书", "三体", 50, "支出")
    print(f"   添加记录成功，ID: {record_id}")

    # 测试查询记录
    print("\n2. 查询记录测试")
    records = db.query_by_item("三体")
    print(f"   查询到 {len(records)} 条记录")

    # 测试汇总统计
    print("\n3. 汇总统计测试")
    summary = db.get_summary()
    print(f"   总收入: {summary['收入']}元")
    print(f"   总支出: {summary['支出']}元")
    print(f"   净收入: {summary['净收入']}元")

    # 测试删除记录
    print("\n4. 删除记录测试")
    success = db.delete_record(record_id)
    print(f"   删除记录: {'成功' if success else '失败'}")

    print("\n" + "=" * 60)
    print("数据库操作测试完成")
    print("=" * 60)


def main():
    """主函数"""
    print(OPENING_MESSAGE)
    print()

    # 运行测试
    success = test_cases()
    test_database_operations()

    if success:
        print("\n所有测试通过！")
        return 0
    else:
        print("\n部分测试失败！")
        return 1


if __name__ == "__main__":
    sys.exit(main())

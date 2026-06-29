#!/usr/bin/env python3
"""
工单编号：人工智能NLP-Agent数字人项目-记账本任务
记账本Agent - API接口

功能：
1. 提供RESTful API
2. 支持对话式记账
3. 支持查询和删除
"""

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from agent import process_message, OPENING_MESSAGE
from database import get_db

# 创建Flask应用
app = Flask(__name__, static_folder='templates')

# 模板目录
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates')


@app.route('/')
def index():
    """首页"""
    return send_from_directory(TEMPLATE_DIR, 'index.html')


@app.route('/api/opening', methods=['GET'])
def get_opening():
    """获取开场白"""
    return jsonify({"message": OPENING_MESSAGE})


@app.route('/api/chat', methods=['POST'])
def chat():
    """对话API"""
    data = request.get_json()
    message = data.get('message', '')

    if not message:
        return jsonify({"reply": "请输入消息"})

    reply = process_message(message)
    return jsonify({"reply": reply})


@app.route('/api/records', methods=['GET'])
def get_records():
    """获取记录列表"""
    db = get_db()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    member = request.args.get('member')
    limit = request.args.get('limit', 20, type=int)

    if start_date and end_date:
        records = db.query_by_date_range(start_date, end_date, member)
    else:
        records = db.query_by_date_range("2000-01-01", "2099-12-31", member)

    # 限制返回数量
    records = records[:limit]

    return jsonify({"records": records})


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """获取汇总统计"""
    db = get_db()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    member = request.args.get('member')

    summary = db.get_summary(start_date, end_date, member)
    return jsonify({"summary": summary})


@app.route('/api/member_summary', methods=['GET'])
def get_member_summary():
    """获取各成员汇总"""
    db = get_db()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    summary = db.get_member_summary(start_date, end_date)
    return jsonify({"summary": summary})


@app.route('/api/category_summary', methods=['GET'])
def get_category_summary():
    """获取各类别汇总"""
    db = get_db()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    summary = db.get_category_summary(start_date, end_date)
    return jsonify({"summary": summary})


@app.route('/api/add_record', methods=['POST'])
def add_record():
    """添加记录API"""
    data = request.get_json()
    db = get_db()

    try:
        record_id = db.add_record(
            date_str=data['date'],
            member=data['member'],
            category=data['category'],
            item=data['item'],
            amount=float(data['amount']),
            type_=data['type'],
            note=data.get('note', '')
        )
        return jsonify({"success": True, "id": record_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/delete_record', methods=['POST'])
def delete_record():
    """删除记录API"""
    data = request.get_json()
    db = get_db()

    try:
        success = db.delete_record(data['id'])
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/clear_all', methods=['POST'])
def clear_all():
    """清空所有记录"""
    db = get_db()
    try:
        count = db.clear_all_records()
        return jsonify({"success": True, "count": count, "message": f"已清空 {count} 条记录"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({"status": "healthy", "service": "记账本Agent"})


if __name__ == '__main__':
    print("启动记账本Agent服务...")
    print("访问地址: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)

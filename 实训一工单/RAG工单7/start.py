#!/usr/bin/env python3
"""Start RAG工单7 server"""
import os, sys
BASE = '/mnt/d/RAG工单/RAG工单7'
os.chdir(BASE)
sys.path.insert(0, BASE)
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-171f528187724a14a74acc98e756c1c1')
os.environ['HF_HUB_OFFLINE'] = '1'  # 离线模式，防卡网络

# 修复：启动前删除Milvus锁文件（防崩溃后残留LOCK）
for root, dirs, files in os.walk(BASE):
    for f in files:
        if f == 'LOCK':
            fp = os.path.join(root, f)
            try:
                os.remove(fp)
                print(f"  [清理锁文件] {fp}")
            except: pass

import uvicorn
PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8507

# Import app AFTER chdir and path setup
from app_v7 import app
print(f"Starting on port {PORT}...")
uvicorn.run(app, host='0.0.0.0', port=PORT, log_level='info')

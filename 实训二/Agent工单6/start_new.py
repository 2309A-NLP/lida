"""
直接启动新服务器在8080端口
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from backend.api import app
from backend.schedule_agent import init_schedule_db, ReminderWorker

# 初始化
init_schedule_db()
ReminderWorker().start()

print("=" * 60)
print("新服务器启动在端口 8080")
print("请访问: http://localhost:8080")
print("=" * 60)

uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")

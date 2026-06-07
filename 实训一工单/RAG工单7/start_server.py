import os, sys, time
sys.path.insert(0, '/mnt/d/RAG工单/RAG工单7')
os.chdir('/mnt/d/RAG工单/RAG工单7')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-171c1cdaa57347628ee2f4ef8de4875c')

import uvicorn
from app_v7 import app

print("=== Starting Uvicorn on 8507 ===")
sys.stdout.flush()
uvicorn.run(app, host='0.0.0.0', port=8507, log_level='info')

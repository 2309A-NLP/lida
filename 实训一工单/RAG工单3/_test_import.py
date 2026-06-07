import sys, os, time
sys.path.insert(0, '/mnt/d/RAG工单/RAG工单3')
t0 = time.time()
print("Starting import...")
from app import app
print(f"Import done in {time.time()-t0:.2f}s")
print("FastAPI app created successfully")

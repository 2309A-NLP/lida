import os, sys, time
sys.path.insert(0, '/mnt/d/RAG工单/RAG工单7')
os.chdir('/mnt/d/RAG工单/RAG工单7')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-171c1cdaa57347628ee2f4ef8de4875c')

print("Step 1: Importing app...")
sys.stdout.flush()
from app_v7 import app

print("Step 2: App imported, checking startup...")
sys.stdout.flush()

# Run the startup manually
print("Step 3: Running startup...")
sys.stdout.flush()
import app_v7 as a
a.engine.load()
print(f"  Engine loaded: {a.engine.vector_count} vectors")
sys.stdout.flush()

print("Step 4: Init sessions...")
sys.stdout.flush()
a.init_sessions_collection()
print("  Sessions init done")
sys.stdout.flush()

print("=== All startup checks passed ===")
sys.stdout.flush()

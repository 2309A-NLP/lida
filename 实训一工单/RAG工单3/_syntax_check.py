import sys
sys.path.insert(0, '/mnt/d/RAG工单/RAG工单3')
import importlib.util
spec = importlib.util.spec_from_file_location("app", "/mnt/d/RAG工单/RAG工单3/app.py")
mod = importlib.util.module_from_spec(spec)
# We won't fully import since it triggers chromadb init, just check syntax
import py_compile
py_compile.compile("/mnt/d/RAG工单/RAG工单3/app.py", doraise=True)
print("SYNTAX OK")

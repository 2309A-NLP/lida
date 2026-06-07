import subprocess, sys
result = subprocess.run(
    [sys.executable, '/mnt/d/RAG工单/RAG工单3/app.py'],
    capture_output=True, text=True, timeout=5,
    cwd='/mnt/d/RAG工单/RAG工单3'
)
print("STDOUT:", repr(result.stdout[:500]))
print("STDERR:", repr(result.stderr[:500]))
print("Return code:", result.returncode)

import subprocess, time, sys

# Start the app
proc = subprocess.Popen(
    [sys.executable, '-u', '/mnt/d/RAG工单/RAG工单3/app.py'],
    cwd='/mnt/d/RAG工单/RAG工单3',
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Wait for it to start
time.sleep(6)

# Check if it's listening
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = s.connect_ex(('127.0.0.1', 8503))
s.close()

print("Port 8503 listening:", result == 0)

# Get output so far
try:
    proc.stdout.flush()
except:
    pass
try:
    proc.stderr.flush()
except:
    pass

# Read without blocking
import os
import select

stdout_data = ""
stderr_data = ""

for fd, dest in [(proc.stdout, 'stdout'), (proc.stderr, 'stderr')]:
    if fd:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                data = fd.read1(4096)
                if dest == 'stdout':
                    stdout_data += data.decode('utf-8', errors='replace')
                else:
                    stderr_data += data.decode('utf-8', errors='replace')
            except:
                pass

print("STDOUT:", repr(stdout_data[:500]))
print("STDERR:", repr(stderr_data[:500]))

proc.terminate()
proc.wait(timeout=5)
print("Done, exit code:", proc.returncode)

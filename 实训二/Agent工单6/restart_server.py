"""重启服务器脚本"""
import psutil
import subprocess
import sys
import time

# 结束占用8000端口的Python进程
for proc in psutil.process_iter(['pid', 'name', 'connections']):
    try:
        if proc.info['name'] and 'python' in proc.info['name'].lower():
            for conn in proc.connections():
                if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == 8000:
                    proc.kill()
                    print(f'Killed PID {proc.pid}')
                    break
    except Exception:
        pass

time.sleep(2)
print('Starting server...')
subprocess.Popen([sys.executable, 'main.py'])
print('Server started.')

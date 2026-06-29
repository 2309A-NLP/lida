"""
智能体任务工单系统 - 主入口
"""
import uvicorn
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """主函数"""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    print("\n" + "=" * 60)
    print("智能体任务工单系统 V1.1")
    print("AI NLP-Agent数字人项目 - 智能任务工单管理系统")
    print("=" * 60)
    print(f"服务地址: http://localhost:{port}")
    print(f"API文档: http://localhost:{port}/docs")
    print("=" * 60 + "\n")

    # 直接导入app，不用字符串引用，关闭热重载确保加载最新代码
    from backend.api import app
    from backend.schedule_agent import init_schedule_db, ReminderWorker
    init_schedule_db()
    ReminderWorker().start()

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()

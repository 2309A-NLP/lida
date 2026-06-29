#!/bin/bash
# 快速启动脚本

echo "智能体任务工单系统 V1.1 启动脚本"
echo "=================================="

# 检查Python版本
python --version

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 启动服务
echo "启动服务..."
python main.py

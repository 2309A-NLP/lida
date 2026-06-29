#!/bin/bash
# 工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务

echo "========================================"
echo "招股书问答智能体 - 一键启动脚本"
echo "========================================"
echo ""

echo "[1/4] 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python，请先安装Python 3.8+"
    exit 1
fi

echo "[2/4] 检查依赖包..."
if ! python3 -c "import fastapi" &> /dev/null; then
    echo "[提示] 首次运行，正在安装依赖包..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[错误] 依赖包安装失败"
        exit 1
    fi
fi

echo "[3/4] 检查知识库..."
if [ ! -f "dataset_raw/question.json" ]; then
    echo "[提示] 正在下载知识库数据..."
    python3 scripts/download_knowledge_base.py
    if [ $? -ne 0 ]; then
        echo "[错误] 知识库下载失败"
        exit 1
    fi
fi

if [ ! -f "outputs/index/chunks.jsonl" ]; then
    echo "[提示] 正在构建索引..."
    python3 scripts/build_index.py
    if [ $? -ne 0 ]; then
        echo "[错误] 索引构建失败"
        exit 1
    fi
fi

echo "[4/4] 启动Web服务..."
echo ""
echo "========================================"
echo "服务启动中..."
echo "访问地址：http://127.0.0.1:8001"
echo "按 Ctrl+C 停止服务"
echo "========================================"
echo ""

python3 scripts/run_web.py

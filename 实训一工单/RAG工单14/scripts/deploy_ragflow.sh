#!/bin/bash
# RAGFlow 部署脚本
# 用法: bash deploy_ragflow.sh

set -e

echo "=== RAGFlow 部署脚本 ==="
echo ""

# 配置
RAGFLOW_DIR="/mnt/d/ragflow"
RAGFLOW_REPO="https://github.com/infiniflow/ragflow.git"
RAGFLOW_BRANCH="main"

# 检查是否已部署
if [ -d "$RAGFLOW_DIR" ]; then
    echo "[INFO] RAGFlow 目录已存在: $RAGFLOW_DIR"
    read -p "是否重新部署？(y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "跳过部署"
        exit 0
    fi
fi

# 克隆仓库
echo "[1/5] 克隆 RAGFlow 仓库..."
if [ ! -d "$RAGFLOW_DIR" ]; then
    git clone -b $RAGFLOW_BRANCH $RAGFLOW_REPO $RAGFLOW_DIR
else
    cd $RAGFLOW_DIR
    git pull
fi

cd $RAGFLOW_DIR

# 检查 Docker
echo "[2/5] 检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "[ERROR] Docker Compose 未安装"
    exit 1
fi

# 配置环境变量
echo "[3/5] 配置环境变量..."
if [ ! -f ".env" ]; then
    cp .env.example .env 2>/dev/null || true
fi

# 启动服务
echo "[4/5] 启动 RAGFlow 服务..."
if [ -f "docker-compose.yml" ]; then
    docker compose up -d
elif [ -f "docker-compose-CN.yml" ]; then
    docker compose -f docker-compose-CN.yml up -d
else
    echo "[ERROR] 未找到 docker-compose 文件"
    exit 1
fi

# 等待服务启动
echo "[5/5] 等待服务启动..."
sleep 30

# 检查服务状态
echo ""
echo "=== 部署完成 ==="
echo "RAGFlow 地址: http://localhost:9380"
echo ""
echo "检查服务状态:"
docker compose ps 2>/dev/null || docker ps

echo ""
echo "=== 下一步 ==="
echo "1. 访问 http://localhost:9380 创建账号"
echo "2. 运行 python scripts/build_knowledge_base.py 构建知识库"
echo "3. 运行 python scripts/test_questions.py 测试问题"

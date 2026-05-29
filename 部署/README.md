# RAG 多角色智能聊天机器人 - 部署概览

## 项目简介

基于 RAG（检索增强生成）技术的多角色智能聊天机器人系统。用户可以与不同预设角色的 AI 进行对话，系统通过检索增强生成技术提供更准确、更贴合角色设定的回复。

## 部署方式

本项目支持三种部署方式：

| 方式 | 适用场景 | 难度 |
|------|---------|------|
| 本地部署 | 开发调试、个人使用 | 低 |
| Docker 部署 | 测试环境、单机生产 | 中 |
| Docker Compose 部署 | 生产环境、多实例负载均衡 | 中高 |

## 文件清单

### 核心程序文件

| 文件 | 说明 |
|------|------|
| main.py | 主入口文件，基于 FastAPI 启动 HTTP 服务 |
| requirements.txt | Python 依赖清单 |
| .env | 环境变量配置文件（数据库连接、API Key 等） |
| .gitignore | Git 忽略规则 |

### 项目模块

| 目录 | 说明 |
|------|------|
| api/ | API 接口层，定义所有 HTTP 端点 |
| service/ | 业务逻辑层，处理聊天、角色、知识库等逻辑 |
| data/ | 数据访问层，操作 MySQL、Redis、Milvus 等数据库 |
| model/ | 模型调用层，封装 LLM 和 Embedding 模型接口 |
| config/ | 配置管理模块 |
| utils/ | 工具模块（日志、错误处理、编码等） |
| static/ | 静态资源文件 |
| template/ | HTML 模板文件 |
| tests/ | 测试脚本 |
| text_data/ | 文本语料数据 |
| logs/ | 日志输出目录 |

### 部署配置文件

| 文件 | 说明 |
|------|------|
| Dockerfile | 容器镜像构建文件 |
| docker-compose.yml | Docker Compose 编排文件（含 Nginx、Redis、Milvus 等） |
| nginx.conf | Nginx 反向代理与负载均衡配置 |
| .env | 环境变量配置 |

## 端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 8080 | 主应用 | FastAPI 主服务端口 |
| 8081-8083 | 后端实例 | Docker Compose 多实例端口 |
| 6379 | Redis | 短期记忆缓存 |
| 3306 | MySQL | 持久化数据库 |
| 19530 | Milvus | 向量数据库 |
| 9091 | Milvus | Milvus 监控端口 |

## 快速启动

```bash
# 本地部署
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
# 编辑 .env 配置数据库连接信息
python main.py --host 0.0.0.0 --port 8080

# Docker Compose 部署
docker-compose up -d
```

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **AI 模型**: 支持在线 API（如 DeepSeek）和本地模型
- **向量数据库**: Milvus（长期记忆存储）
- **关系数据库**: MySQL（用户数据、角色信息）
- **缓存**: Redis（短期记忆、会话管理）
- **嵌入模型**: BGE-M3 / BGE-Reranker
- **反向代理**: Nginx（负载均衡、SSL 终止）

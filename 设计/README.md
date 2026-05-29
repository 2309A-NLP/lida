# RAG 多角色智能聊天机器人 - 设计方案

## 项目概述

基于 RAG（检索增强生成）技术的多角色智能聊天机器人系统，提供专业的心理健康咨询服务。系统集成了两个 AI 角色——心理医生（林语薇）和精神科医生（陈志远），每个角色拥有独立的专业知识库和回复风格。

## 技术栈

- **后端框架**: FastAPI (Python)
- **缓存存储**: Redis (端口 6379)
- **持久化存储**: MySQL (端口 3306)
- **AI 模型**: DeepSeek API (云端大语言模型)
- **检索技术**: jieba 分词 + BM25 关键词检索 + BGE-M3 向量检索 (可选用)
- **向量数据库**: Milvus (可选)
- **前端**: 纯 HTML / CSS / JavaScript

## 系统架构

```
配置层  config/settings.py
   |
接口层  api/routes.py
   |
业务逻辑层  service/chat_service.py, service/knowledge_service.py, service/auth_service.py, service/role_service.py
   |
数据层  data/redis_client.py, data/mysql_client.py, data/milvus_client.py
   |
模型层  model/llm_model.py (DeepSeek API)
```

## 核心功能

1. 用户注册与登录 (MySQL / 内存存储)
2. 双角色 AI 对话 (心理医生 + 精神科医生)
3. RAG 知识库检索增强生成
4. 聊天历史管理
5. 知识库动态管理 (添加 / 清空 / 重新加载)

## 项目文件清单

### 核心代码

| 文件 | 说明 |
|------|------|
| main.py | 应用主入口，启动 FastAPI 服务器 |
| config/settings.py | 全局配置管理 (数据库 / 模型 / 应用参数) |
| api/routes.py | API 接口层，定义所有 RESTful 端点 |
| service/chat_service.py | 聊天业务逻辑 (消息处理 / 历史管理) |
| service/role_service.py | 角色管理 (角色信息 / 提示词) |
| service/auth_service.py | 用户认证 (注册 / 登录 / bcrypt 加密) |
| service/knowledge_service.py | 知识库服务 (RAG 检索 / BM25 关键词匹配) |
| model/llm_model.py | DeepSeek API 调用 (消息构建 / 备用回复) |
| data/redis_client.py | Redis 缓存客户端 (聊天历史存储) |
| data/mysql_client.py | MySQL 数据库客户端 (用户表 / 聊天历史表) |
| data/milvus_client.py | Milvus 向量数据库客户端 (可选) |
| utils/error_handler.py | 全局异常处理 |
| utils/encoder.py | 编码工具 |
| utils/logger.py | 日志工具 |

### 前端模板

| 文件 | 说明 |
|------|------|
| template/index.html | 首页 / 登录注册页面 |
| template/chat.html | 聊天对话页面 |
| template/characters.html | 角色选择页面 |
| template/architecture.html | 系统架构展示页面 |

### 知识库

| 文件 | 说明 |
|------|------|
| text_data/心理医生.txt | 心理医生角色知识库 (33 条) |
| text_data/精神科医生.txt | 精神科医生角色知识库 (492 条) |

### 测试

| 文件 | 说明 |
|------|------|
| tests/api_test.py | API 接口测试 |
| tests/qps_test.py | QPS 性能测试 |
| tests/qps_light_test.py | 轻量 QPS 压测 |
| tests/qps_stress_test.py | 高并发压力测试 |
| tests/rag_manual_eval.py | RAG 人工评估 |
| tests/ragas_eval.py | RAGAS 自动评估 |

## 端口说明

- 应用服务: 8080
- Redis: 6379 (localhost)
- MySQL: 3306 (localhost)

## 环境要求

- Python 3.9+
- Redis 服务 (可选，无 Redis 时自动降级为内存存储)
- MySQL 服务 (可选，无 MySQL 时自动降级为内存存储)
- DeepSeek API Key (通过环境变量 MODEL_API_KEY 配置)

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量 (复制并编辑 .env)
cp .env.example .env
# 编辑 .env 文件，填入 DeepSeek API Key

# 启动服务
python main.py --host 0.0.0.0 --port 8080

# 访问
# http://localhost:8080
```

# RAG 多角色智能聊天机器人 - 研发概览

## 项目简介

基于 RAG（检索增强生成）技术的多角色智能聊天机器人系统，支持多个 AI 角色扮演（心理医生、精神科医生），通过向量检索 + BM25 混合检索技术结合大语言模型，为每个角色提供专业、准确的知识支撑。

## 技术栈

- 后端框架：FastAPI + Uvicorn
- 大模型 API：DeepSeek Chat API
- 向量嵌入：BGE-M3（本地部署）
- 向量数据库：Milvus（可选）
- 关键词检索：BM25（rank-bm25）
- 重排序：BGE-Reranker（本地部署）
- 缓存/会话：Redis（含内存降级）
- 持久化存储：MySQL（含内存降级）
- 中文分词：jieba
- 密码加密：bcrypt
- 容器化：Docker / Docker Compose
- 负载均衡：Nginx

## 项目文件清单

```
RAG_多角色智能聊天机器人项目/
├── main.py                    # 主入口：FastAPI 应用启动
├── requirements.txt           # Python 依赖清单
├── Dockerfile                 # Docker 构建文件
├── docker-compose.yml         # Docker Compose 多服务部署
├── nginx.conf                 # Nginx 负载均衡配置
├── test_startup.py            # 启动调试脚本
├── .env                       # 环境变量配置（密钥/数据库连接等）
├── .gitignore
│
├── config/
│   ├── __init__.py
│   └── settings.py            # 配置层：读取 .env 管理所有配置
│
├── api/
│   ├── __init__.py
│   └── routes.py              # 接口层：定义所有 API 端点
│
├── service/
│   ├── __init__.py
│   ├── chat_service.py        # 聊天服务：核心业务逻辑
│   ├── knowledge_service.py   # 知识库服务：RAG 检索与知识管理
│   ├── auth_service.py        # 认证服务：用户注册/登录
│   └── role_service.py        # 角色服务：角色信息与提示词管理
│
├── model/
│   ├── __init__.py
│   └── llm_model.py           # 模型层：调用 DeepSeek API 生成回复
│
├── data/
│   ├── __init__.py
│   ├── redis_client.py        # 数据层：Redis 缓存客户端
│   ├── mysql_client.py        # 数据层：MySQL 数据库客户端
│   └── milvus_client.py       # 数据层：Milvus 向量数据库客户端
│
├── utils/
│   ├── __init__.py
│   ├── logger.py              # 日志工具：控制台+文件日志
│   ├── error_handler.py       # 错误处理：统一异常处理
│   └── encoder.py             # 编码工具：JSON/Base64/响应格式化
│
├── template/
│   ├── index.html             # 首页
│   ├── chat.html              # 聊天页面
│   ├── characters.html        # 角色选择页面
│   └── architecture.html      # 架构展示页面
│
├── static/
│   ├── architecture.png       # 架构图
│   └── mindmap.png            # 思维导图
│
├── text_data/
│   ├── 心理医生.txt            # 心理医生角色知识库（~1000行）
│   └── 精神科医生.txt          # 精神科医生角色知识库
│
├── data/                      # PDF 原始资料
│   ├── 心里医生PDF/
│   └── 精神科PDF/
│
├── docs/                      # 已有技术文档
│   ├── API接口文档.md
│   ├── 技术设计文档.md
│   ├── 测试成果报告.md
│   ├── 需求规格说明书.md
│   └── postman_collection.json
│
├── tests/                     # 测试脚本
│   ├── api_test.py
│   ├── qps_test.py / qps_light_test.py / qps_stress_test.py
│   ├── jmeter_test.jmx
│   ├── rag_manual_eval.py
│   └── ragas_eval.py
│
├── logs/                      # 运行时日志
│   └── app.log
│
└── venv/                      # Python 虚拟环境（Windows）
```

## 分层架构

```
┌──────────────────────────────────────────────────────────────┐
│  前端页面 (template/)                                        │
│  index.html | characters.html | chat.html | architecture.html│
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP
┌──────────────────────────────▼───────────────────────────────┐
│  API 网关 - Nginx (nginx.conf)                               │
│  负载均衡 / 反向代理 / SSL / 限流 / 静态资源缓存              │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│  接口层 - api/routes.py                                      │
│  API 端点定义 / 请求验证 / 响应序列化                         │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│  业务逻辑层 - service/                                        │
│  chat_service  |  knowledge_service  |  auth_service  |  role│
└──────┬───────────────────────────────────────────┬───────────┘
       │                                           │
┌──────▼──────────┐                  ┌─────────────▼───────────┐
│  模型层          │                  │  数据层                 │
│  model/llm_model │                  │  redis / mysql / milvus│
│  (DeepSeek API)  │                  │                         │
└─────────────────┘                  └─────────────────────────┘
```

## 核心业务流程

1. 用户打开前端页面 -> 选择角色（心理医生/精神科医生）
2. 用户发送消息 -> API 路由接收请求
3. ChatService 获取聊天历史（Redis）+ 检索相关知识（KnowledgeService）
4. KnowledgeService 使用混合检索（BGE-M3 向量 + BM25 + BGE-Rerank）
5. LLMModel 将系统提示词 + 历史 + 知识 + 用户消息发送给 DeepSeek API
6. API 返回 AI 回复 -> 存入 Redis -> 返回给前端

## 系统特性

- 优雅降级：所有外部依赖（Redis/MySQL/Milvus）连接失败时自动切换到内存模式
- 混合检索：向量检索 + BM25 关键词检索 + BGE-Rerank 重排序
- 多角色支持：可扩展增加新角色及其知识库
- 容器化部署：Docker Compose 一键部署全套服务
- 负载均衡：Nginx 支持多后端实例水平扩展

# 测试文档概览

## 项目简介

基于RAG技术的多角色智能聊天机器人（版本 2.0.0），支持心理医生（林语薇）和精神科医生（陈志远）两个AI角色，提供专业医疗咨询服务。

## 测试文档清单

| 文件名 | 说明 |
|---|---|
| README.md | 本文档 - 测试概览与文件清单 |
| 接口测试手册.md | 每个API端点的详细测试用例（正常场景 + 异常场景） |
| 压力测试指南.md | QPS测试脚本使用说明和性能指标解读 |
| 质量评估.md | RAG检索增强生成系统质量评估方法 |
| 测试场景清单.md | 端到端测试流程与验收标准 |

## API端点总览

| 方法 | 端点 | 说明 |
|---|---|---|
| GET | / | 登录页面 |
| GET | /characters.html | 角色选择页面 |
| GET | /chat.html | 聊天页面 |
| GET | /architecture.html | 架构说明页面 |
| GET | /roles | 获取所有角色列表 |
| POST | /register | 用户注册 |
| POST | /login | 用户登录 |
| POST | /chat | 发送聊天消息（核心RAG功能） |
| GET | /chat/history/{user_id}/{role_id} | 获取聊天历史 |
| DELETE | /chat/history/{user_id}/{role_id} | 清空聊天历史 |
| DELETE | /chat/history/{user_id}/{role_id}/message/{index} | 删除单条消息 |
| GET | /chat/history/list | 获取会话列表 |
| POST | /start_new_chat/{user_id}/{role_id} | 开始新对话 |
| POST | /knowledge/add | 添加知识库文档 |
| DELETE | /knowledge/clear/{role_id} | 清空角色知识库 |
| POST | /knowledge/reload | 重新加载知识库 |
| GET | /knowledge/search | 搜索知识库 |

## 现有测试脚本

项目 tests/ 目录下已包含以下测试脚本：

| 脚本 | 说明 |
|---|---|
| api_test.py | API接口全覆盖测试（16个端点，含边界条件） |
| qps_test.py | Locust压力测试脚本（Web界面，支持并发用户模拟） |
| qps_light_test.py | 轻量级QPS基准测试（Python版，3并发） |
| qps_stress_test.py | 完整QPS压力测试（递增并发，延迟分布统计） |
| rag_manual_eval.py | RAG系统手动评估（文本相似度 + 关键词召回） |
| ragas_eval.py | RAGAS自动化评估（Faithfulness + Context Precision） |
| rag_manual_eval.py | RAG系统手动评估（文本相似度 + 关键词召回） |

## 测试环境要求

- Python 3.10+
- FastAPI + Uvicorn
- Redis（聊天历史存储）
- MySQL（用户数据存储，可选，降级到内存存储）
- Milvus（向量数据库，可选，降级到关键词匹配）
- BGE-M3 / BGE-Rerank 嵌入模型（本地部署）
- 依赖安装：pip install -r requirements.txt

## 快速开始测试

```bash
# 1. 启动服务
python main.py --host 0.0.0.0 --port 8080

# 2. 运行API接口测试
cd tests && python api_test.py

# 3. 运行轻量压力测试
cd tests && python qps_light_test.py

# 4. 运行RAG质量评估
cd tests && python rag_manual_eval.py
```

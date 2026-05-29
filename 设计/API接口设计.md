# API 接口设计文档

## 1. 接口总览

| 方法 | 路径 | 说明 | 标签 |
|------|------|------|------|
| GET | / | 首页 | 页面 |
| GET | /characters.html | 角色选择页面 | 页面 |
| GET | /chat.html | 聊天页面 | 页面 |
| GET | /architecture.html | 架构展示页面 | 页面 |
| GET | /roles | 获取角色列表 | 角色管理 |
| POST | /register | 用户注册 | 用户认证 |
| POST | /login | 用户登录 | 用户认证 |
| POST | /chat | 发送聊天消息 | 聊天功能 |
| GET | /chat/history/{user_id}/{role_id} | 获取聊天历史 | 聊天历史 |
| DELETE | /chat/history/{user_id}/{role_id} | 清空聊天历史 | 聊天历史 |
| DELETE | /chat/history/{user_id}/{role_id}/message/{index} | 删除单条消息 | 聊天历史 |
| GET | /chat/history/list | 获取会话列表 | 聊天历史 |
| POST | /start_new_chat/{user_id}/{role_id} | 开始新对话 | 聊天历史 |
| POST | /knowledge/add | 添加知识库文档 | 知识库管理 |
| DELETE | /knowledge/clear/{role_id} | 清空知识库 | 知识库管理 |
| POST | /knowledge/reload | 重新加载知识库 | 知识库管理 |
| GET | /knowledge/search | 搜索知识库 | 知识库管理 |

---

## 2. 页面路由

### 2.1 GET /

返回首页（登录注册页面）。

**响应:** `template/index.html` (HTML 文件)

### 2.2 GET /characters.html

返回角色选择页面。

**响应:** `template/characters.html` (HTML 文件)

### 2.3 GET /chat.html

返回聊天对话页面。

**响应:** `template/chat.html` (HTML 文件)

### 2.4 GET /architecture.html

返回系统架构展示页面。

**响应:** `template/architecture.html` (HTML 文件)

---

## 3. 角色管理

### 3.1 GET /roles

获取所有可用的 AI 角色列表。

**请求参数:** 无

**响应示例:**
```json
{
    "roles": [
        {
            "id": "char_lin",
            "name": "林语薇",
            "title": "心理医生",
            "description": "温暖共情的倾听者，擅长通过认知行为疗法帮助你理清思绪，用无条件积极关注陪伴你走过低谷。",
            "welcome": "你好，我是林语薇，一位心理医生。很高兴在这里与你相遇。无论你正在经历什么，我都会认真倾听。想和我聊聊吗？",
            "tags": ["心理", "焦虑", "情绪", "心理咨询"]
        },
        {
            "id": "char_chen",
            "name": "陈志远",
            "title": "精神科医生",
            "description": "从医二十年的精神科专家，以循证医学为基础，擅长精神疾病的诊断评估与治疗方案制定。",
            "welcome": "你好，我是陈志远，一位精神科医生。很高兴能为你提供专业的医疗咨询服务。请问有什么可以帮助你的吗？",
            "tags": ["精神", "疾病", "诊断", "治疗"]
        }
    ]
}
```

---

## 4. 用户认证

### 4.1 POST /register

用户注册。

**请求体:**
```json
{
    "username": "alice",
    "password": "password123",
    "email": "alice@example.com"
}
```

**参数校验规则:**
- `username`: 3-50 字符，只允许字母和数字
- `password`: 6-100 字符
- `email`: 可选，必须包含 @ 符号

**成功响应 (201):**
```json
{
    "success": true,
    "message": "注册成功"
}
```

**失败响应 (400):**
```json
{
    "detail": "用户名已存在"
}
```

### 4.2 POST /login

用户登录。

**请求体:**
```json
{
    "username": "alice",
    "password": "password123"
}
```

**成功响应 (200):**
```json
{
    "success": true,
    "message": "登录成功",
    "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "username": "alice"
    }
}
```

**失败响应 (401):**
```json
{
    "detail": "用户名不存在"
}
```

---

## 5. 聊天功能

### 5.1 POST /chat

发送聊天消息并获取 AI 回复。

**请求体:**
```json
{
    "user_id": "user_1",
    "role_id": "char_lin",
    "message": "我最近总是失眠，很焦虑"
}
```

**参数校验规则:**
- `user_id`: 1-100 字符
- `role_id`: 必须为 "char_lin" 或 "char_chen"
- `message`: 1-2000 字符

**成功响应 (200):**
```json
{
    "response": "我能感受到你现在的心情，失眠和焦虑确实让人很困扰。能告诉我这种情况持续多久了吗？最近有没有遇到什么让你感到压力的事情？",
    "chat_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**失败响应 (500):**
```json
{
    "detail": "Internal server error message"
}
```

**处理流程:**
1. 从 Redis 读取聊天历史
2. 从知识库检索相关知识
3. 调用 DeepSeek API 生成回复
4. 存储用户消息和 AI 回复到 Redis

---

## 6. 聊天历史

### 6.1 GET /chat/history/{user_id}/{role_id}

获取指定用户与角色的聊天历史。

**路径参数:**
- `user_id`: 用户 ID
- `role_id`: 角色 ID (char_lin / char_chen)

**查询参数:**
- `limit`: 返回消息数量上限 (默认 100)

**成功响应:**
```json
{
    "history": [
        {
            "role": "user",
            "content": "我最近总是失眠，很焦虑",
            "time": "2026-05-29T18:30:00.123456"
        },
        {
            "role": "assistant",
            "content": "我能感受到你现在的心情...",
            "time": "2026-05-29T18:30:05.654321"
        }
    ]
}
```

消息按时间从旧到新排序。

### 6.2 DELETE /chat/history/{user_id}/{role_id}

清空指定用户与角色的所有聊天历史。

**路径参数:**
- `user_id`: 用户 ID
- `role_id`: 角色 ID

**成功响应:**
```json
{
    "message": "聊天历史已清空"
}
```

### 6.3 DELETE /chat/history/{user_id}/{role_id}/message/{index}

删除指定索引的单条消息。

**路径参数:**
- `user_id`: 用户 ID
- `role_id`: 角色 ID
- `index`: 消息索引 (从旧到新排序，0 为最早的消息)

**成功响应:**
```json
{
    "message": "消息已删除",
    "deleted": {
        "role": "user",
        "content": "删除的消息内容",
        "time": "2026-05-29T18:30:00.123456"
    }
}
```

**失败响应:**
- 404: `{"detail": "聊天记录不存在"}`
- 400: `{"detail": "消息索引无效"}`

### 6.4 GET /chat/history/list

获取指定用户的所有会话列表。

**查询参数:**
- `user_id`: 用户 ID (默认 "user_1")

**成功响应:**
```json
{
    "history": [
        {
            "role_id": "char_lin",
            "name": "林语薇",
            "last_message": "我最近总是失眠，很焦虑...",
            "last_time": "2026-05-29T18:30:00",
            "message_count": 12
        },
        {
            "role_id": "char_chen",
            "name": "陈志远",
            "last_message": "我的头痛持续两周了...",
            "last_time": "2026-05-28T14:20:00",
            "message_count": 8
        }
    ]
}
```

会话按最后消息时间降序排列。

### 6.5 POST /start_new_chat/{user_id}/{role_id}

开始新的对话（清空历史后发送欢迎语）。

**路径参数:**
- `user_id`: 用户 ID
- `role_id`: 角色 ID

**成功响应:**
```json
{
    "message": "新对话已开始",
    "welcome": "你好，我是林语薇，一位心理医生。很高兴在这里与你相遇。无论你正在经历什么，我都会认真倾听。想和我聊聊吗？"
}
```

---

## 7. 知识库管理

### 7.1 POST /knowledge/add

向指定角色的知识库添加新文档。

**请求体:**
```json
{
    "role_id": "char_lin",
    "content": "认知行为疗法（CBT）是一种...",
    "title": "CBT疗法介绍"
}
```

**参数校验规则:**
- `role_id`: 必须为 "char_lin" 或 "char_chen"
- `content`: 1-10000 字符
- `title`: 最多 200 字符，可选

**成功响应:**
```json
{
    "success": true,
    "message": "文档添加成功"
}
```

**失败响应 (500):**
```json
{
    "detail": "文档添加失败"
}
```

### 7.2 DELETE /knowledge/clear/{role_id}

清空指定角色的知识库。

**路径参数:**
- `role_id`: 角色 ID

**成功响应:**
```json
{
    "success": true,
    "message": "知识库已清空"
}
```

**失败响应 (500):**
```json
{
    "detail": "清空失败"
}
```

### 7.3 POST /knowledge/reload

重新加载所有角色的知识库（从文件系统读取）。

**请求参数:** 无

**成功响应:**
```json
{
    "success": true,
    "message": "知识库重新加载完成",
    "stats": {
        "char_lin": 33,
        "char_chen": 492
    }
}
```

### 7.4 GET /knowledge/search

搜索知识库中的相关内容。

**查询参数:**
- `query`: 搜索关键词 (必填)
- `role_id`: 角色 ID (可选，不传则搜索所有角色)
- `top_k`: 返回结果数量 (默认 5)

**成功响应:**
```json
{
    "results": [
        "广泛性焦虑障碍（GAD）是一种以持续的、过度的担忧和焦虑为特征的心理障碍...",
        "认知行为疗法（CBT）是治疗焦虑症的首选心理治疗方法之一...",
        "焦虑症患者常伴有自主神经功能紊乱症状，如心悸、出汗、震颤等..."
    ]
}
```

---

## 8. 数据模型定义

### 8.1 RegisterRequest

```json
{
    "username": "string (3-50, alphanumeric)",
    "password": "string (6-100)",
    "email": "string (optional, must contain @)"
}
```

### 8.2 LoginRequest

```json
{
    "username": "string (3-50)",
    "password": "string (6-100)"
}
```

### 8.3 ChatRequest

```json
{
    "user_id": "string (1-100)",
    "role_id": "string (must be 'char_lin' or 'char_chen')",
    "message": "string (1-2000)"
}
```

### 8.4 ChatResponse

```json
{
    "response": "string (AI 回复内容)",
    "chat_id": "string (UUID v4)"
}
```

### 8.5 KnowledgeRequest

```json
{
    "role_id": "string (must be 'char_lin' or 'char_chen')",
    "content": "string (1-10000)",
    "title": "string (optional, max 200)"
}
```

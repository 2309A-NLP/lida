# API使用文档

## 基础信息

- **基础URL**: `http://localhost:8000`
- **内容类型**: `application/json`
- **编码**: `UTF-8`

## 核心API端点

### 1. 工单管理

#### 创建工单
```http
POST /api/workorders
Content-Type: application/json

{
  "title": "系统登录异常",
  "description": "无法登录系统，提示密码错误",
  "category": "技术支持",
  "priority": "高",
  "creator_name": "张三",
  "creator_contact": "13800138000"
}
```

**响应示例**:
```json
{
  "id": 1,
  "order_number": "WO202506250001",
  "title": "系统登录异常",
  "status": "待处理",
  "created_at": "2025-06-25T10:30:00"
}
```

#### 获取工单列表
```http
GET /api/workorders?status=待处理&category=技术支持&skip=0&limit=20
```

#### 获取工单详情
```http
GET /api/workorders/{workorder_id}
```

#### 更新工单
```http
PUT /api/workorders/{workorder_id}
Content-Type: application/json

{
  "status": "处理中",
  "assigned_to": "技术支持团队"
}
```

#### 删除工单
```http
DELETE /api/workorders/{workorder_id}
```

### 2. 工单消息

#### 添加消息
```http
POST /api/workorders/{workorder_id}/messages
Content-Type: application/json

{
  "content": "问题已解决",
  "sender": "技术支持",
  "sender_type": "agent"
}
```

#### 获取消息列表
```http
GET /api/workorders/{workorder_id}/messages
```

### 3. 智能对话

#### 聊天接口
```http
POST /api/chat
Content-Type: application/json

{
  "message": "我的系统登录不了",
  "user_name": "张三",
  "work_order_id": null
}
```

**响应示例**:
```json
{
  "message": "我已为您创建了工单...",
  "intent": "技术支持",
  "work_order_created": true,
  "work_order_id": 1
}
```

### 4. NLP分析

#### 文本分析
```http
POST /api/nlp/analyze
Content-Type: application/json

{
  "text": "系统出现故障，需要紧急修复",
  "analyze_intent": true,
  "analyze_entities": true,
  "analyze_sentiment": true
}
```

**响应示例**:
```json
{
  "intent": "故障报修",
  "intent_confidence": 0.85,
  "entities": [],
  "sentiment": "消极",
  "sentiment_score": 0.3,
  "keywords": ["系统", "故障", "紧急", "修复"]
}
```

### 5. Agent处理

#### 自动处理工单
```http
POST /api/workorders/{workorder_id}/process
```

### 6. 统计信息

#### 获取统计数据
```http
GET /api/stats
```

**响应示例**:
```json
{
  "total": 100,
  "pending": 20,
  "processing": 30,
  "completed": 45,
  "cancelled": 5,
  "by_category": {
    "技术支持": 40,
    "业务咨询": 30,
    "故障报修": 20,
    "需求开发": 10
  },
  "by_priority": {
    "低": 20,
    "中": 50,
    "高": 25,
    "紧急": 5
  },
  "avg_completion_time": 12.5
}
```

### 7. 系统状态

#### 健康检查
```http
GET /health
```

#### 系统状态
```http
GET /api/status
```

## 状态码

- `200`: 成功
- `201`: 创建成功
- `400`: 请求参数错误
- `404`: 资源不存在
- `500`: 服务器内部错误

## 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

## 数据字典

### 工单状态
- `待处理`: 新创建的工单
- `处理中`: 正在处理的工单
- `已完成`: 已完成的工单
- `已取消`: 已取消的工单
- `待审核`: 等待审核的工单

### 工单类别
- `技术支持`: 技术相关问题
- `业务咨询`: 业务流程咨询
- `故障报修`: 系统故障报修
- `需求开发`: 新功能开发需求
- `其他`: 其他类型

### 优先级
- `低`: 低优先级
- `中`: 中等优先级
- `高`: 高优先级
- `紧急`: 紧急处理

## 使用示例

### Python示例
```python
import requests

# 创建工单
response = requests.post(
    'http://localhost:8000/api/workorders',
    json={
        'title': '系统故障',
        'description': '无法访问',
        'category': '技术支持',
        'priority': '高',
        'creator_name': '张三'
    }
)

workorder = response.json()
print(f"工单编号: {workorder['order_number']}")
```

### JavaScript示例
```javascript
// 创建工单
fetch('http://localhost:8000/api/workorders', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    title: '系统故障',
    description: '无法访问',
    category: '技术支持',
    priority: '高',
    creator_name: '张三'
  })
})
.then(response => response.json())
.then(data => console.log('工单编号:', data.order_number));
```

## 交互式文档

访问 `http://localhost:8000/docs` 可查看Swagger UI交互式API文档，支持在线测试API。

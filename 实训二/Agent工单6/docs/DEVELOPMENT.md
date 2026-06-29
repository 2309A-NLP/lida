# 智能体任务工单系统 - 开发文档

## 项目架构

### 技术栈
- **后端**: FastAPI (Python 3.9+)
- **数据库**: SQLAlchemy ORM (SQLite/PostgreSQL)
- **前端**: HTML5 + CSS3 + Vanilla JavaScript
- **NLP**: 基于关键词匹配（可扩展到transformers/spaCy）
- **AI**: 支持OpenAI和Anthropic API集成

### 目录结构
```
Agent工单6/
├── backend/              # 后端服务
│   ├── __init__.py
│   ├── api.py           # FastAPI路由定义
│   ├── database.py      # 数据库连接管理
│   └── services.py      # 业务逻辑层
├── config/              # 配置文件
│   ├── __init__.py
│   └── config.yaml      # 主配置文件
├── models/              # 数据模型
│   ├── __init__.py
│   ├── database.py      # SQLAlchemy模型
│   └── schemas.py       # Pydantic schemas
├── frontend/            # 前端资源
│   ├── index.html       # 主页面
│   ├── css/
│   │   └── style.css    # 样式表
│   └── js/
│       └── app.js       # 前端逻辑
├── docs/                # 文档
├── logs/                # 日志文件
├── data/                # 数据库文件
├── main.py              # 应用入口
├── requirements.txt     # Python依赖
├── .env.example         # 环境变量模板
└── README.md            # 项目说明
```

## 核心模块说明

### 1. 数据模型层 (models/)

#### database.py
定义SQLAlchemy ORM模型：
- `WorkOrder`: 工单主表
- `WorkOrderMessage`: 工单消息表
- `WorkOrderLog`: 工单操作日志表
- `AgentTask`: Agent任务表

#### schemas.py
定义Pydantic数据验证模型：
- 请求模型: `*Create`, `*Update`
- 响应模型: `*Response`
- 业务模型: 统计、分析等

### 2. 后端服务层 (backend/)

#### api.py
FastAPI应用和路由定义：
- 工单CRUD操作
- 消息管理
- NLP分析
- 智能对话
- 统计查询

#### database.py
数据库连接管理：
- 数据库引擎创建
- 会话管理
- 依赖注入

#### services.py
业务逻辑实现：
- `WorkOrderService`: 工单管理服务
- `NLPService`: NLP分析服务
- `AgentService`: Agent自动化服务
- `ChatService`: 智能对话服务

### 3. 前端层 (frontend/)

#### index.html
单页应用主页面，包含：
- 数字人对话界面
- 工单列表展示
- 统计卡片
- 工单详情模态框

#### app.js
前端业务逻辑：
- API调用封装
- UI交互处理
- 数据渲染
- 事件监听

#### style.css
样式定义：
- 响应式布局
- 渐变色主题
- 动画效果
- 组件样式

## 数据库设计

### ER图
```
┌─────────────┐       ┌──────────────────┐
│  WorkOrder  │──1:N──│ WorkOrderMessage │
└─────────────┘       └──────────────────┘
       │
       │1:N
       │
┌──────────────┐       ┌────────────┐
│WorkOrderLog  │       │ AgentTask  │
└──────────────┘       └────────────┘
```

### 表结构

#### work_orders (工单表)
- id: 主键
- order_number: 工单编号（唯一）
- title: 标题
- description: 描述
- category: 类别（枚举）
- priority: 优先级（枚举）
- status: 状态（枚举）
- creator_name: 创建者
- assigned_to: 负责人
- intent: 意图（NLP）
- entities: 实体（JSON）
- sentiment: 情感
- created_at, updated_at, completed_at

#### work_order_messages (消息表)
- id: 主键
- work_order_id: 外键
- sender: 发送者
- sender_type: 发送者类型
- content: 内容
- created_at

#### work_order_logs (日志表)
- id: 主键
- work_order_id: 外键
- action: 操作
- description: 描述
- operator: 操作者
- created_at

#### agent_tasks (任务表)
- id: 主键
- work_order_id: 外键（可选）
- task_type: 任务类型
- status: 状态
- input_data, output_data: JSON
- started_at, completed_at

## API设计

### RESTful设计原则
- 使用HTTP动词: GET, POST, PUT, DELETE
- 资源URL命名: 复数名词
- 状态码: 200, 201, 400, 404, 500
- 响应格式: JSON

### 路由规划
```
GET    /                          # 首页
GET    /health                    # 健康检查
GET    /api/status                # 系统状态

# 工单相关
POST   /api/workorders            # 创建工单
GET    /api/workorders            # 工单列表
GET    /api/workorders/{id}       # 工单详情
PUT    /api/workorders/{id}       # 更新工单
DELETE /api/workorders/{id}       # 删除工单

# 消息相关
POST   /api/workorders/{id}/messages    # 添加消息
GET    /api/workorders/{id}/messages    # 消息列表

# NLP和AI
POST   /api/nlp/analyze           # NLP分析
POST   /api/chat                  # 智能对话
POST   /api/workorders/{id}/process     # Agent处理

# 统计
GET    /api/stats                 # 统计信息
```

## 业务流程

### 工单创建流程
```
1. 用户输入 → 2. NLP分析 → 3. 创建工单 → 4. 记录日志 → 5. 返回结果
```

### 智能对话流程
```
1. 接收消息 → 2. NLP分析 → 3. 判断意图 
   → 4a. 创建工单 → 5a. 返回工单信息
   → 4b. 添加消息 → 5b. 生成回复
```

### Agent处理流程
```
1. 接收任务 → 2. 分析工单 → 3. 自动分配 → 4. 更新状态 → 5. 添加消息
```

## 扩展开发

### 添加新的API端点

1. **在 api.py 中定义路由**:
```python
@app.get("/api/custom")
async def custom_endpoint(db: Session = Depends(get_db)):
    # 业务逻辑
    return {"result": "success"}
```

2. **创建对应的服务方法**:
```python
class CustomService:
    def __init__(self, db: Session):
        self.db = db
    
    def process(self):
        # 处理逻辑
        pass
```

### 集成高级NLP

替换 `NLPService` 中的简化实现：

```python
from transformers import pipeline

class NLPService:
    def __init__(self, db: Session):
        self.db = db
        self.classifier = pipeline("text-classification", 
                                   model="bert-base-chinese")
    
    def analyze_text(self, text: str):
        result = self.classifier(text)
        # 处理结果
        return result
```

### 添加数据库字段

1. **修改模型**:
```python
# models/database.py
class WorkOrder(Base):
    # ... 现有字段
    custom_field = Column(String(100))
```

2. **更新Schema**:
```python
# models/schemas.py
class WorkOrderResponse(BaseModel):
    # ... 现有字段
    custom_field: Optional[str] = None
```

3. **生成迁移** (使用Alembic):
```bash
alembic revision --autogenerate -m "add custom field"
alembic upgrade head
```

### 自定义前端组件

在 `app.js` 中添加新功能：
```javascript
function customFeature() {
    // 自定义逻辑
}

// 注册到页面加载事件
document.addEventListener('DOMContentLoaded', function() {
    customFeature();
});
```

## 性能优化

### 数据库优化
- 添加索引: `order_number`, `status`, `created_at`
- 使用连接池: SQLAlchemy连接池配置
- 查询优化: 使用 `joinedload` 预加载关联

### API优化
- 启用响应缓存
- 使用异步处理
- 分页查询: `skip` 和 `limit` 参数

### 前端优化
- 懒加载: 工单列表滚动加载
- 防抖: 输入框防抖处理
- 缓存: localStorage缓存配置

## 测试

### 单元测试示例
```python
import pytest
from backend.services import WorkOrderService

def test_create_workorder(db_session):
    service = WorkOrderService(db_session)
    workorder = service.create_workorder(
        WorkOrderCreate(
            title="测试工单",
            description="测试描述",
            category="技术支持",
            priority="中",
            creator_name="测试用户"
        )
    )
    assert workorder.id is not None
    assert workorder.order_number.startswith("WO")
```

### API测试
使用 pytest + httpx:
```python
def test_api_create_workorder(client):
    response = client.post("/api/workorders", json={
        "title": "测试工单",
        "description": "测试",
        "category": "技术支持",
        "priority": "中",
        "creator_name": "测试"
    })
    assert response.status_code == 201
```

## 部署建议

### 开发环境
```bash
python main.py
```

### 生产环境
使用Gunicorn + Nginx:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 backend.api:app
```

### Docker部署
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

## 安全考虑

1. **输入验证**: Pydantic自动验证
2. **SQL注入**: 使用ORM防止
3. **XSS防护**: 前端HTML转义
4. **CORS配置**: 生产环境限制来源
5. **密钥管理**: 使用环境变量
6. **日志审计**: 记录关键操作

## 贡献指南

1. Fork项目
2. 创建特性分支
3. 提交变更
4. 推送到分支
5. 创建Pull Request

## 许可证

MIT License

"""
Pydantic数据模型/Schema定义
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ==================== 工单相关 ====================

class WorkOrderCreate(BaseModel):
    """创建工单请求"""
    title: str = Field(..., min_length=1, max_length=200, description="工单标题")
    description: str = Field(..., min_length=1, description="工单详细描述")
    category: str = Field(..., description="工单类别")
    priority: str = Field(default="中", description="优先级")
    creator_name: str = Field(..., description="创建者姓名")
    creator_contact: Optional[str] = Field(None, description="创建者联系方式")


class WorkOrderUpdate(BaseModel):
    """更新工单请求"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None


class WorkOrderResponse(BaseModel):
    """工单响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    creator_name: str
    creator_contact: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    intent: Optional[str] = None
    entities: Optional[str] = None
    sentiment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class WorkOrderDetail(WorkOrderResponse):
    """工单详细信息（包含消息和日志）"""
    messages: List["MessageResponse"] = []
    logs: List["LogResponse"] = []


# ==================== 消息相关 ====================

class MessageCreate(BaseModel):
    """创建消息请求"""
    content: str = Field(..., min_length=1, description="消息内容")
    sender: Optional[str] = Field(None, description="发送者")
    sender_type: str = Field(default="user", description="发送者类型")


class MessageResponse(BaseModel):
    """消息响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    sender: str
    sender_type: str
    content: str
    created_at: datetime


# ==================== 日志相关 ====================

class LogResponse(BaseModel):
    """日志响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    action: str
    description: Optional[str] = None
    operator: str
    created_at: datetime


# ==================== NLP分析相关 ====================

class NLPAnalysisRequest(BaseModel):
    """NLP分析请求"""
    text: str = Field(..., description="待分析文本")
    analyze_intent: bool = Field(default=True, description="是否分析意图")
    analyze_entities: bool = Field(default=True, description="是否识别实体")
    analyze_sentiment: bool = Field(default=True, description="是否分析情感")


class NLPAnalysisResponse(BaseModel):
    """NLP分析结果"""
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    entities: List[dict] = []
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    keywords: List[str] = []


# ==================== Agent相关 ====================

class AgentTaskResponse(BaseModel):
    """Agent任务响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: Optional[int] = None
    task_type: str
    status: str
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, description="用户消息")
    work_order_id: Optional[int] = Field(None, description="关联的工单ID")
    user_name: Optional[str] = Field("访客", description="用户名称")
    user_id: Optional[str] = Field(None, description="用户ID")


class ChatResponse(BaseModel):
    """聊天响应"""
    message: str
    intent: Optional[str] = None
    suggested_action: Optional[str] = None
    work_order_created: bool = False
    work_order_id: Optional[int] = None


# ==================== 统计相关 ====================

class WorkOrderStats(BaseModel):
    """工单统计"""
    total: int
    total_count: Optional[int] = None
    pending: int
    pending_count: Optional[int] = None
    processing: int
    processing_count: Optional[int] = None
    completed: int
    completed_count: Optional[int] = None
    cancelled: int
    by_category: dict
    by_priority: dict
    avg_completion_time: Optional[float] = None  # 小时


class SystemStatus(BaseModel):
    """系统状态"""
    status: str = "running"
    version: str = "1.1.0"
    uptime: str
    database_connected: bool
    ai_service_status: str
    active_agents: int
    total_work_orders: int

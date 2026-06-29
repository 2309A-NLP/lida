"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class WorkOrderStatus(str, enum.Enum):
    """工单状态枚举"""
    PENDING = "待处理"
    PROCESSING = "处理中"
    COMPLETED = "已完成"
    CANCELLED = "已取消"
    REVIEWING = "待审核"


class WorkOrderPriority(str, enum.Enum):
    """工单优先级枚举"""
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"
    URGENT = "紧急"


class WorkOrderCategory(str, enum.Enum):
    """工单类别枚举"""
    TECHNICAL_SUPPORT = "技术支持"
    BUSINESS_INQUIRY = "业务咨询"
    FAULT_REPAIR = "故障报修"
    REQUIREMENT_DEV = "需求开发"
    OTHER = "其他"


class WorkOrder(Base):
    """工单数据模型"""
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_number = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(SQLEnum(WorkOrderCategory), nullable=False)
    priority = Column(SQLEnum(WorkOrderPriority), default=WorkOrderPriority.MEDIUM)
    status = Column(SQLEnum(WorkOrderStatus), default=WorkOrderStatus.PENDING)

    # 创建信息
    creator_name = Column(String(100), nullable=False)
    creator_contact = Column(String(200))

    # 处理信息
    assigned_to = Column(String(100))
    assigned_at = Column(DateTime)

    # NLP分析结果
    intent = Column(String(100))
    entities = Column(Text)  # JSON格式存储
    sentiment = Column(String(50))

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    # 关联
    messages = relationship("WorkOrderMessage", back_populates="work_order", cascade="all, delete-orphan")
    logs = relationship("WorkOrderLog", back_populates="work_order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkOrder(order_number={self.order_number}, title={self.title}, status={self.status})>"


class WorkOrderMessage(Base):
    """工单消息/对话记录"""
    __tablename__ = "work_order_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    sender = Column(String(100), nullable=False)  # 发送者名称或"系统"/"AI助手"
    sender_type = Column(String(20), nullable=False)  # user, agent, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    work_order = relationship("WorkOrder", back_populates="messages")

    def __repr__(self):
        return f"<WorkOrderMessage(id={self.id}, sender={self.sender}, sender_type={self.sender_type})>"


class WorkOrderLog(Base):
    """工单操作日志"""
    __tablename__ = "work_order_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    action = Column(String(100), nullable=False)  # 创建、更新、分配、完成等
    description = Column(Text)
    operator = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    work_order = relationship("WorkOrder", back_populates="logs")

    def __repr__(self):
        return f"<WorkOrderLog(id={self.id}, action={self.action}, operator={self.operator})>"


class AgentTask(Base):
    """Agent任务记录"""
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))
    task_type = Column(String(50), nullable=False)  # nlp_analysis, auto_response, assignment等
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    input_data = Column(Text)  # JSON格式
    output_data = Column(Text)  # JSON格式
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AgentTask(id={self.id}, task_type={self.task_type}, status={self.status})>"

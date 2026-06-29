"""
FastAPI路由和API端点定义
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import os

from backend.database import get_db, init_database
from models.schemas import (
    WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse, WorkOrderDetail,
    MessageCreate, MessageResponse, ChatRequest, ChatResponse,
    NLPAnalysisRequest, NLPAnalysisResponse, WorkOrderStats, SystemStatus
)
from backend.services import WorkOrderService, NLPService, AgentService, ChatService
from backend.money_agent import process_money_message
from backend.schedule_agent import process_schedule_message, get_schedule_repo, init_schedule_db, ReminderWorker
from backend.fund_agent import process_fund_question, get_fund_db_schema
from backend.prospectus_agent import process_prospectus_question, get_prospectus_stats

# 创建FastAPI应用
app = FastAPI(
    title="智能体任务工单系统",
    description="AI NLP-Agent数字人项目 - 智能任务工单管理系统 V1.1",
    version="1.1.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ==================== 启动和关闭事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    print("=" * 60)
    print("智能体任务工单系统 V1.1 启动中...")
    print("=" * 60)
    init_database()
    init_schedule_db()
    ReminderWorker().start()
    print("系统启动完成")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    print("系统正在关闭...")


# ==================== 首页 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    html_path = "frontend/index.html"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return """
    <html>
        <head><title>智能体任务工单系统</title></head>
        <body>
            <h1>智能体任务工单系统 V1.1</h1>
            <p>API文档: <a href="/docs">/docs</a></p>
        </body>
    </html>
    """


# ==================== 系统状态 ====================

@app.get("/api/status", response_model=SystemStatus)
async def get_system_status(db: Session = Depends(get_db)):
    """获取系统状态"""
    from models.database import WorkOrder

    total_orders = db.query(WorkOrder).count()

    return SystemStatus(
        status="running",
        version="1.1.0",
        uptime="运行中",
        database_connected=True,
        ai_service_status="正常",
        active_agents=0,
        total_work_orders=total_orders
    )


# ==================== 工单管理API ====================

@app.post("/api/workorders", response_model=WorkOrderResponse, status_code=201)
async def create_workorder(
    workorder: WorkOrderCreate,
    db: Session = Depends(get_db)
):
    """创建新工单"""
    service = WorkOrderService(db)
    return service.create_workorder(workorder)


@app.get("/api/workorders", response_model=List[WorkOrderResponse])
async def list_workorders(
    status: Optional[str] = Query(None, description="按状态筛选"),
    category: Optional[str] = Query(None, description="按类别筛选"),
    priority: Optional[str] = Query(None, description="按优先级筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    creator_name: Optional[str] = Query(None, description="按创建人筛选"),
    assigned_to: Optional[str] = Query(None, description="按负责人筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """获取工单列表（支持搜索和多条件筛选）"""
    service = WorkOrderService(db)
    return service.list_workorders(
        status=status,
        category=category,
        priority=priority,
        search=search,
        creator_name=creator_name,
        assigned_to=assigned_to,
        skip=skip,
        limit=limit
    )


@app.get("/api/workorders/export/csv")
async def export_workorders_csv(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """导出工单为CSV格式"""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    service = WorkOrderService(db)
    workorders = service.list_workorders(
        status=status,
        category=category,
        priority=priority,
        limit=10000
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['工单编号', '标题', '状态', '优先级', '类别', '创建人', '负责人', '创建时间', '更新时间'])

    for wo in workorders:
        writer.writerow([
            wo.order_number, wo.title, wo.status.value, wo.priority.value,
            wo.category.value, wo.creator_name, wo.assigned_to or '',
            wo.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            wo.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8-sig')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=workorders_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"}
    )


@app.get("/api/workorders/{workorder_id}", response_model=WorkOrderDetail)
async def get_workorder(
    workorder_id: int,
    db: Session = Depends(get_db)
):
    """获取工单详情"""
    service = WorkOrderService(db)
    workorder = service.get_workorder(workorder_id)
    if not workorder:
        raise HTTPException(status_code=404, detail="工单不存在")
    return workorder


@app.put("/api/workorders/{workorder_id}", response_model=WorkOrderResponse)
async def update_workorder(
    workorder_id: int,
    workorder: WorkOrderUpdate,
    db: Session = Depends(get_db)
):
    """更新工单"""
    service = WorkOrderService(db)
    updated = service.update_workorder(workorder_id, workorder)
    if not updated:
        raise HTTPException(status_code=404, detail="工单不存在")
    return updated


@app.delete("/api/workorders/{workorder_id}")
async def delete_workorder(
    workorder_id: int,
    db: Session = Depends(get_db)
):
    """删除工单"""
    service = WorkOrderService(db)
    success = service.delete_workorder(workorder_id)
    if not success:
        raise HTTPException(status_code=404, detail="工单不存在")
    return {"message": "工单已删除"}


@app.get("/api/workorders/{workorder_id}/logs")
async def get_workorder_logs(
    workorder_id: int,
    db: Session = Depends(get_db)
):
    """获取工单操作日志"""
    from models.database import WorkOrderLog
    logs = db.query(WorkOrderLog).filter(
        WorkOrderLog.work_order_id == workorder_id
    ).order_by(WorkOrderLog.created_at.desc()).all()
    return [
        {"id": log.id, "action": log.action, "description": log.description,
         "operator": log.operator, "created_at": log.created_at.isoformat()}
        for log in logs
    ]


# ==================== 工单消息API ====================

@app.post("/api/workorders/{workorder_id}/messages", response_model=MessageResponse)
async def add_message(
    workorder_id: int,
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """添加工单消息"""
    service = WorkOrderService(db)
    return service.add_message(workorder_id, message)


@app.get("/api/workorders/{workorder_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    workorder_id: int,
    db: Session = Depends(get_db)
):
    """获取工单消息列表"""
    service = WorkOrderService(db)
    return service.get_messages(workorder_id)


# ==================== NLP分析API ====================

@app.post("/api/nlp/analyze", response_model=NLPAnalysisResponse)
async def analyze_text(
    request: NLPAnalysisRequest,
    db: Session = Depends(get_db)
):
    """NLP文本分析"""
    service = NLPService(db)
    return service.analyze_text(
        request.text,
        request.analyze_intent,
        request.analyze_entities,
        request.analyze_sentiment
    )


# ==================== 智能对话API ====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """智能对话接口"""
    service = ChatService(db)
    return await service.process_chat(request)


# ==================== 统计API ====================

@app.get("/api/stats", response_model=WorkOrderStats)
async def get_statistics(db: Session = Depends(get_db)):
    """获取工单统计信息"""
    service = WorkOrderService(db)
    return service.get_statistics()


# ==================== Agent任务API ====================

@app.post("/api/workorders/{workorder_id}/process")
async def process_workorder(
    workorder_id: int,
    db: Session = Depends(get_db)
):
    """Agent自动处理工单"""
    agent_service = AgentService(db)
    result = await agent_service.process_workorder(workorder_id)
    return result


# ==================== 健康检查 ====================

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ==================== 记账本Agent API（工单一）====================

@app.post("/api/money/chat")
async def money_chat(request: dict):
    """记账本智能对话"""
    message = request.get("message", "").strip()
    if not message:
        return {"reply": "请输入消息"}
    reply = process_money_message(message)
    return {"reply": reply}


@app.get("/api/money/records")
async def money_records(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    member: Optional[str] = Query(None)
):
    """获取账目记录"""
    from backend.money_database import get_money_db
    db = get_money_db()
    sd = start_date or "2000-01-01"
    ed = end_date or "2099-12-31"
    records = db.query_by_date_range(sd, ed, member)
    return {"records": records, "count": len(records)}


@app.get("/api/money/summary")
async def money_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    member: Optional[str] = Query(None)
):
    """获取账目汇总"""
    from backend.money_database import get_money_db
    db = get_money_db()
    summary = db.get_summary(start_date, end_date, member)
    member_summary = db.get_member_summary(start_date, end_date)
    category_summary = db.get_category_summary(start_date, end_date)
    return {
        "summary": summary,
        "member_summary": member_summary,
        "category_summary": category_summary
    }


# ==================== 日程提醒Agent API（工单二）====================

@app.post("/api/schedule/chat")
async def schedule_chat(request: dict):
    """日程提醒智能对话"""
    question = request.get("question", request.get("message", "")).strip()
    if not question:
        return {"intent": "error", "answer": "请输入日程指令"}
    result = process_schedule_message(question)
    return result


@app.get("/api/schedule/list")
async def schedule_list():
    """获取所有有效日程"""
    repo = get_schedule_repo()
    items = repo.list_active()
    from backend.schedule_agent import serialize_schedule
    return {"items": [serialize_schedule(i) for i in items]}


@app.get("/api/schedule/today")
async def schedule_today():
    """获取今日日程"""
    repo = get_schedule_repo()
    items = repo.list_today()
    from backend.schedule_agent import serialize_schedule
    return {"items": [serialize_schedule(i) for i in items]}


@app.get("/api/schedule/reminders")
async def schedule_reminders(limit: int = Query(20)):
    """获取最近提醒记录"""
    repo = get_schedule_repo()
    items = repo.list_reminders(limit)
    return {"items": items}


@app.post("/api/schedule/delete")
async def schedule_delete(request: dict):
    """删除日程"""
    schedule_id = request.get("id")
    if not schedule_id:
        return {"success": False, "answer": "请提供日程ID"}
    result = process_schedule_message(f"删除日程 {schedule_id}")
    return result


@app.get("/api/schedule/stats")
async def schedule_stats():
    """日程统计"""
    repo = get_schedule_repo()
    stats = repo.stats()
    stats["today"] = datetime.now().strftime("%Y-%m-%d")
    return stats


# ==================== 基金数据问答Agent API（工单四）====================

@app.post("/api/fund/ask")
async def fund_ask(request: dict):
    """基金数据问答"""
    question = request.get("question", request.get("message", "")).strip()
    if not question:
        return {"answer": "请输入查询问题", "success": False}
    result = process_fund_question(question)
    return result


@app.get("/api/fund/schema")
async def fund_schema():
    """获取基金数据库结构"""
    return get_fund_db_schema()


# ==================== 招股书问答Agent API（工单五）====================

@app.post("/api/prospectus/ask")
async def prospectus_ask(request: dict):
    """招股书问答"""
    question = request.get("question", request.get("message", "")).strip()
    if not question:
        return {"answer": "请输入查询问题", "success": False}
    result = process_prospectus_question(question)
    return result


@app.get("/api/prospectus/stats")
async def prospectus_stats():
    """招股书知识库统计"""
    return get_prospectus_stats()




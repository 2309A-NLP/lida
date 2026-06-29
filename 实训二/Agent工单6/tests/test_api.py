"""
测试套件
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api import app
from backend.database import Base, get_db
from models.schemas import WorkOrderCreate


# 测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """创建测试客户端"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def test_read_root(client):
    """测试根路径"""
    response = client.get("/")
    assert response.status_code == 200


def test_health_check(client):
    """测试健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_workorder(client):
    """测试创建工单"""
    response = client.post("/api/workorders", json={
        "title": "测试工单",
        "description": "这是一个测试工单",
        "category": "技术支持",
        "priority": "中",
        "creator_name": "测试用户"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "测试工单"
    assert "order_number" in data
    assert data["status"] == "待处理"


def test_list_workorders(client):
    """测试获取工单列表"""
    # 先创建一个工单
    client.post("/api/workorders", json={
        "title": "测试工单",
        "description": "测试",
        "category": "技术支持",
        "priority": "中",
        "creator_name": "测试"
    })

    response = client.get("/api/workorders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_workorder_detail(client):
    """测试获取工单详情"""
    # 创建工单
    create_response = client.post("/api/workorders", json={
        "title": "测试工单",
        "description": "测试",
        "category": "技术支持",
        "priority": "中",
        "creator_name": "测试"
    })
    workorder_id = create_response.json()["id"]

    # 获取详情
    response = client.get(f"/api/workorders/{workorder_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == workorder_id


def test_update_workorder(client):
    """测试更新工单"""
    # 创建工单
    create_response = client.post("/api/workorders", json={
        "title": "测试工单",
        "description": "测试",
        "category": "技术支持",
        "priority": "中",
        "creator_name": "测试"
    })
    workorder_id = create_response.json()["id"]

    # 更新工单
    response = client.put(f"/api/workorders/{workorder_id}", json={
        "status": "处理中",
        "assigned_to": "技术团队"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "处理中"
    assert data["assigned_to"] == "技术团队"


def test_chat_creates_workorder(client):
    """测试聊天创建工单"""
    response = client.post("/api/chat", json={
        "message": "系统出现故障，无法登录",
        "user_name": "测试用户"
    })
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    # 根据NLP分析，可能会创建工单
    if data.get("work_order_created"):
        assert data["work_order_id"] is not None


def test_nlp_analyze(client):
    """测试NLP分析"""
    response = client.post("/api/nlp/analyze", json={
        "text": "系统出现严重故障，需要紧急修复",
        "analyze_intent": True,
        "analyze_entities": True,
        "analyze_sentiment": True
    })
    assert response.status_code == 200
    data = response.json()
    assert "intent" in data
    assert "sentiment" in data


def test_get_statistics(client):
    """测试获取统计信息"""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "pending" in data
    assert "processing" in data
    assert "completed" in data


def test_search_workorders(client):
    """测试搜索工单"""
    # 创建工单
    client.post("/api/workorders", json={
        "title": "网络故障排查",
        "description": "办公室网络无法连接",
        "category": "故障报修",
        "priority": "高",
        "creator_name": "测试员"
    })

    # 搜索标题
    response = client.get("/api/workorders?search=网络")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any("网络" in wo["title"] or "网络" in wo["description"] for wo in data)


def test_filter_by_category(client):
    """测试按类别筛选"""
    client.post("/api/workorders", json={
        "title": "业务咨询测试",
        "description": "咨询业务流程",
        "category": "业务咨询",
        "priority": "低",
        "creator_name": "测试员"
    })

    response = client.get("/api/workorders?category=业务咨询")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(wo["category"] == "业务咨询" for wo in data)


def test_filter_by_priority(client):
    """测试按优先级筛选"""
    client.post("/api/workorders", json={
        "title": "紧急故障",
        "description": "服务器宕机",
        "category": "故障报修",
        "priority": "紧急",
        "creator_name": "测试员"
    })

    response = client.get("/api/workorders?priority=紧急")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert all(wo["priority"] == "紧急" for wo in data)


def test_add_and_get_messages(client):
    """测试添加和获取消息"""
    # 创建工单
    r = client.post("/api/workorders", json={
        "title": "消息测试工单",
        "description": "测试消息功能",
        "category": "技术支持",
        "priority": "中",
        "creator_name": "测试员"
    })
    wo_id = r.json()["id"]

    # 添加消息
    r = client.post(f"/api/workorders/{wo_id}/messages", json={
        "content": "这是第一条测试消息",
        "sender": "测试员"
    })
    assert r.status_code == 200
    assert r.json()["content"] == "这是第一条测试消息"

    # 获取消息列表
    r = client.get(f"/api/workorders/{wo_id}/messages")
    assert r.status_code == 200
    messages = r.json()
    assert len(messages) >= 1
    assert any(m["content"] == "这是第一条测试消息" for m in messages)


def test_get_workorder_logs(client):
    """测试获取操作日志"""
    # 创建工单（自动产生日志）
    r = client.post("/api/workorders", json={
        "title": "日志测试工单",
        "description": "测试操作日志功能",
        "category": "技术支持",
        "priority": "中",
        "creator_name": "测试员"
    })
    wo_id = r.json()["id"]

    # 更新工单（产生更多日志）
    client.put(f"/api/workorders/{wo_id}", json={"status": "处理中"})

    # 获取日志
    r = client.get(f"/api/workorders/{wo_id}/logs")
    assert r.status_code == 200
    logs = r.json()
    assert len(logs) >= 1
    assert all("action" in log and "operator" in log for log in logs)


def test_export_csv(client):
    """测试导出CSV"""
    # 创建几个工单
    for i in range(3):
        client.post("/api/workorders", json={
            "title": f"导出测试工单{i}",
            "description": f"测试导出功能{i}",
            "category": "技术支持",
            "priority": "中",
            "creator_name": "测试员"
        })

    # 导出CSV
    r = client.get("/api/workorders/export/csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    # 验证CSV内容包含表头
    content = r.content.decode("utf-8-sig")
    assert "工单编号" in content
    assert "标题" in content
    assert "状态" in content


def test_agent_process_workorder(client):
    """测试Agent自动处理工单"""
    # 创建工单
    r = client.post("/api/workorders", json={
        "title": "需要自动处理的工单",
        "description": "服务器出现故障",
        "category": "故障报修",
        "priority": "高",
        "creator_name": "测试员"
    })
    wo_id = r.json()["id"]

    # Agent处理
    r = client.post(f"/api/workorders/{wo_id}/process")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "message" in data


def test_delete_workorder(client):
    """测试删除工单"""
    # 创建工单
    r = client.post("/api/workorders", json={
        "title": "待删除工单",
        "description": "测试删除功能",
        "category": "其他",
        "priority": "低",
        "creator_name": "测试员"
    })
    wo_id = r.json()["id"]

    # 删除
    r = client.delete(f"/api/workorders/{wo_id}")
    assert r.status_code == 200

    # 确认已删除
    r = client.get(f"/api/workorders/{wo_id}")
    assert r.status_code == 404


def test_workorder_not_found(client):
    """测试工单不存在返回404"""
    r = client.get("/api/workorders/99999")
    assert r.status_code == 404


def test_system_status(client):
    """测试系统状态"""
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "running"
    assert data["version"] == "1.1.0"
    assert data["database_connected"] is True


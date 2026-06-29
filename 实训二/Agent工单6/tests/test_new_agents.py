"""
新增功能测试：记账本、日程、基金、招股书
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api import app
from backend.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    db.close()
    Base.metadata.drop_all(bind=engine)


# ==================== 记账本测试 ====================

def test_money_chat_help(client):
    """测试记账本 - 无金额时返回帮助"""
    r = client.post("/api/money/chat", json={"message": "你好"})
    assert r.status_code == 200
    assert "reply" in r.json()


def test_money_chat_record(client):
    """测试记账本 - 识别记账请求"""
    r = client.post("/api/money/chat", json={"message": "今天女儿买了登山鞋499元"})
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    # 应该触发确认流程
    assert "确认" in data["reply"] or "499" in data["reply"]


def test_money_chat_query(client):
    """测试记账本 - 查询消费明细"""
    r = client.post("/api/money/chat", json={"message": "查询本月消费明细"})
    assert r.status_code == 200
    assert "reply" in r.json()


def test_money_records_api(client):
    """测试记账本 - 获取记录列表"""
    r = client.get("/api/money/records")
    assert r.status_code == 200
    data = r.json()
    assert "records" in data
    assert "count" in data


def test_money_summary_api(client):
    """测试记账本 - 获取汇总信息"""
    r = client.get("/api/money/summary")
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "member_summary" in data
    assert "category_summary" in data


# ==================== 日程提醒测试 ====================

def test_schedule_chat_add(client):
    """测试日程 - 添加日程"""
    r = client.post("/api/schedule/chat", json={"question": "提醒我明天下午3点开会"})
    assert r.status_code == 200
    data = r.json()
    assert "intent" in data
    assert "answer" in data


def test_schedule_chat_list(client):
    """测试日程 - 查询日程列表"""
    r = client.post("/api/schedule/chat", json={"question": "我的日程有哪些"})
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "list"
    assert "items" in data


def test_schedule_list_api(client):
    """测试日程 - 获取日程列表API"""
    r = client.get("/api/schedule/list")
    assert r.status_code == 200
    assert "items" in r.json()


def test_schedule_today_api(client):
    """测试日程 - 获取今日日程"""
    r = client.get("/api/schedule/today")
    assert r.status_code == 200
    assert "items" in r.json()


def test_schedule_reminders_api(client):
    """测试日程 - 获取提醒记录"""
    r = client.get("/api/schedule/reminders")
    assert r.status_code == 200
    assert "items" in r.json()


def test_schedule_stats_api(client):
    """测试日程 - 统计信息"""
    r = client.get("/api/schedule/stats")
    assert r.status_code == 200
    data = r.json()
    assert "active_schedules" in data
    assert "reminder_logs" in data


def test_schedule_guide_response(client):
    """测试日程 - 无法识别时返回引导"""
    r = client.post("/api/schedule/chat", json={"question": "随便说点什么"})
    assert r.status_code == 200
    data = r.json()
    assert "intent" in data
    assert "answer" in data


# ==================== 基金数据问答测试 ====================

def test_fund_ask_basic(client):
    """测试基金 - 基本查询"""
    r = client.post("/api/fund/ask", json={"question": "基金数据库有哪些表"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "success" in data


def test_fund_ask_info(client):
    """测试基金 - 查询基金信息"""
    r = client.post("/api/fund/ask", json={"question": "查询基金基本信息"})
    assert r.status_code == 200
    assert "answer" in r.json()


def test_fund_schema_api(client):
    """测试基金 - 获取数据库结构"""
    r = client.get("/api/fund/schema")
    assert r.status_code == 200
    data = r.json()
    assert "available" in data
    assert "tables" in data


# ==================== 招股书问答测试 ====================

def test_prospectus_ask_basic(client):
    """测试招股书 - 基本查询"""
    r = client.post("/api/prospectus/ask", json={"question": "公司主营业务是什么"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "success" in data


def test_prospectus_ask_empty(client):
    """测试招股书 - 空查询"""
    r = client.post("/api/prospectus/ask", json={"question": ""})
    assert r.status_code == 200
    assert "answer" in r.json()


def test_prospectus_stats_api(client):
    """测试招股书 - 知识库统计"""
    r = client.get("/api/prospectus/stats")
    assert r.status_code == 200
    data = r.json()
    assert "available" in data
    assert "total_docs" in data

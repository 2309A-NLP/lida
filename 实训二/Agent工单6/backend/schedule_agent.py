"""
工单编号：人工智能NLP-Agent数字人项目-日程提醒智能体任务
日程管理数据库和业务逻辑
"""
import sqlite3
import re
import threading
import time
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'schedule_agent.db')
DB_LOCK = threading.Lock()

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
REMINDER_TEMPLATES = [
    "温馨提醒：（{content}）的时间到啦！",
    "主人！是时候（{content}）了喔~",
    "亲爱的主人，现在是（{content}）的时候啦！",
    "嘿，主人，该（{content}）了哦~",
]


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schedule_db():
    with DB_LOCK:
        conn = get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    time_segment TEXT NOT NULL,
                    repeat_rule TEXT NOT NULL DEFAULT '0000000',
                    planned_at TEXT NOT NULL,
                    time_label TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_triggered_key TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at TEXT NOT NULL
                );
            """)
            conn.commit()
        finally:
            conn.close()


def describe_repeat(rule):
    if rule == "0000000": return "单次"
    if rule == "1111111": return "每天"
    days = [WEEKDAY_NAMES[i] for i, b in enumerate(rule) if b == "1"]
    return "每周 " + "/".join(days) if days else "单次"


def serialize_schedule(row: dict) -> dict:
    return {
        "id": row["id"],
        "content": row["content"],
        "time_segment": row["time_segment"],
        "repeat_rule": row["repeat_rule"],
        "repeat_text": describe_repeat(row["repeat_rule"]),
        "planned_at": row["planned_at"],
        "time_label": row["time_label"],
        "status": row["status"],
    }


class ScheduleRepository:
    def create(self, content, planned_at, repeat_rule):
        now = datetime.now().isoformat()
        with DB_LOCK:
            conn = get_connection()
            try:
                cur = conn.execute(
                    """INSERT INTO schedules (content,time_segment,repeat_rule,planned_at,time_label,status,created_at,updated_at,last_triggered_key)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (content, planned_at.strftime("%H:%M"), repeat_rule,
                     planned_at.isoformat(), planned_at.strftime("%Y/%m/%d %H:%M"),
                     "active", now, now, "")
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def list_active(self):
        with DB_LOCK:
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM schedules WHERE status='active' ORDER BY planned_at ASC"
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def list_today(self):
        today = date.today()
        result = []
        for item in self.list_active():
            planned_at = datetime.fromisoformat(item["planned_at"])
            if item["repeat_rule"] == "0000000":
                if planned_at.date() == today:
                    result.append(item)
            elif item["repeat_rule"][today.weekday()] == "1":
                result.append(item)
        return result

    def get(self, schedule_id):
        with DB_LOCK:
            conn = get_connection()
            try:
                row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def update(self, schedule_id, content, planned_at, repeat_rule):
        now = datetime.now().isoformat()
        with DB_LOCK:
            conn = get_connection()
            try:
                cur = conn.execute(
                    """UPDATE schedules SET content=?,time_segment=?,repeat_rule=?,planned_at=?,time_label=?,updated_at=?,last_triggered_key=''
                       WHERE id=? AND status='active'""",
                    (content, planned_at.strftime("%H:%M"), repeat_rule,
                     planned_at.isoformat(), planned_at.strftime("%Y/%m/%d %H:%M"), now, schedule_id)
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def delete(self, schedule_id):
        item = self.get(schedule_id)
        if not item:
            return None
        with DB_LOCK:
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE schedules SET status='deleted', updated_at=? WHERE id=?",
                    (datetime.now().isoformat(), schedule_id)
                )
                conn.commit()
                return item
            finally:
                conn.close()

    def add_reminder(self, schedule_id, message):
        now = datetime.now().isoformat()
        with DB_LOCK:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO reminders (schedule_id,message,triggered_at) VALUES (?,?,?)",
                    (schedule_id, message, now)
                )
                conn.commit()
            finally:
                conn.close()

    def mark_triggered(self, schedule_id, trigger_key):
        with DB_LOCK:
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE schedules SET last_triggered_key=?, updated_at=? WHERE id=?",
                    (trigger_key, datetime.now().isoformat(), schedule_id)
                )
                conn.commit()
            finally:
                conn.close()

    def list_reminders(self, limit=20):
        with DB_LOCK:
            conn = get_connection()
            try:
                rows = conn.execute(
                    """SELECT r.id, r.schedule_id, r.message, r.triggered_at, s.content
                       FROM reminders r JOIN schedules s ON s.id=r.schedule_id
                       ORDER BY r.triggered_at DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def stats(self):
        with DB_LOCK:
            conn = get_connection()
            try:
                active = conn.execute("SELECT COUNT(*) FROM schedules WHERE status='active'").fetchone()[0]
                logs = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
                return {"active_schedules": active, "reminder_logs": logs}
            finally:
                conn.close()


def _weekday_rule(text):
    mapping = {"周一": 0, "星期一": 0, "周二": 1, "星期二": 1, "周三": 2, "星期三": 2,
               "周四": 3, "星期四": 3, "周五": 4, "星期五": 4, "周六": 5, "星期六": 5,
               "周日": 6, "星期日": 6, "星期天": 6, "周天": 6}
    bits = ["0"] * 7
    for k, i in mapping.items():
        if k in text:
            bits[i] = "1"
    return "".join(bits)


def _parse_schedule_datetime(text):
    base = datetime.now()
    day_offset = 0
    if "明天" in text: day_offset = 1
    elif "后天" in text: day_offset = 2

    explicit = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', text)
    if explicit:
        y, mo, d = map(int, explicit.groups())
        base = datetime(y, mo, d, base.hour, base.minute)
    else:
        base = base + timedelta(days=day_offset)

    hour, minute = None, 0
    hm = re.search(r'(\d{1,2})[:：点时](\d{1,2})?', text)
    if hm:
        hour = int(hm.group(1))
        if hm.group(2): minute = int(hm.group(2))
    else:
        half = re.search(r'(\d{1,2})点半', text)
        if half:
            hour = int(half.group(1)); minute = 30

    if hour is None: return None

    if any(t in text for t in ["下午", "晚上", "傍晚"]) and hour < 12: hour += 12
    if "中午" in text and hour < 11: hour += 12

    try:
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except ValueError:
        return None

    if not explicit and day_offset == 0 and candidate < datetime.now() and "今天" not in text:
        candidate += timedelta(days=1)
    return candidate


def _parse_content(text):
    content = text
    content = re.sub(r'^(添加|新增|创建|设置|安排)(一个)?日程[:：]?', '', content)
    content = re.sub(r'^(提醒我|帮我记得|记得)', '', content)
    content = re.sub(r'(今天|明天|后天|每周[一二三四五六日天]?|每天|每日)', '', content)
    content = re.sub(r'(上午|下午|晚上|中午|凌晨|早上|傍晚)', '', content)
    content = re.sub(r'\d{1,2}[:：点时]\d{0,2}', '', content)
    content = re.sub(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?', '', content)
    content = re.sub(r'(提醒|通知|一下|哦|呀|啊|吧)$', '', content)
    content = re.sub(r'^[，。,.\s]+|[，。,.\s]+$', '', content)
    return content.strip() or None


_repo = ScheduleRepository()


def process_schedule_message(text: str) -> dict:
    norm = re.sub(r'\s+', '', text.strip())

    # 删除
    if any(kw in norm for kw in ("删除日程", "取消日程")):
        m = re.search(r'(删除日程|取消日程)\s*(\d+)', norm)
        if not m:
            return {"intent": "delete", "success": False, "answer": "请告诉我要删除哪一条日程，例如：删除日程 1"}
        sid = int(m.group(2))
        deleted = _repo.delete(sid)
        if not deleted:
            return {"intent": "delete", "success": False, "answer": f"没有找到日程 {sid}"}
        return {"intent": "delete", "success": True,
                "answer": f"已删除日程 {sid}：{deleted['time_segment']} 提醒您 {deleted['content']}",
                "item": serialize_schedule(deleted)}

    # 修改
    if any(kw in norm for kw in ("修改日程", "更新日程", "编辑日程")):
        m = re.search(r'(修改日程|更新日程|编辑日程)\s*(\d+)', norm)
        if not m:
            return {"intent": "update", "success": False, "answer": "请告诉我要修改哪一条日程，例如：修改日程 1 为 明天下午3点开会"}
        sid = int(m.group(2))
        origin = _repo.get(sid)
        if not origin:
            return {"intent": "update", "success": False, "answer": f"没有找到日程 {sid}"}
        changed = re.sub(r'^(修改日程|更新日程|编辑日程)\s*\d+\s*(为|成)?', '', text).strip()
        repeat_rule = _weekday_rule(changed)
        if "每天" in changed or "每日" in changed: repeat_rule = "1111111"
        planned_at = _parse_schedule_datetime(changed)
        content = _parse_content(changed)
        if not planned_at or not content:
            return {"intent": "update", "success": False, "answer": f"修改日程 {sid} 还缺少时间或内容"}
        _repo.update(sid, content, planned_at, repeat_rule)
        updated = _repo.get(sid)
        return {"intent": "update", "success": True,
                "answer": f"已修改日程 {sid}：{planned_at.strftime('%H:%M')} 提醒您 {content}",
                "item": serialize_schedule(updated)}

    # 查询
    if any(kw in norm for kw in ("日程有哪些", "查看日程", "我的日程", "今天日程", "全部日程",
                                   "查询日程", "今天的日程", "有什么日程", "有哪些日程",
                                   "日程安排", "我今天", "今天有什", "什么日程", "日程列表",
                                   "查一下日程", "看看日程")):
        today_only = "今天" in norm
        items = _repo.list_today() if today_only else _repo.list_active()
        if not items:
            return {"intent": "list", "answer": "当前没有日程", "items": []}
        lines = ["以下是您的日程："]
        for item in items:
            lines.append(f"{item['id']} | {item['time_segment']} | {describe_repeat(item['repeat_rule'])} | {item['content']}")
        return {"intent": "list", "answer": "\n".join(lines), "items": [serialize_schedule(i) for i in items]}

    # 添加
    if any(kw in norm for kw in ("添加日程", "新增日程", "创建日程", "设置日程", "提醒我", "帮我记得", "日程：")):
        repeat_rule = _weekday_rule(norm)
        if "每天" in norm or "每日" in norm: repeat_rule = "1111111"
        planned_at = _parse_schedule_datetime(text)
        content = _parse_content(text)
        missing = []
        if not content: missing.append("事项内容")
        if not planned_at: missing.append("提醒时间")
        if missing:
            return {"intent": "create", "success": False,
                    "answer": f"还需要：{'、'.join(missing)}。例如：提醒我明天下午3点开会",
                    "missing_fields": missing}
        sid = _repo.create(content, planned_at, repeat_rule)
        return {"intent": "create", "success": True, "schedule_id": sid,
                "answer": f"已添加日程 {sid}：{planned_at.strftime('%Y/%m/%d %H:%M')} 提醒您 {content}（{describe_repeat(repeat_rule)}）"}

    return {"intent": "guide",
            "answer": "我可以帮您管理日程：\n1. 提醒我明天下午5点开会\n2. 我今天的日程有哪些？\n3. 删除日程 1\n4. 修改日程 1 为 明天下午3点提交周报"}


class ReminderWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)

    def run(self):
        while True:
            try:
                self._tick()
            except Exception as e:
                print(f"[ReminderWorker] 错误: {e}")
            time.sleep(30)

    def _tick(self):
        now = datetime.now().replace(second=0, microsecond=0)
        trigger_key = now.strftime("%Y-%m-%d %H:%M")
        for item in _repo.list_active():
            if item["last_triggered_key"] == trigger_key:
                continue
            planned_at = datetime.fromisoformat(item["planned_at"])
            should = False
            if item["repeat_rule"] == "0000000":
                should = planned_at.replace(second=0, microsecond=0) == now
            elif item["repeat_rule"][now.weekday()] == "1":
                should = planned_at.strftime("%H:%M") == now.strftime("%H:%M")
            if should:
                msg = REMINDER_TEMPLATES[item["id"] % len(REMINDER_TEMPLATES)].format(content=item["content"])
                _repo.add_reminder(item["id"], msg)
                _repo.mark_triggered(item["id"], trigger_key)
                print(f"[Reminder] {msg}")


def get_schedule_repo():
    return _repo

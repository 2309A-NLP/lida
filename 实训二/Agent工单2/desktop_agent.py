"""
工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
日程提醒智能体服务端
"""
from __future__ import annotations

import io
import json
import mimetypes
import os
import re
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

API_HOST = "0.0.0.0"
API_PORT = 5057
DB_PATH = Path(__file__).with_name("schedule_agent.db")
STATIC_DIR = Path(__file__).parent
REMINDER_TEMPLATES = [
    "温馨提醒：（{content}）的时间到啦，主人！",
    "主人！是时候（{content}）了喔~",
    "亲爱的主人，现在是（{content}）的时候啦！",
    "嘿，主人，该（{content}）了哦~",
]
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
DB_LOCK = threading.Lock()


def ensure_utf8_stdout() -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


ensure_utf8_stdout()


def json_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with DB_LOCK:
        conn = get_connection()
        try:
            conn.executescript(
                """
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
                    last_triggered_at TEXT,
                    last_triggered_key TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at TEXT NOT NULL,
                    FOREIGN KEY(schedule_id) REFERENCES schedules(id)
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()


def now_local() -> datetime:
    return datetime.now()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text.strip())


def format_time_label(dt: datetime) -> str:
    return dt.strftime("%Y/%m/%d %H:%M")


def describe_repeat_rule(repeat_rule: str) -> str:
    if repeat_rule == "0000000":
        return "单次"
    if repeat_rule == "1111111":
        return "每天"
    days = [WEEKDAY_NAMES[index] for index, bit in enumerate(repeat_rule) if bit == "1"]
    return "每周 " + " / ".join(days) if days else "单次"


def weekday_rule_from_text(text: str) -> str:
    mapping = {
        "周一": 0,
        "星期一": 0,
        "周二": 1,
        "星期二": 1,
        "周三": 2,
        "星期三": 2,
        "周四": 3,
        "星期四": 3,
        "周五": 4,
        "星期五": 4,
        "周六": 5,
        "星期六": 5,
        "周日": 6,
        "星期日": 6,
        "星期天": 6,
        "周天": 6,
    }
    bits = ["0"] * 7
    for key, index in mapping.items():
        if key in text:
            bits[index] = "1"
    return "".join(bits)


def compact_schedule_line(item: dict[str, Any]) -> str:
    return f"{item['time_segment']}|{item['repeat_rule']}|{item['content']}"


@dataclass
class ParsedSchedule:
    content: str | None
    planned_at: datetime | None
    repeat_rule: str
    missing_fields: list[str]


class ScheduleRepository:
    def create_schedule(self, content: str, planned_at: datetime, repeat_rule: str) -> int:
        now_str = now_local().isoformat()
        with DB_LOCK:
            conn = get_connection()
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO schedules (
                        content, time_segment, repeat_rule, planned_at, time_label,
                        status, created_at, updated_at, last_triggered_at, last_triggered_key
                    ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, NULL, '')
                    """,
                    (
                        content,
                        planned_at.strftime("%H:%M"),
                        repeat_rule,
                        planned_at.isoformat(),
                        format_time_label(planned_at),
                        now_str,
                        now_str,
                    ),
                )
                conn.commit()
                return int(cursor.lastrowid)
            finally:
                conn.close()

    def list_active_schedules(self) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = get_connection()
            try:
                rows = conn.execute(
                    """
                    SELECT id, content, time_segment, repeat_rule, planned_at, time_label, status,
                           created_at, updated_at, last_triggered_at, last_triggered_key
                    FROM schedules
                    WHERE status = 'active'
                    ORDER BY planned_at ASC, id ASC
                    """
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def list_today_schedules(self) -> list[dict[str, Any]]:
        today = now_local().date()
        results = []
        for item in self.list_active_schedules():
            planned_at = datetime.fromisoformat(item["planned_at"])
            if item["repeat_rule"] == "0000000":
                if planned_at.date() == today:
                    results.append(item)
                continue
            if item["repeat_rule"][today.weekday()] == "1":
                results.append(item)
        return results

    def get_schedule(self, schedule_id: int) -> dict[str, Any] | None:
        with DB_LOCK:
            conn = get_connection()
            try:
                row = conn.execute(
                    """
                    SELECT id, content, time_segment, repeat_rule, planned_at, time_label, status,
                           created_at, updated_at, last_triggered_at, last_triggered_key
                    FROM schedules
                    WHERE id = ?
                    """,
                    (schedule_id,),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def update_schedule(self, schedule_id: int, content: str, planned_at: datetime, repeat_rule: str) -> bool:
        now_str = now_local().isoformat()
        with DB_LOCK:
            conn = get_connection()
            try:
                cursor = conn.execute(
                    """
                    UPDATE schedules
                    SET content = ?, time_segment = ?, repeat_rule = ?, planned_at = ?, time_label = ?,
                        updated_at = ?, last_triggered_key = ''
                    WHERE id = ? AND status = 'active'
                    """,
                    (
                        content,
                        planned_at.strftime("%H:%M"),
                        repeat_rule,
                        planned_at.isoformat(),
                        format_time_label(planned_at),
                        now_str,
                        schedule_id,
                    ),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def delete_schedule(self, schedule_id: int) -> dict[str, Any] | None:
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        with DB_LOCK:
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE schedules SET status = 'deleted', updated_at = ? WHERE id = ?",
                    (now_local().isoformat(), schedule_id),
                )
                conn.commit()
                return schedule
            finally:
                conn.close()

    def add_reminder(self, schedule_id: int, message: str, triggered_at: datetime) -> None:
        with DB_LOCK:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO reminders (schedule_id, message, triggered_at) VALUES (?, ?, ?)",
                    (schedule_id, message, triggered_at.isoformat()),
                )
                conn.commit()
            finally:
                conn.close()

    def list_recent_reminders(self, limit: int = 20) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = get_connection()
            try:
                rows = conn.execute(
                    """
                    SELECT r.id, r.schedule_id, r.message, r.triggered_at, s.content
                    FROM reminders r
                    JOIN schedules s ON s.id = r.schedule_id
                    ORDER BY r.triggered_at DESC, r.id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def mark_triggered(self, schedule_id: int, trigger_key: str, triggered_at: datetime) -> None:
        with DB_LOCK:
            conn = get_connection()
            try:
                conn.execute(
                    """
                    UPDATE schedules
                    SET last_triggered_at = ?, last_triggered_key = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (triggered_at.isoformat(), trigger_key, triggered_at.isoformat(), schedule_id),
                )
                conn.commit()
            finally:
                conn.close()

    def stats(self) -> dict[str, Any]:
        with DB_LOCK:
            conn = get_connection()
            try:
                total_active = conn.execute("SELECT COUNT(*) FROM schedules WHERE status = 'active'").fetchone()[0]
                total_reminders = conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
                return {
                    "active_schedules": total_active,
                    "reminder_logs": total_reminders,
                }
            finally:
                conn.close()


class ScheduleParser:
    def parse(self, text: str) -> ParsedSchedule:
        normalized = normalize_text(text)
        repeat_rule = self._parse_repeat_rule(normalized)
        planned_at = self._parse_datetime(normalized)
        content = self._parse_content(text)

        missing_fields = []
        if not content:
            missing_fields.append("事项内容")
        if not planned_at:
            missing_fields.append("提醒时间")

        return ParsedSchedule(content=content, planned_at=planned_at, repeat_rule=repeat_rule, missing_fields=missing_fields)

    def _parse_repeat_rule(self, text: str) -> str:
        if "每天" in text or "每日" in text:
            return "1111111"
        weekday_rule = weekday_rule_from_text(text)
        if weekday_rule != "0000000":
            return weekday_rule
        return "0000000"

    def _parse_datetime(self, text: str) -> datetime | None:
        base = now_local()
        day_offset = 0
        if "明天" in text:
            day_offset = 1
        elif "后天" in text:
            day_offset = 2

        explicit_date = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
        if explicit_date:
            year, month, day = map(int, explicit_date.groups())
            base = datetime(year, month, day, base.hour, base.minute)
        else:
            base = base + timedelta(days=day_offset)

        hour = None
        minute = 0

        hm_match = re.search(r"(\d{1,2})[:：点时](\d{1,2})?", text)
        if hm_match:
            hour = int(hm_match.group(1))
            if hm_match.group(2):
                minute = int(hm_match.group(2))
        else:
            half_match = re.search(r"(\d{1,2})点半", text)
            if half_match:
                hour = int(half_match.group(1))
                minute = 30

        if hour is None:
            return None

        if any(token in text for token in ["下午", "晚上", "傍晚"]) and hour < 12:
            hour += 12
        if "中午" in text and hour < 11:
            hour += 12
        if "凌晨" in text and hour == 12:
            hour = 0

        try:
            candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            return None

        if explicit_date is None and day_offset == 0 and candidate < now_local() and "今天" not in text:
            candidate += timedelta(days=1)
        return candidate

    def _parse_content(self, text: str) -> str | None:
        content = text.strip()
        content = re.sub(r"^(添加|新增|创建|设置|安排)(一个)?日程[:：]?", "", content)
        content = re.sub(r"^(提醒我|帮我记得|记得|到时候提醒我)", "", content)
        content = re.sub(r"(今天|明天|后天|每周[一二三四五六日天]?|每星期[一二三四五六日天]?|每天|每日)", "", content)
        content = re.sub(r"(上午|下午|晚上|中午|凌晨|早上|傍晚)", "", content)
        content = re.sub(r"\d{1,2}[:：点时]\d{0,2}", "", content)
        content = re.sub(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?", "", content)
        content = re.sub(r"(提醒|通知|一下|一下子|一下哦|哦|呀|啊|吧)$", "", content)
        content = re.sub(r"^[，。,.、\s]+|[，。,.、\s]+$", "", content)
        return content or None


class ScheduleAgent:
    def __init__(self, repo: ScheduleRepository, parser: ScheduleParser):
        self.repo = repo
        self.parser = parser

    def handle_chat(self, text: str) -> dict[str, Any]:
        normalized = normalize_text(text)

        if self._is_delete_request(normalized):
            return self._delete_schedule(normalized)
        if self._is_update_request(normalized):
            return self._update_schedule(text)
        if self._is_list_request(normalized):
            return self._list_schedules(today_only="今天" in normalized)
        if self._is_create_request(normalized):
            return self._create_schedule(text)
        return {
            "intent": "guide",
            "answer": (
                "我可以帮您管理日程。您可以这样说：\n"
                "1. 添加日程：下午5点开会\n"
                "2. 我今天的日程有哪些？\n"
                "3. 删除日程 1\n"
                "4. 修改日程 1 为 明天下午3点提交周报"
            ),
        }

    def _is_create_request(self, text: str) -> bool:
        keywords = ("添加日程", "新增日程", "创建日程", "设置日程", "安排日程", "提醒我", "帮我记得", "日程：")
        return any(word in text for word in keywords)

    def _is_list_request(self, text: str) -> bool:
        return any(word in text for word in ("日程有哪些", "查看日程", "我的日程", "今天的日程", "全部日程", "查询日程", "今天日程"))

    def _is_delete_request(self, text: str) -> bool:
        return any(word in text for word in ("删除日程", "取消日程"))

    def _is_update_request(self, text: str) -> bool:
        return any(word in text for word in ("修改日程", "更新日程", "编辑日程"))

    def _create_schedule(self, text: str) -> dict[str, Any]:
        parsed = self.parser.parse(text)
        if parsed.missing_fields:
            return {
                "intent": "create",
                "success": False,
                "answer": f"要帮您记录日程，我还需要这些信息：{'、'.join(parsed.missing_fields)}。",
                "missing_fields": parsed.missing_fields,
            }

        schedule_id = self.repo.create_schedule(parsed.content, parsed.planned_at, parsed.repeat_rule)
        return {
            "intent": "create",
            "success": True,
            "schedule_id": schedule_id,
            "answer": f"已为您添加日程 {schedule_id}：{parsed.planned_at.strftime('%H:%M')}|{parsed.repeat_rule}|{parsed.content}",
        }

    def _list_schedules(self, today_only: bool) -> dict[str, Any]:
        items = self.repo.list_today_schedules() if today_only else self.repo.list_active_schedules()
        if not items:
            return {
                "intent": "list",
                "answer": "当前没有符合条件的日程。",
                "items": [],
            }

        lines = ["以下是您的日程："]
        for item in items:
            lines.append(f"{item['id']} | {compact_schedule_line(item)}")
        return {
            "intent": "list",
            "answer": "\n".join(lines),
            "items": [serialize_schedule(item) for item in items],
        }

    def _delete_schedule(self, text: str) -> dict[str, Any]:
        match = re.search(r"(删除日程|取消日程)\s*(\d+)", text)
        if not match:
            return {
                "intent": "delete",
                "success": False,
                "answer": "请告诉我要删除哪一条日程，例如：删除日程 1。",
            }
        schedule_id = int(match.group(2))
        deleted = self.repo.delete_schedule(schedule_id)
        if not deleted:
            return {
                "intent": "delete",
                "success": False,
                "answer": f"没有找到日程 {schedule_id}。",
            }
        return {
            "intent": "delete",
            "success": True,
            "answer": f"已经删除日程 {schedule_id}，删除的日程内容是：{deleted['time_segment']} 提醒您 {deleted['content']}",
            "item": serialize_schedule(deleted),
        }

    def _update_schedule(self, text: str) -> dict[str, Any]:
        match = re.search(r"(修改日程|更新日程|编辑日程)\s*(\d+)", text)
        if not match:
            return {
                "intent": "update",
                "success": False,
                "answer": "请先告诉我要修改哪一条日程，例如：修改日程 1 为 明天下午3点开会。",
            }
        schedule_id = int(match.group(2))
        origin = self.repo.get_schedule(schedule_id)
        if not origin or origin["status"] != "active":
            return {
                "intent": "update",
                "success": False,
                "answer": f"没有找到可修改的日程 {schedule_id}。",
            }

        changed_text = re.sub(r"^(修改日程|更新日程|编辑日程)\s*\d+\s*(为|成)?", "", text).strip()
        parsed = self.parser.parse(changed_text)
        if parsed.missing_fields:
            return {
                "intent": "update",
                "success": False,
                "answer": f"修改日程 {schedule_id} 还缺少：{'、'.join(parsed.missing_fields)}。",
                "missing_fields": parsed.missing_fields,
            }

        updated = self.repo.update_schedule(schedule_id, parsed.content, parsed.planned_at, parsed.repeat_rule)
        if not updated:
            return {
                "intent": "update",
                "success": False,
                "answer": f"日程 {schedule_id} 修改失败，请稍后重试。",
            }
        return {
            "intent": "update",
            "success": True,
            "answer": f"已修改日程 {schedule_id}：{parsed.planned_at.strftime('%H:%M')}|{parsed.repeat_rule}|{parsed.content}",
            "item": serialize_schedule(self.repo.get_schedule(schedule_id)),
        }


def serialize_schedule(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "content": item["content"],
        "time_segment": item["time_segment"],
        "repeat_rule": item["repeat_rule"],
        "repeat_text": describe_repeat_rule(item["repeat_rule"]),
        "planned_at": item["planned_at"],
        "time_label": item["time_label"],
        "status": item["status"],
    }


class ReminderWorker(threading.Thread):
    def __init__(self, repo: ScheduleRepository):
        super().__init__(daemon=True)
        self.repo = repo

    def run(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as exc:
                print(f"[ReminderWorker] 巡检失败: {exc}")
            time.sleep(10)

    def tick(self) -> None:
        now = now_local().replace(second=0, microsecond=0)
        items = self.repo.list_active_schedules()
        for item in items:
            planned_at = datetime.fromisoformat(item["planned_at"])
            should_trigger, trigger_key = self._should_trigger(item, planned_at, now)
            if not should_trigger:
                continue

            message = REMINDER_TEMPLATES[item["id"] % len(REMINDER_TEMPLATES)].format(content=item["content"])
            self.repo.add_reminder(item["id"], message, now)
            self.repo.mark_triggered(item["id"], trigger_key, now)
            print(f"[Reminder] {message}")

    def _should_trigger(self, item: dict[str, Any], planned_at: datetime, now: datetime) -> tuple[bool, str]:
        trigger_key = now.strftime("%Y-%m-%d %H:%M")
        if item["last_triggered_key"] == trigger_key:
            return False, trigger_key

        if item["repeat_rule"] == "0000000":
            if planned_at.replace(second=0, microsecond=0) == now:
                return True, trigger_key
            return False, trigger_key

        if item["repeat_rule"][now.weekday()] != "1":
            return False, trigger_key
        if planned_at.strftime("%H:%M") != now.strftime("%H:%M"):
            return False, trigger_key
        return True, trigger_key


repo = ScheduleRepository()
parser = ScheduleParser()
agent = ScheduleAgent(repo, parser)


class ScheduleAgentHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            stats = repo.stats()
            json_response(
                self,
                {
                    "ok": True,
                    "service": "日程提醒智能体",
                    "active_schedules": stats["active_schedules"],
                    "reminder_logs": stats["reminder_logs"],
                    "today": now_local().strftime("%Y-%m-%d"),
                },
            )
            return

        if parsed.path == "/api/schedules":
            json_response(self, {"items": [serialize_schedule(item) for item in repo.list_active_schedules()]})
            return

        if parsed.path == "/api/reminders":
            json_response(self, {"items": repo.list_recent_reminders()})
            return

        self.serve_static(parsed.path)

    def serve_static(self, path: str) -> None:
        if path == "/" or path == "":
            path = "/index.html"

        requested = path.lstrip("/")
        file_path = (STATIC_DIR / requested).resolve()
        static_root = STATIC_DIR.resolve()
        if not str(file_path).startswith(str(static_root)):
            json_response(self, {"error": "Forbidden"}, status=403)
            return

        if not file_path.exists() or not file_path.is_file():
            json_response(self, {"error": "Not Found"}, status=404)
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            json_response(self, {"error": "请求体不是有效的 JSON"}, status=400)
            return

        if parsed.path == "/api/chat":
            question = str(payload.get("question", "")).strip()
            if not question:
                json_response(self, {"error": "请输入日程指令"}, status=400)
                return
            result = agent.handle_chat(question)
            json_response(self, result)
            return

        if parsed.path == "/api/schedules/delete":
            schedule_id = int(payload.get("id", 0))
            result = agent.handle_chat(f"删除日程 {schedule_id}")
            json_response(self, result)
            return

        json_response(self, {"error": "Not Found"}, status=404)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    init_db()
    ReminderWorker(repo).start()
    server = ThreadingHTTPServer((API_HOST, API_PORT), ScheduleAgentHandler)
    print("日程提醒智能体启动中...")
    print(f"   API: http://localhost:{API_PORT}")
    print(f"   数据库: {DB_PATH}")
    print(f"   服务状态: 运行中")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        server.server_close()
        print("日程提醒智能体已停止。")


if __name__ == "__main__":
    main()

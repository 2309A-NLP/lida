"""
聊天记录存储模块 - 基于SQLite本地文件持久化
"""
import time
import json
import sqlite3
from pathlib import Path


class ChatHistoryStore:
    """基于 SQLite 的聊天记录存储（本地文件，轻量可靠）"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(Path(__file__).parent.parent / "data" / "chat_history.db")
        self._conn = None
        self._connected = False

    def connect(self) -> bool:
        """初始化本地 SQLite 数据库"""
        if self._connected:
            return True
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id)
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON chat_history(timestamp)
            """)
            self._conn.commit()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def save_message(self, session_id: str, role: str, content: str,
                     metadata: dict = None) -> bool:
        """保存单条消息"""
        if not self._connected:
            return False
        try:
            self._conn.execute(
                "INSERT INTO chat_history (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, time.time(),
                 json.dumps(metadata or {}, ensure_ascii=False))
            )
            self._conn.commit()
            return True
        except Exception:
            return False

    def save_conversation(self, session_id: str, messages: list[dict]) -> bool:
        """批量保存对话"""
        if not self._connected:
            return False
        try:
            ts = time.time()
            rows = []
            for i, msg in enumerate(messages):
                rows.append((
                    session_id,
                    msg["role"],
                    msg.get("content", ""),
                    ts + i * 0.001,
                    json.dumps(msg.get("metadata", {}), ensure_ascii=False),
                ))
            self._conn.executemany(
                "INSERT INTO chat_history (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                rows
            )
            self._conn.commit()
            return True
        except Exception:
            return False

    def get_history(self, session_id: str, limit: int = 50) -> list[dict]:
        """获取指定会话的历史消息"""
        if not self._connected:
            return []
        try:
            cursor = self._conn.execute(
                "SELECT role, content, timestamp, metadata FROM chat_history WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit)
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "metadata": row["metadata"],
                })
            return results
        except Exception:
            return []

    def get_all_sessions(self) -> list[str]:
        """获取所有会话ID列表"""
        if not self._connected:
            return []
        try:
            cursor = self._conn.execute(
                "SELECT DISTINCT session_id FROM chat_history ORDER BY MIN(timestamp) DESC"
            )
            return [row["session_id"] for row in cursor.fetchall()]
        except Exception:
            return []

    def get_all_sessions_with_preview(self) -> list[dict]:
        """获取所有会话预览（首条用户问题 + 时间戳 + 消息数）"""
        if not self._connected:
            return []
        try:
            cursor = self._conn.execute("""
                SELECT session_id,
                       MIN(timestamp) as first_ts,
                       MAX(timestamp) as last_ts,
                       COUNT(*) as msg_count
                FROM chat_history
                GROUP BY session_id
                ORDER BY last_ts DESC
            """)
            sessions = []
            for row in cursor.fetchall():
                sid = row["session_id"]
                # Get first user query for preview
                preview_cursor = self._conn.execute(
                    "SELECT content FROM chat_history WHERE session_id = ? AND role = 'user' ORDER BY timestamp ASC LIMIT 1",
                    (sid,)
                )
                preview_row = preview_cursor.fetchone()
                first_query = preview_row["content"][:60] if preview_row else ""

                sessions.append({
                    "session_id": sid,
                    "first_query": first_query,
                    "first_timestamp": row["first_ts"],
                    "last_timestamp": row["last_ts"],
                    "message_count": row["msg_count"],
                })
            return sessions
        except Exception:
            return []

    def delete_session(self, session_id: str) -> bool:
        """删除指定会话记录"""
        if not self._connected:
            return False
        try:
            self._conn.execute(
                "DELETE FROM chat_history WHERE session_id = ?",
                (session_id,)
            )
            self._conn.commit()
            return True
        except Exception:
            return False

    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
        self._connected = False
        self._conn = None

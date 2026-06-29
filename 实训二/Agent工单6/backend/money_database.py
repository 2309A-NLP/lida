"""
工单编号：人工智能NLP-Agent数字人项目-记账本任务
记账本数据库模块
"""
import sqlite3
import os
from datetime import datetime, date
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'money_notes.db')


class MoneyDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS money_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                member TEXT NOT NULL,
                category TEXT NOT NULL,
                item TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('收入', '支出')),
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_money_date ON money_notes(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_money_member ON money_notes(member)")
        self.conn.commit()

    def add_record(self, date_str, member, category, item, amount, type_, note=""):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO money_notes (date,member,category,item,amount,type,note) VALUES (?,?,?,?,?,?,?)",
            (date_str, member, category, item, amount, type_, note)
        )
        self.conn.commit()
        return cursor.lastrowid

    def delete_record(self, record_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM money_notes WHERE id=?", (record_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def query_by_date_range(self, start_date, end_date, member=None):
        cursor = self.conn.cursor()
        if member:
            cursor.execute(
                "SELECT * FROM money_notes WHERE date BETWEEN ? AND ? AND member=? ORDER BY date DESC",
                (start_date, end_date, member)
            )
        else:
            cursor.execute(
                "SELECT * FROM money_notes WHERE date BETWEEN ? AND ? ORDER BY date DESC",
                (start_date, end_date)
            )
        return [dict(row) for row in cursor.fetchall()]

    def query_by_item(self, item):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM money_notes WHERE item LIKE ? ORDER BY date DESC",
            (f"%{item}%",)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_summary(self, start_date=None, end_date=None, member=None):
        cursor = self.conn.cursor()
        conditions, params = [], []
        if start_date:
            conditions.append("date >= ?"); params.append(start_date)
        if end_date:
            conditions.append("date <= ?"); params.append(end_date)
        if member:
            conditions.append("member = ?"); params.append(member)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor.execute(
            f"SELECT type, SUM(amount) as total, COUNT(*) as count FROM money_notes WHERE {where} GROUP BY type",
            params
        )
        result = {"收入": 0, "支出": 0, "收入笔数": 0, "支出笔数": 0}
        for row in cursor.fetchall():
            result[row["type"]] = row["total"]
            result[f'{row["type"]}笔数'] = row["count"]
        result["净收入"] = result["收入"] - result["支出"]
        return result

    def get_member_summary(self, start_date=None, end_date=None):
        cursor = self.conn.cursor()
        conditions, params = [], []
        if start_date: conditions.append("date >= ?"); params.append(start_date)
        if end_date: conditions.append("date <= ?"); params.append(end_date)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor.execute(
            f"SELECT member, type, SUM(amount) as total, COUNT(*) as count FROM money_notes WHERE {where} GROUP BY member, type ORDER BY member, type",
            params
        )
        member_stats = {}
        for row in cursor.fetchall():
            m = row["member"]
            if m not in member_stats:
                member_stats[m] = {"收入": 0, "支出": 0, "净收入": 0}
            member_stats[m][row["type"]] = row["total"]
        for m in member_stats:
            member_stats[m]["净收入"] = member_stats[m]["收入"] - member_stats[m]["支出"]
        return member_stats

    def get_category_summary(self, start_date=None, end_date=None):
        cursor = self.conn.cursor()
        conditions, params = [], []
        if start_date: conditions.append("date >= ?"); params.append(start_date)
        if end_date: conditions.append("date <= ?"); params.append(end_date)
        where = " AND ".join(conditions) if conditions else "1=1"
        cursor.execute(
            f"SELECT category, type, SUM(amount) as total, COUNT(*) as count FROM money_notes WHERE {where} GROUP BY category, type ORDER BY total DESC",
            params
        )
        return [dict(row) for row in cursor.fetchall()]

    def clear_all_records(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM money_notes")
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM money_notes")
        self.conn.commit()
        return count


_db_instance = None

def get_money_db() -> MoneyDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = MoneyDatabase()
    return _db_instance

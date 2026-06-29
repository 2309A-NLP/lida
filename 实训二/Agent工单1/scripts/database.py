#!/usr/bin/env python3
"""
工单编号：人工智能NLP-Agent数字人项目-记账本任务
记账本Agent - 数据库模块

功能：
1. 创建数据库表结构
2. 提供增删改查操作
3. 支持按时间、成员、类别查询
"""

import sqlite3
import os
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "money_notes.db")


class MoneyDatabase:
    """记账本数据库管理类"""

    def __init__(self, db_path: str = DB_PATH):
        """初始化数据库连接"""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 返回字典格式
        self._create_tables()

    def _create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()

        # 创建账目表
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

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON money_notes(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_member ON money_notes(member)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON money_notes(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON money_notes(type)")

        self.conn.commit()
        print(f"数据库初始化完成: {self.db_path}")

    def add_record(self, date_str: str, member: str, category: str, item: str, amount: float, type_: str, note: str = "") -> int:
        """
        添加账目记录

        Args:
            date_str: 日期（YYYY-MM-DD格式）
            member: 成员（爸爸/妈妈/女儿）
            category: 类别（买书/吃饭/交通等）
            item: 具体项目
            amount: 金额（正数）
            type_: 类型（收入/支出）
            note: 备注

        Returns:
            新记录的ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO money_notes (date, member, category, item, amount, type, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date_str, member, category, item, amount, type_, note))
        self.conn.commit()
        return cursor.lastrowid

    def delete_record(self, record_id: int) -> bool:
        """
        删除账目记录

        Args:
            record_id: 记录ID

        Returns:
            是否删除成功
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM money_notes WHERE id = ?", (record_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def update_record(self, record_id: int, **kwargs) -> bool:
        """
        更新账目记录

        Args:
            record_id: 记录ID
            **kwargs: 要更新的字段

        Returns:
            是否更新成功
        """
        if not kwargs:
            return False

        # 构建UPDATE语句
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(record_id)

        cursor = self.conn.cursor()
        cursor.execute(f"""
            UPDATE money_notes
            SET {set_clause}, updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, values)
        self.conn.commit()
        return cursor.rowcount > 0

    def query_by_date_range(self, start_date: str, end_date: str, member: str = None) -> List[Dict]:
        """
        按日期范围查询

        Args:
            start_date: 开始日期
            end_date: 结束日期
            member: 成员（可选）

        Returns:
            记录列表
        """
        cursor = self.conn.cursor()
        if member:
            cursor.execute("""
                SELECT * FROM money_notes
                WHERE date BETWEEN ? AND ? AND member = ?
                ORDER BY date DESC
            """, (start_date, end_date, member))
        else:
            cursor.execute("""
                SELECT * FROM money_notes
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
            """, (start_date, end_date))
        return [dict(row) for row in cursor.fetchall()]

    def query_by_member(self, member: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        按成员查询

        Args:
            member: 成员名称
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            记录列表
        """
        cursor = self.conn.cursor()
        if start_date and end_date:
            cursor.execute("""
                SELECT * FROM money_notes
                WHERE member = ? AND date BETWEEN ? AND ?
                ORDER BY date DESC
            """, (member, start_date, end_date))
        else:
            cursor.execute("""
                SELECT * FROM money_notes
                WHERE member = ?
                ORDER BY date DESC
            """, (member,))
        return [dict(row) for row in cursor.fetchall()]

    def query_by_category(self, category: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        按类别查询

        Args:
            category: 类别名称
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            记录列表
        """
        cursor = self.conn.cursor()
        if start_date and end_date:
            cursor.execute("""
                SELECT * FROM money_notes
                WHERE category = ? AND date BETWEEN ? AND ?
                ORDER BY date DESC
            """, (category, start_date, end_date))
        else:
            cursor.execute("""
                SELECT * FROM money_notes
                WHERE category = ?
                ORDER BY date DESC
            """, (category,))
        return [dict(row) for row in cursor.fetchall()]

    def query_by_item(self, item: str) -> List[Dict]:
        """
        按项目名称查询

        Args:
            item: 项目名称（支持模糊匹配）

        Returns:
            记录列表
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM money_notes
            WHERE item LIKE ?
            ORDER BY date DESC
        """, (f"%{item}%",))
        return [dict(row) for row in cursor.fetchall()]

    def get_summary(self, start_date: str = None, end_date: str = None, member: str = None) -> Dict:
        """
        获取汇总统计

        Args:
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            member: 成员（可选）

        Returns:
            汇总数据
        """
        cursor = self.conn.cursor()

        # 构建查询条件
        conditions = []
        params = []

        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)
        if member:
            conditions.append("member = ?")
            params.append(member)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 查询总收入和总支出
        cursor.execute(f"""
            SELECT
                type,
                SUM(amount) as total,
                COUNT(*) as count
            FROM money_notes
            WHERE {where_clause}
            GROUP BY type
        """, params)

        result = {"收入": 0, "支出": 0, "收入笔数": 0, "支出笔数": 0}
        for row in cursor.fetchall():
            if row["type"] == "收入":
                result["收入"] = row["total"]
                result["收入笔数"] = row["count"]
            else:
                result["支出"] = row["total"]
                result["支出笔数"] = row["count"]

        result["净收入"] = result["收入"] - result["支出"]
        return result

    def get_member_summary(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        获取各成员汇总

        Args:
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            各成员汇总数据
        """
        cursor = self.conn.cursor()

        conditions = []
        params = []

        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT
                member,
                type,
                SUM(amount) as total,
                COUNT(*) as count
            FROM money_notes
            WHERE {where_clause}
            GROUP BY member, type
            ORDER BY member, type
        """, params)

        # 整理结果
        member_stats = {}
        for row in cursor.fetchall():
            member = row["member"]
            if member not in member_stats:
                member_stats[member] = {"收入": 0, "支出": 0, "净收入": 0}
            member_stats[member][row["type"]] = row["total"]

        # 计算净收入
        for member in member_stats:
            member_stats[member]["净收入"] = member_stats[member]["收入"] - member_stats[member]["支出"]

        return member_stats

    def get_category_summary(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        获取各类别汇总

        Args:
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            各类别汇总数据
        """
        cursor = self.conn.cursor()

        conditions = []
        params = []

        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT
                category,
                type,
                SUM(amount) as total,
                COUNT(*) as count
            FROM money_notes
            WHERE {where_clause}
            GROUP BY category, type
            ORDER BY total DESC
        """, params)

        return [dict(row) for row in cursor.fetchall()]

    def clear_all_records(self) -> int:
        """
        清空所有账目记录

        Returns:
            删除的记录数
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM money_notes")
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM money_notes")
        self.conn.commit()
        return count

    def close(self):
        """关闭数据库连接"""
        self.conn.close()


# 全局数据库实例
_db_instance = None


def get_db() -> MoneyDatabase:
    """获取数据库单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = MoneyDatabase()
    return _db_instance


if __name__ == "__main__":
    # 测试数据库操作
    db = MoneyDatabase()

    # 添加测试数据
    db.add_record("2025-01-14", "女儿", "买书", "三体", 50, "支出")
    db.add_record("2025-01-14", "妈妈", "工资", "工资", 10000, "收入")
    db.add_record("2025-01-15", "爸爸", "吃饭", "午餐", 30, "支出")

    # 查询
    records = db.query_by_date_range("2025-01-01", "2025-01-31")
    print(f"查询到 {len(records)} 条记录")

    # 汇总
    summary = db.get_summary()
    print(f"汇总: {summary}")

    db.close()
    print("数据库测试完成")

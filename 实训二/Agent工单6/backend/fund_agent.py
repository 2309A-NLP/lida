"""
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
基金数据NL2SQL问答服务（关键词规则版，不依赖LLM）
"""
import re
import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional

# 数据库路径
FUND_DB_PATHS = [
    Path("D:/Agent工单/Agent工单4/dataset_partial/_____temp/dataset/博金杯比赛数据.db"),
    Path("D:/Agent工单/Agent工单5/dataset_raw/financial_data.db"),
]


def _find_fund_db() -> Optional[Path]:
    for p in FUND_DB_PATHS:
        if p.exists():
            return p
    return None


def _get_tables(db_path: Path) -> List[str]:
    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def _safe_query(db_path: Path, sql: str, max_rows: int = 20) -> Dict:
    try:
        sql_upper = sql.upper().strip()
        if any(kw in sql_upper for kw in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE"]):
            return {"success": False, "error": "只允许查询操作", "rows": []}
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = [dict(r) for r in cursor.fetchmany(max_rows)]
        conn.close()
        return {"success": True, "rows": rows, "count": len(rows)}
    except Exception as e:
        return {"success": False, "error": str(e), "rows": []}


def process_fund_question(question: str) -> Dict:
    """处理基金数据查询问题"""
    db_path = _find_fund_db()

    if not db_path:
        return {
            "answer": "基金数据库文件未找到。系统支持查询基金基本信息、股票持仓、债券持仓、日行情等数据。请确认数据库文件已正确配置。",
            "success": False,
            "tables": [],
        }

    tables = _get_tables(db_path)

    # 查询数据库有哪些表
    if any(kw in question for kw in ["有哪些表", "哪些表", "表结构", "数据库结构", "有什么表", "表名"]):
        table_info = "\n".join([f"• {t}" for t in tables])
        return {
            "answer": f"基金数据库共有 {len(tables)} 个数据表：\n{table_info}",
            "success": True,
            "tables": tables
        }

    # 基金基本信息查询
    if any(kw in question for kw in ["基金基本", "基金信息", "管理人", "成立日期", "基金类型", "基金简称", "基金代码"]):
        fund_tables = [t for t in tables if "基本" in t or "basic" in t.lower()]
        if fund_tables:
            result = _safe_query(db_path, f'SELECT * FROM "{fund_tables[0]}" LIMIT 5')
            if result["success"] and result["rows"]:
                return {
                    "answer": f"基金基本信息（前5条）：\n" + _format_rows(result["rows"]),
                    "success": True,
                    "sql": f'SELECT * FROM "{fund_tables[0]}" LIMIT 5',
                    "rows": result["rows"]
                }

    # 股票持仓查询
    if any(kw in question for kw in ["股票持仓", "持仓股票", "重仓股", "持股", "股票明细"]):
        stock_tables = [t for t in tables if "股票" in t and "持仓" in t]
        if stock_tables:
            result = _safe_query(db_path, f'SELECT * FROM "{stock_tables[0]}" LIMIT 5')
            if result["success"] and result["rows"]:
                return {
                    "answer": f"股票持仓明细（前5条）：\n" + _format_rows(result["rows"]),
                    "success": True,
                    "rows": result["rows"]
                }

    # 债券持仓查询
    if any(kw in question for kw in ["债券持仓", "持仓债券", "债券明细", "债券"]):
        bond_tables = [t for t in tables if "债券" in t and "持仓" in t]
        if bond_tables:
            result = _safe_query(db_path, f'SELECT * FROM "{bond_tables[0]}" LIMIT 5')
            if result["success"] and result["rows"]:
                return {
                    "answer": f"债券持仓明细（前5条）：\n" + _format_rows(result["rows"]),
                    "success": True,
                    "rows": result["rows"]
                }

    # 日行情查询
    if any(kw in question for kw in ["日行情", "净值", "行情", "涨跌", "收益"]):
        daily_tables = [t for t in tables if "日行情" in t or "daily" in t.lower()]
        if daily_tables:
            result = _safe_query(db_path, f'SELECT * FROM "{daily_tables[0]}" LIMIT 5')
            if result["success"] and result["rows"]:
                return {
                    "answer": f"基金日行情数据（前5条）：\n" + _format_rows(result["rows"]),
                    "success": True,
                    "rows": result["rows"]
                }

    # 股票行情查询
    if any(kw in question for kw in ["股票行情", "A股", "港股", "股价", "涨幅", "跌幅", "涨跌幅"]):
        stock_daily = [t for t in tables if "股票" in t and "行情" in t]
        if stock_daily:
            result = _safe_query(db_path, f'SELECT * FROM "{stock_daily[0]}" LIMIT 5')
            if result["success"] and result["rows"]:
                return {
                    "answer": f"股票行情数据（前5条）：\n" + _format_rows(result["rows"]),
                    "success": True,
                    "rows": result["rows"]
                }

    # 基金规模查询
    if any(kw in question for kw in ["规模", "份额", "持有人", "机构", "个人"]):
        scale_tables = [t for t in tables if "规模" in t or "份额" in t or "持有人" in t]
        if scale_tables:
            result = _safe_query(db_path, f'SELECT * FROM "{scale_tables[0]}" LIMIT 5')
            if result["success"] and result["rows"]:
                return {
                    "answer": f"基金规模/份额数据（前5条）：\n" + _format_rows(result["rows"]),
                    "success": True,
                    "rows": result["rows"]
                }

    # 通用返回：数据库结构信息
    table_info = "\n".join([f"• {t}" for t in tables[:10]])
    return {
        "answer": (f"基金数据库包含以下 {len(tables)} 个数据表：\n{table_info}\n\n"
                   f"您可以查询：\n"
                   f"• 基金基本信息（基金代码、名称、管理人等）\n"
                   f"• 股票持仓明细（基金重仓股）\n"
                   f"• 债券持仓明细\n"
                   f"• 基金日行情（净值、涨跌）\n"
                   f"• 基金规模变动\n"
                   f"• A股/港股行情数据\n\n"
                   f"请提供更具体的查询条件，例如：「查询股票持仓明细」"),
        "success": True,
        "tables": tables,
        "db_available": True
    }


def get_fund_db_schema() -> Dict:
    """获取基金数据库表结构"""
    db_path = _find_fund_db()
    if not db_path:
        return {"available": False, "tables": []}

    tables = _get_tables(db_path)
    schema = []
    try:
        conn = sqlite3.connect(str(db_path))
        for table in tables[:10]:
            try:
                cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                schema.append({
                    "name": table,
                    "columns": [{"name": c[1], "type": c[2]} for c in cols],
                    "row_count": count
                })
            except Exception:
                pass
        conn.close()
    except Exception:
        pass

    return {"available": True, "tables": schema, "db_path": str(db_path)}


def _format_rows(rows: List[Dict]) -> str:
    if not rows:
        return "无数据"
    lines = []
    for i, row in enumerate(rows[:5], 1):
        items = [f"{k}:{v}" for k, v in list(row.items())[:5]]
        lines.append(f"{i}. " + " | ".join(items))
    return "\n".join(lines)

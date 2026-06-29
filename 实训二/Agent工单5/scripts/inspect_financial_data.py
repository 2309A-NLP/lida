"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def print_table_info(conn: sqlite3.Connection, table_name: str) -> None:
    columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    print(f"[TABLE] {table_name}")
    for column in columns:
        print(column)
    sample = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 3').fetchall()
    print("[SAMPLE]")
    for row in sample:
        print(row)
    print()


def inspect_questions() -> None:
    path = Path("dataset_raw/question.json")
    lines = path.read_text(encoding="utf-8").splitlines()
    print(f"[QUESTIONS] lines={len(lines)}")
    for line in lines[:5]:
        row = json.loads(line)
        print(row)
    print()


def main() -> None:
    inspect_questions()
    conn = sqlite3.connect("dataset_raw/financial_data.db")
    tables = conn.execute(
        "select name from sqlite_master where type='table' order by name"
    ).fetchall()
    print("[TABLES]")
    for table in tables:
        print(table[0])
    print()

    for table_name in [
        "A股票日行情表",
        "A股公司行业划分表",
        "基金基本信息",
        "基金股票持仓明细",
        "基金可转债持仓明细",
        "基金规模变动表",
        "基金份额持有人结构",
        "基金日行情表",
    ]:
        print_table_info(conn, table_name)


if __name__ == "__main__":
    main()

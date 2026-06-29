"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import sqlite3


def print_rows(title: str, rows: list[tuple]) -> None:
    print(f"[{title}]")
    for row in rows:
        print(row)
    print()


def main() -> None:
    conn = sqlite3.connect("dataset_raw/financial_data.db")

    for table in [
        "基金股票持仓明细",
        "基金可转债持仓明细",
        "基金债券持仓明细",
        "基金规模变动表",
        "基金份额持有人结构",
    ]:
        rows = conn.execute(
            f'SELECT DISTINCT "报告类型" FROM "{table}" ORDER BY 1'
        ).fetchall()
        print_rows(f"{table}-报告类型", rows)

    rows = conn.execute(
        'SELECT DISTINCT "一级行业名称" FROM "A股公司行业划分表" '
        'WHERE "行业划分标准"="中信行业分类" ORDER BY 1'
    ).fetchall()
    print_rows("中信一级行业", rows)

    rows = conn.execute(
        'SELECT DISTINCT "一级行业名称" FROM "A股公司行业划分表" '
        'WHERE "行业划分标准"="申万行业分类" ORDER BY 1'
    ).fetchall()
    print_rows("申万一级行业", rows)

    rows = conn.execute(
        'SELECT DISTINCT "基金类型" FROM "基金基本信息" ORDER BY 1'
    ).fetchall()
    print_rows("基金类型", rows)


if __name__ == "__main__":
    main()

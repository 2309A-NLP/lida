"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prospectus_qa.config import FINANCIAL_DB_PATH
from prospectus_qa.financial_answering import FinancialDatabaseAnswerer
from prospectus_qa.financial_routing import detect_financial_question


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--show-covered", action="store_true")
    args = parser.parse_args()

    answerer = FinancialDatabaseAnswerer(FINANCIAL_DB_PATH)
    rows = [
        json.loads(line)
        for line in Path("dataset_raw/question.json").open(encoding="utf-8")
        if line.strip()
    ]
    rows = rows[args.start :]
    if args.limit is not None:
        rows = rows[: args.limit]

    covered = 0
    uncovered: list[dict[str, object]] = []
    pattern_counter: Counter[str] = Counter()

    for row in rows:
        question = row["question"]
        if not detect_financial_question(question):
            continue
        t0 = time.perf_counter()
        result = answerer.answer(question)
        elapsed = time.perf_counter() - t0
        if result is not None:
            covered += 1
            if args.show_covered:
                print(f'COVERED\t{row["id"]}\t{elapsed:.3f}\t{guess_pattern(question)}\t{question}', flush=True)
            continue
        uncovered.append(row)
        pattern_counter[guess_pattern(question)] += 1
        print(f'UNCOVERED\t{row["id"]}\t{elapsed:.3f}\t{guess_pattern(question)}\t{question}', flush=True)

    print(f"financial_total={covered + len(uncovered)}")
    print(f"financial_covered={covered}")
    print(f"financial_uncovered={len(uncovered)}")
    print("pattern_counts:")
    for name, count in pattern_counter.most_common():
        print(f"{name}: {count}")
    print("samples:")
    for row in uncovered[:120]:
        print(f'{row["id"]}\t{row["question"]}')


def guess_pattern(question: str) -> str:
    checks = [
        ("market_count_top10", "所在证券市场是"),
        ("bond_count_top10", "且是前10大重仓股的基金有几个"),
        ("top_n_code_name", "大重仓股的代码和股票名称"),
        ("top_n_code", "大重仓股的代码是什么"),
        ("manager_nav", "管理人和累计单位净值"),
        ("fee_rate", "管理费率是"),
        ("custodian_rate", "托管费率是"),
        ("custodian", "托管人是"),
        ("fund_type", "基金类型是"),
        ("bond_type_max", "持有最大仓位的债券类型"),
        ("bond_names_top3", "前三大持仓占比的债券名称"),
        ("convertible_industry", "可转债持仓占比最大"),
        ("top10_positive", "前10大重仓股中"),
        ("avg_mv_top20", "前20大重仓股票"),
        ("report_diff_max", "差额最大"),
        ("hk_amplitude", "港股日价格振幅"),
        ("top7_top10_count", "在多少只基金的前"),
        ("industry_level_lookup", "属于哪个一级行业"),
        ("stock_max_change", "涨跌幅最大股票"),
        ("industry_rise_count", "涨幅超过5%"),
        ("industry_amount_avg", "平均成交金额"),
        ("industry_amount_max", "成交金额(元)最多"),
    ]
    for name, needle in checks:
        if needle in question:
            return name
    return "other"


if __name__ == "__main__":
    main()

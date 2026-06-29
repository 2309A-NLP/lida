"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


DB_HINTS = [
    "基金",
    "股票",
    "A股",
    "港股",
    "行业",
    "净值",
    "申购",
    "赎回",
    "重仓股",
    "可转债",
    "持有份额",
    "持有人",
    "成交量",
    "成交金额",
]

PATTERNS: list[tuple[str, list[str]]] = [
    ("stock_max_change", ["涨跌幅最大股票"]),
    ("rise_count", ["涨幅超过5%"]),
    ("limit_up", ["涨停天数"]),
    ("industry_volume_sum", ["成交量合计"]),
    ("industry_amount_sum", ["成交金额合计"]),
    ("industry_amount_max", ["成交金额最多"]),
    ("close_price", ["收盘价是多少"]),
    ("manager_fund_count", ["成立了多少基金"]),
    ("manager_product_count", ["管理的债券型产品的数量有多少", "管理的股票型产品的数量有多少"]),
    ("net_redeem_summary", ["净赎回"]),
    ("net_subscribe_summary", ["净申购"]),
    ("fund_nav", ["资产净值和单位净值"]),
    ("convertible_max_industry", ["可转债持仓占比最大"]),
    ("holder_inst_more_count", ["机构投资者持有份额比个人投资者多"]),
    ("holder_personal_more_type_count", ["个人投资者持有基金份额大于机构投资者持有基金份额的基金属于"]),
    ("holder_personal_more_ratio", ["个人投资者持有的份额超过机构投资者"]),
    ("heavy_holding_count", ["市值占基金资产净值比不小于5%"]),
    ("scale_growth_count", ["报告期期初基金总份额小于报告期期末基金总份额"]),
    ("fee_avg", ["管理费率的平均值", "托管费率的平均数"]),
    ("quarter_topn_return", ["第3大重股", "第6大重股"]),
    ("fund_top_holding_code", ["第1大重仓股的代码"]),
    ("stock_topn_holding_count", ["前七大重仓股"]),
    ("open_gt_prev_close_days", ["今开盘高于昨收盘的天数"]),
    ("low_volume_days", ["日成交量低于该股票当年平均日成交量"]),
    ("latest_industry_level2", ["申万行业分类下的二级行业是什么"]),
    ("redeem_zero_count", ["基金总赎回份额为零"]),
    ("inst_ratio_over", ["机构投资者持有的份额占比超过"]),
    ("top3_amount_codes", ["成交金额最大的前三家上市公司"]),
    ("highest_close_price", ["最高日收盘价"]),
    ("annualized_return", ["年化收益率"]),
    ("bond_type_max", ["持有最大仓位的债券类型"]),
    ("manager_bond_cd_count", ["持有过同业存单"]),
    ("hk_market_count", ["中国香港证券交易所"]),
    ("industry_amount_avg", ["平均成交金额"]),
    ("industry_company_count", ["行业的A股公司有多少"]),
    ("industry_company_most", ["A股公司数量最多"]),
    ("daily_return_best", ["日均收益率最高"]),
    ("industry_volatility_max", ["收盘价波动最大"]),
    ("fund_fee_rate", ["它的管理费率是"]),
    ("fund_top3_bond_names", ["前三大持仓占比的债券名称"]),
    ("bond_market_value_type_max", ["哪类债券市值最高"]),
    ("manager_type_most", ["成立哪种类型的基金个数最多"]),
    ("fund_scale_down_count", ["基金总份额降低"]),
    ("report_diff_max_fund", ["差额最大的那只基金"]),
    ("open_gt_prev_high_count", ["开盘价较上一交易日最高价高"]),
    ("hk_down_count", ["港股下跌的股票家数"]),
]


def is_db_question(question: str) -> bool:
    return any(hint in question for hint in DB_HINTS)


def main() -> None:
    questions = [
        json.loads(line)["question"]
        for line in Path("dataset_raw/question.json").open(encoding="utf-8")
        if line.strip()
    ]
    db_questions = [question for question in questions if is_db_question(question)]
    print(f"db_questions={len(db_questions)}")

    counter: Counter[str] = Counter()
    matched_map: defaultdict[str, list[str]] = defaultdict(list)
    unmatched: list[str] = []

    for question in db_questions:
        matched = False
        for name, needles in PATTERNS:
            if any(needle in question for needle in needles):
                counter[name] += 1
                matched_map[name].append(question)
                matched = True
        if not matched:
            unmatched.append(question)

    print("matched_counts:")
    for name, count in counter.most_common():
        print(f"{name}: {count}")

    print(f"\nunmatched={len(unmatched)}")
    for question in unmatched[:120]:
        print(question)
        print("---")


if __name__ == "__main__":
    main()

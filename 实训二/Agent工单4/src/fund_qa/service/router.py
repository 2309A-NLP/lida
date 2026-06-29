"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

import re


SQL_KEYWORDS = [
    "基金",
    "股票",
    "债券",
    "可转债",
    "持仓",
    "净值",
    "涨跌幅",
    "成交量",
    "成交金额",
    "行业",
    "份额",
    "规模",
    "涨停",
    "季报",
    "年报",
    "半年报",
    "周转率",
    "专利",
    "平均市值",
    "平均成交金额",
    "正收益",
    "比例",
]

TEXT_KEYWORDS = [
    "招股",
    "公司",
    "发起人",
    "部门",
    "风险",
    "产品",
    "优势",
    "利润率",
    "控股股东",
    "募投",
    "募集资金",
    "研发",
    "存货",
]


def route_question(question: str) -> str:
    if "招股" in question or "招股说明书" in question or "招股意向书" in question:
        return "prospectus"
    score_sql = sum(1 for item in SQL_KEYWORDS if item in question)
    score_text = sum(1 for item in TEXT_KEYWORDS if item in question)
    if re.search(r"\b\d{6}\b", question) or re.search(r"\b20\d{6}\b", question):
        score_sql += 1
    if "有限公司" in question and score_sql == 0:
        score_text += 1
    return "prospectus" if score_text > score_sql else "sql"

"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import re

from .financial_schema import ALL_FINANCIAL_TABLES

STOCK_HINTS = [
    "股票",
    "收盘价",
    "涨停",
    "成交量",
    "成交金额",
    "中信行业",
    "申万行业",
    "行业分类",
    "一级行业",
    "二级行业",
    "昨收盘",
    "今开盘",
]

FUND_HINTS = [
    "基金",
    "净赎回",
    "净申购",
    "资产净值",
    "单位净值",
    "持有人",
    "基金份额",
    "基金经理",
    "年报",
    "半年报",
    "季报",
    "重仓股",
    "债券持仓",
    "可转债",
]


def detect_financial_question(question: str) -> bool:
    return any(hint in question for hint in STOCK_HINTS + FUND_HINTS)


def suggested_tables(question: str) -> list[str]:
    tables: list[str] = []
    if any(hint in question for hint in ["基金简称", "管理人", "基金类型", "成立了多少基金", "成立日期"]):
        tables.append("基金基本信息")
    if any(hint in question for hint in ["资产净值", "单位净值", "累计单位净值"]):
        tables.extend(["基金日行情表", "基金基本信息"])
    if any(hint in question for hint in ["净赎回", "净申购", "总申购", "总赎回", "规模变动"]):
        tables.append("基金规模变动表")
    if any(hint in question for hint in ["机构投资者", "个人投资者", "持有人结构", "份额占比"]):
        tables.append("基金份额持有人结构")
    if any(hint in question for hint in ["重仓股", "股票名称", "市值占基金资产净值比"]):
        tables.append("基金股票持仓明细")
    if any(hint in question for hint in ["债券持仓", "债券类型", "债券名称"]):
        tables.append("基金债券持仓明细")
    if any(hint in question for hint in ["可转债", "对应股票代码"]):
        tables.append("基金可转债持仓明细")
    if any(hint in question for hint in ["收盘价", "涨停", "成交量", "成交金额", "最高价", "最低价", "昨收盘", "今开盘"]):
        tables.append("A股票日行情表")
    if "港股" in question:
        tables.append("港股票日行情表")
    if any(hint in question for hint in ["中信行业", "申万行业", "行业分类", "一级行业", "二级行业"]):
        tables.append("A股公司行业划分表")
    if not tables:
        return ALL_FINANCIAL_TABLES
    return list(dict.fromkeys(tables))


def extract_dates(question: str) -> list[str]:
    return re.findall(r"(20\d{6}|20\d{2}年\d{1,2}月\d{1,2}日|20\d{2}年\d{1,2}月|20\d{4})", question)


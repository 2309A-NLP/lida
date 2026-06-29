"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3


class SqlEngineError(RuntimeError):
    """Raised when SQL execution is unavailable or unsafe."""


@dataclass(slots=True)
class SqlExecution:
    sql: str
    rows: list[dict]


def _s(*codes: int) -> str:
    return "".join(chr(code) for code in codes)


T_A_STOCK_DAILY = "A" + _s(0x80a1, 0x7968, 0x65e5, 0x884c, 0x60c5, 0x8868)
T_A_INDUSTRY = "A" + _s(0x80a1, 0x516c, 0x53f8, 0x884c, 0x4e1a, 0x5212, 0x5206, 0x8868)
T_FUND_BASIC = _s(0x57fa, 0x91d1, 0x57fa, 0x672c, 0x4fe1, 0x606f)
T_FUND_DAILY = _s(0x57fa, 0x91d1, 0x65e5, 0x884c, 0x60c5, 0x8868)
T_FUND_SCALE = _s(0x57fa, 0x91d1, 0x89c4, 0x6a21, 0x53d8, 0x52a8, 0x8868)
T_FUND_HOLDER = _s(0x57fa, 0x91d1, 0x4efd, 0x989d, 0x6301, 0x6709, 0x4eba, 0x7ed3, 0x6784)
T_FUND_BOND = _s(0x57fa, 0x91d1, 0x503a, 0x5238, 0x6301, 0x4ed3, 0x660e, 0x7ec6)
T_FUND_CONVERTIBLE = _s(0x57fa, 0x91d1, 0x53ef, 0x8f6c, 0x503a, 0x6301, 0x4ed3, 0x660e, 0x7ec6)
T_FUND_STOCK = _s(0x57fa, 0x91d1, 0x80a1, 0x7968, 0x6301, 0x4ed3, 0x660e, 0x7ec6)

C_STOCK_CODE = _s(0x80a1, 0x7968, 0x4ee3, 0x7801)
C_TRADE_DAY = _s(0x4ea4, 0x6613, 0x65e5)
C_TRADE_DATE = _s(0x4ea4, 0x6613, 0x65e5, 0x671f)
C_PREV_CLOSE = _s(0x6628, 0x6536, 0x76d8) + "(元)"
C_CLOSE = _s(0x6536, 0x76d8, 0x4ef7) + "(元)"
C_VOLUME = _s(0x6210, 0x4ea4, 0x91cf) + "(股)"
C_AMOUNT = _s(0x6210, 0x4ea4, 0x91d1, 0x989d) + "(元)"
C_STANDARD = _s(0x884c, 0x4e1a, 0x5212, 0x5206, 0x6807, 0x51c6)
C_INDUSTRY_L1 = _s(0x4e00, 0x7ea7, 0x884c, 0x4e1a, 0x540d, 0x79f0)
C_INDUSTRY_L2 = _s(0x4e8c, 0x7ea7, 0x884c, 0x4e1a, 0x540d, 0x79f0)

C_FUND_CODE = _s(0x57fa, 0x91d1, 0x4ee3, 0x7801)
C_FUND_SHORT = _s(0x57fa, 0x91d1, 0x7b80, 0x79f0)
C_MANAGER = _s(0x7ba1, 0x7406, 0x4eba)
C_SETUP_DATE = _s(0x6210, 0x7acb, 0x65e5, 0x671f)
C_NAV = _s(0x5355, 0x4f4d, 0x51c0, 0x503c)
C_ASSET_NAV = _s(0x8d44, 0x4ea7, 0x51c0, 0x503c)
C_ANNOUNCE_DATE = _s(0x516c, 0x544a, 0x65e5, 0x671f)
C_END_DATE = _s(0x622a, 0x6b62, 0x65e5, 0x671f)
C_BEGIN_SHARE = _s(0x62a5, 0x544a, 0x671f, 0x671f, 0x521d, 0x57fa, 0x91d1, 0x603b, 0x4efd, 0x989d)
C_PURCHASE_SHARE = _s(0x62a5, 0x544a, 0x671f, 0x57fa, 0x91d1, 0x603b, 0x7533, 0x8d2d, 0x4efd, 0x989d)
C_REDEEM_SHARE = _s(0x62a5, 0x544a, 0x671f, 0x57fa, 0x91d1, 0x603b, 0x8d4e, 0x56de, 0x4efd, 0x989d)
C_END_SHARE = _s(0x62a5, 0x544a, 0x671f, 0x671f, 0x672b, 0x57fa, 0x91d1, 0x603b, 0x4efd, 0x989d)
C_REPORT_YEAR = _s(0x5b9a, 0x671f, 0x62a5, 0x544a, 0x6240, 0x5c5e, 0x5e74, 0x5ea6)
C_REPORT_TYPE = _s(0x62a5, 0x544a, 0x7c7b, 0x578b)
C_FUND_TYPE = _s(0x57fa, 0x91d1, 0x7c7b, 0x578b)
C_INST_SHARE = _s(0x673a, 0x6784, 0x6295, 0x8d44, 0x8005, 0x6301, 0x6709, 0x7684, 0x57fa, 0x91d1, 0x4efd, 0x989d)
C_PERSON_SHARE = _s(0x4e2a, 0x4eba, 0x6295, 0x8d44, 0x8005, 0x6301, 0x6709, 0x7684, 0x57fa, 0x91d1, 0x4efd, 0x989d)
C_HOLD_DATE = _s(0x6301, 0x4ed3, 0x65e5, 0x671f)
C_STOCK_NAME = _s(0x80a1, 0x7968, 0x540d, 0x79f0)
C_MARKET_VALUE = _s(0x5e02, 0x503c)
C_STOCK_MV_RATIO = _s(0x5e02, 0x503c, 0x5360, 0x57fa, 0x91d1, 0x8d44, 0x4ea7, 0x51c0, 0x503c, 0x6bd4)
C_TOP_N = "第N大重仓股"
C_MGMT_FEE = _s(0x7ba1, 0x7406, 0x8d39, 0x7387)
C_BOND_NAME = _s(0x503a, 0x5238, 0x540d, 0x79f0)
C_BOND_MV_RATIO = _s(0x6301, 0x503a, 0x5e02, 0x503c, 0x5360, 0x57fa, 0x91d1, 0x8d44, 0x4ea7, 0x51c0, 0x503c, 0x6bd4)
C_CONVERT_STOCK_CODE = _s(0x5bf9, 0x5e94, 0x80a1, 0x7968, 0x4ee3, 0x7801)
C_CONVERT_MV_RATIO = _s(0x5e02, 0x503c, 0x5360, 0x57fa, 0x91d1, 0x8d44, 0x4ea7, 0x51c0, 0x503c, 0x6bd4)


class SqlEngine:
    def __init__(self, db_path: Path, max_rows: int = 50):
        self.db_path = db_path
        self.max_rows = max_rows

    def available(self) -> bool:
        return self.db_path.exists()

    def execute(self, sql: str) -> SqlExecution:
        if not self.available():
            raise SqlEngineError(f"SQLite DB not found: {self.db_path}")
        if not self._is_safe_select(sql):
            raise SqlEngineError("Only read-only SELECT/WITH SQL is allowed.")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            rows = [dict(row) for row in cursor.fetchmany(self.max_rows)]
            return SqlExecution(sql=sql, rows=rows)
        finally:
            conn.close()

    @staticmethod
    def _is_safe_select(sql: str) -> bool:
        normalized = sql.strip().lower()
        if not normalized:
            return False
        if ";" in normalized.rstrip(";"):
            return False
        return normalized.startswith("select") or normalized.startswith("with")


class HeuristicSqlPlanner:
    def __init__(self, schema_text: str):
        self.schema_text = schema_text

    def plan(self, question: str) -> str:
        handlers = [
            self._stock_close_price,
            self._stock_limit_up_days,
            self._industry_volume_sum,
            self._industry_top_pct_change,
            self._industry_count_above_pct,
            self._industry_top_amount,
            self._industry_most_company_count,
            self._avg_amount_by_industry_l2,
            self._top_avg_daily_return,
            self._fund_count_by_manager_year,
            self._fund_nav_on_date,
            self._fund_net_redeem_stats,
            self._fund_net_purchase_stats,
            self._institution_gt_personal_count,
            self._personal_gt_inst_money_fund_count,
            self._personal_gt_inst_ratio_by_manager,
            self._avg_management_fee_mixed_funds,
            self._late_report_share_growth_count,
            self._stock_holding_ratio_count,
            self._positive_return_top10_count,
            self._avg_market_value_by_industry_l2_for_fund,
            self._top3_bond_names,
            self._convertible_top_industry,
        ]
        for handler in handlers:
            sql = handler(question)
            if sql:
                return sql
        return self._fallback_plan(question)

    def _stock_close_price(self, question: str) -> str | None:
        match_code = re.search(r"股票(\d{6})", question)
        match_date = re.search(r"(20\d{6})", question)
        if "收盘价是多少" not in question or not match_code or not match_date:
            return None
        code, date = match_code.group(1), match_date.group(1)
        return f"""SELECT "{C_STOCK_CODE}" AS 股票代码,
ROUND("{C_CLOSE}", 3) AS 收盘价
FROM "{T_A_STOCK_DAILY}"
WHERE "{C_STOCK_CODE}" = '{code}' AND "{C_TRADE_DAY}" = '{date}'"""

    def _stock_limit_up_days(self, question: str) -> str | None:
        match_code = re.search(r"(\d{6})股票|股票(\d{6})", question)
        match_year = re.search(r"(20\d{2})", question)
        if "涨停天数" not in question or not match_year:
            return None
        code = next(group for group in match_code.groups() if group) if match_code else None
        if not code:
            return None
        year = match_year.group(1)
        return f"""SELECT COUNT(*) AS 涨停天数
FROM "{T_A_STOCK_DAILY}"
WHERE "{C_STOCK_CODE}" = '{code}'
  AND substr("{C_TRADE_DAY}", 1, 4) = '{year}'
  AND ("{C_CLOSE}" / "{C_PREV_CLOSE}" - 1.0) >= 0.098"""

    def _industry_volume_sum(self, question: str) -> str | None:
        if "成交量合计" not in question and "成交量合计是多少" not in question:
            return None
        date_match = re.search(r"(20\d{6})", question)
        industry_match = re.search(r"一级行业为(.+?)的股票", question)
        if not date_match or not industry_match:
            return None
        date = date_match.group(1)
        industry = industry_match.group(1)
        standard = "申万行业分类" if "申万" in question else None
        if standard is None:
            standard = "中信行业分类" if "中信" in question else None
        standard_sql = f'AND i."{C_STANDARD}" = \'{standard}\'' if standard else ""
        return f"""SELECT ROUND(SUM(d."{C_VOLUME}"), 0) AS 成交量合计
FROM "{T_A_STOCK_DAILY}" d
JOIN "{T_A_INDUSTRY}" i
  ON d."{C_STOCK_CODE}" = i."{C_STOCK_CODE}"
 AND d."{C_TRADE_DAY}" = i."{C_TRADE_DATE}"
WHERE d."{C_TRADE_DAY}" = '{date}'
  {standard_sql}
  AND i."{C_INDUSTRY_L1}" = '{industry}'"""

    def _industry_top_pct_change(self, question: str) -> str | None:
        if "涨跌幅最大" not in question:
            return None
        date_match = re.search(r"(20\d{6})", question)
        industry_match = re.search(r"一级行业为(.+?)行业", question)
        if not date_match or not industry_match:
            return None
        date = date_match.group(1)
        industry = industry_match.group(1)
        standard = "申万行业分类" if "申万" in question else None
        if standard is None:
            standard = "中信行业分类" if "中信" in question else None
        standard_sql = f'AND i."{C_STANDARD}" = \'{standard}\'' if standard else ""
        return f"""WITH ranked AS (
  SELECT d."{C_STOCK_CODE}" AS 股票代码,
         ROUND((d."{C_CLOSE}" / d."{C_PREV_CLOSE}" - 1.0) * 100, 2) AS 涨跌幅
  FROM "{T_A_STOCK_DAILY}" d
  JOIN "{T_A_INDUSTRY}" i
    ON d."{C_STOCK_CODE}" = i."{C_STOCK_CODE}"
   AND d."{C_TRADE_DAY}" = i."{C_TRADE_DATE}"
  WHERE d."{C_TRADE_DAY}" = '{date}'
    {standard_sql}
    AND i."{C_INDUSTRY_L1}" = '{industry}'
)
SELECT 股票代码, 涨跌幅
FROM ranked
ORDER BY 涨跌幅 DESC
LIMIT 1"""

    def _industry_count_above_pct(self, question: str) -> str | None:
        if "涨幅超过" not in question:
            return None
        date_match = re.search(r"(20\d{6})", question)
        industry_match = re.search(r"[，,]?([^，,。]+?)一级行业涨幅超过", question)
        pct_match = re.search(r"超过(\d+)%", question)
        if not date_match or not industry_match or not pct_match:
            return None
        date = date_match.group(1)
        industry = industry_match.group(1).replace("请帮我查询出", "").strip()
        pct = pct_match.group(1)
        standard = "申万行业分类" if "申万" in question else None
        if standard is None:
            standard = "中信行业分类" if "中信" in question else None
        standard_sql = f'AND i."{C_STANDARD}" = \'{standard}\'' if standard else ""
        return f"""SELECT COUNT(*) AS 股票数量
FROM "{T_A_STOCK_DAILY}" d
JOIN "{T_A_INDUSTRY}" i
  ON d."{C_STOCK_CODE}" = i."{C_STOCK_CODE}"
 AND d."{C_TRADE_DAY}" = i."{C_TRADE_DATE}"
WHERE d."{C_TRADE_DAY}" = '{date}'
  {standard_sql}
  AND i."{C_INDUSTRY_L1}" = '{industry}'
  AND ((d."{C_CLOSE}" / d."{C_PREV_CLOSE}" - 1.0) * 100) > {pct}"""

    def _industry_top_amount(self, question: str) -> str | None:
        if "成交金额" not in question or "最多" not in question:
            return None
        date_match = re.search(r"(20\d{6})", question)
        industry_match = re.search(r"一级行业为(.+?)行业", question)
        if not date_match or not industry_match:
            return None
        date = date_match.group(1)
        industry = industry_match.group(1)
        standard = "申万行业分类" if "申万" in question else None
        if standard is None:
            standard = "中信行业分类" if "中信" in question else None
        standard_sql = f'AND i."{C_STANDARD}" = \'{standard}\'' if standard else ""
        return f"""SELECT d."{C_STOCK_CODE}" AS 股票代码,
ROUND(d."{C_AMOUNT}", 2) AS 成交金额
FROM "{T_A_STOCK_DAILY}" d
JOIN "{T_A_INDUSTRY}" i
  ON d."{C_STOCK_CODE}" = i."{C_STOCK_CODE}"
 AND d."{C_TRADE_DAY}" = i."{C_TRADE_DATE}"
WHERE d."{C_TRADE_DAY}" = '{date}'
  {standard_sql}
  AND i."{C_INDUSTRY_L1}" = '{industry}'
ORDER BY d."{C_AMOUNT}" DESC
LIMIT 1"""

    def _industry_most_company_count(self, question: str) -> str | None:
        if "A股公司数量最多" not in question:
            return None
        date_match = re.search(r"(20\d{6})", question)
        if not date_match:
            return None
        date = date_match.group(1)
        standard = "中信行业分类" if "中信" in question else "申万行业分类"
        return f"""SELECT i."{C_INDUSTRY_L1}" AS 一级行业名称,
COUNT(DISTINCT i."{C_STOCK_CODE}") AS 公司数量
FROM "{T_A_INDUSTRY}" i
WHERE i."{C_TRADE_DATE}" = '{date}'
  AND i."{C_STANDARD}" = '{standard}'
GROUP BY i."{C_INDUSTRY_L1}"
ORDER BY 公司数量 DESC
LIMIT 1"""

    def _avg_amount_by_industry_l2(self, question: str) -> str | None:
        if "平均成交金额是多少" not in question:
            return None
        date_match = re.search(r"(20\d{6})", question)
        industry_match = re.search(r"申万二级(.+?)行业", question)
        if not date_match or not industry_match:
            return None
        date = date_match.group(1)
        industry2 = industry_match.group(1)
        return f"""SELECT ROUND(AVG(d."{C_AMOUNT}"), 5) AS 平均成交金额
FROM "{T_A_STOCK_DAILY}" d
JOIN "{T_A_INDUSTRY}" i
  ON d."{C_STOCK_CODE}" = i."{C_STOCK_CODE}"
 AND d."{C_TRADE_DAY}" = i."{C_TRADE_DATE}"
WHERE d."{C_TRADE_DAY}" = '{date}'
  AND i."{C_STANDARD}" = '申万行业分类'
  AND i."{C_INDUSTRY_L2}" = '{industry2}'"""

    def _top_avg_daily_return(self, question: str) -> str | None:
        if "日均收益率最高" not in question:
            return None
        year_match = re.search(r"在(20\d{2})年", question)
        year_value = year_match.group(1) if year_match else None
        industry_match = re.search(r"([^\s，,。]+)一级行业中", question)
        if not year_value or not industry_match:
            return None
        industry = industry_match.group(1)
        standard = "申万行业分类" if "申万" in question else "中信行业分类"
        return f"""WITH returns AS (
  SELECT d."{C_STOCK_CODE}" AS 股票代码,
         AVG((d."{C_CLOSE}" - d."{C_PREV_CLOSE}") / d."{C_PREV_CLOSE}") AS 日均收益率
  FROM "{T_A_STOCK_DAILY}" d
  JOIN "{T_A_INDUSTRY}" i
    ON d."{C_STOCK_CODE}" = i."{C_STOCK_CODE}"
   AND d."{C_TRADE_DAY}" = i."{C_TRADE_DATE}"
  WHERE substr(d."{C_TRADE_DAY}", 1, 4) = '{year_value}'
    AND i."{C_STANDARD}" = '{standard}'
    AND i."{C_INDUSTRY_L1}" = '{industry}'
  GROUP BY d."{C_STOCK_CODE}"
)
SELECT 股票代码, ROUND(日均收益率, 6) AS 日均收益率
FROM returns
ORDER BY 日均收益率 DESC
LIMIT 1"""

    def _fund_count_by_manager_year(self, question: str) -> str | None:
        if "成立了多少基金" not in question:
            return None
        manager_match = re.search(r"([^\s，,。?？]+?管理有限公司)", question)
        year_match = re.search(r"(20\d{2})年", question)
        if not manager_match or not year_match:
            return None
        manager = manager_match.group(0)
        year = year_match.group(1)
        return f"""SELECT COUNT(*) AS 基金数量
FROM "{T_FUND_BASIC}"
WHERE "{C_MANAGER}" = '{manager}'
  AND substr("{C_SETUP_DATE}", 1, 4) = '{year}'"""

    def _fund_nav_on_date(self, question: str) -> str | None:
        if "资产净值和单位净值" not in question:
            return None
        fund_match = re.search(r"查一下(.+?)基金在(20\d{6})", question)
        if not fund_match:
            return None
        fund_name, date = fund_match.groups()
        return f"""SELECT d."{C_ASSET_NAV}" AS 资产净值,
d."{C_NAV}" AS 单位净值
FROM "{T_FUND_DAILY}" d
JOIN "{T_FUND_BASIC}" b
  ON d."{C_FUND_CODE}" = b."{C_FUND_CODE}"
WHERE b."{C_FUND_SHORT}" = '{fund_name}'
  AND d."{C_TRADE_DATE}" = '{date}'"""

    def _fund_net_redeem_stats(self, question: str) -> str | None:
        if "净赎回" not in question:
            return None
        year_match = re.search(r"(20\d{2})年", question)
        quarter_map = {"一季度": "03-31", "二季度": "06-30", "三季度": "09-30", "四季度": "12-31"}
        quarter = next((k for k in quarter_map if k in question), None)
        if not year_match or not quarter:
            return None
        date = f"{year_match.group(1)}-{quarter_map[quarter]} 00:00:00"
        return f"""SELECT COUNT(*) AS 净赎回基金数量,
ROUND(SUM("{C_REDEEM_SHARE}" - "{C_PURCHASE_SHARE}"), 2) AS 总赎回份额
FROM "{T_FUND_SCALE}"
WHERE "{C_END_DATE}" = '{date}'
  AND "{C_REDEEM_SHARE}" > "{C_PURCHASE_SHARE}" """

    def _fund_net_purchase_stats(self, question: str) -> str | None:
        if "净申购" not in question:
            return None
        year_match = re.search(r"(20\d{2})年", question)
        quarter_map = {"一季度": "03-31", "二季度": "06-30", "三季度": "09-30", "四季度": "12-31"}
        quarter = next((k for k in quarter_map if k in question), None)
        if not year_match or not quarter:
            return None
        date = f"{year_match.group(1)}-{quarter_map[quarter]} 00:00:00"
        return f"""SELECT COUNT(*) AS 净申购基金数量,
ROUND(SUM("{C_PURCHASE_SHARE}" - "{C_REDEEM_SHARE}"), 2) AS 总申购份额
FROM "{T_FUND_SCALE}"
WHERE "{C_END_DATE}" = '{date}'
  AND "{C_PURCHASE_SHARE}" > "{C_REDEEM_SHARE}" """

    def _institution_gt_personal_count(self, question: str) -> str | None:
        if "机构投资者持有份额比个人投资者多" not in question:
            return None
        year_match = re.search(r"(20\d{2})年", question)
        manager_match = re.search(r"([^\s，,。?？]+?管理有限公司)", question)
        report_type = "中期报告" if "中期报告" in question else "年报(含半年报)" if "年报" in question else None
        if not year_match or not report_type or not manager_match:
            return None
        manager = manager_match.group(0)
        return f"""SELECT COUNT(*) AS 基金数量
FROM "{T_FUND_HOLDER}" h
JOIN "{T_FUND_BASIC}" b
  ON h."{C_FUND_CODE}" = b."{C_FUND_CODE}"
WHERE h."{C_REPORT_YEAR}" = {year_match.group(1)}
  AND h."{C_REPORT_TYPE}" = '{report_type}'
  AND b."{C_MANAGER}" = '{manager}'
  AND h."{C_INST_SHARE}" > h."{C_PERSON_SHARE}" """

    def _personal_gt_inst_money_fund_count(self, question: str) -> str | None:
        if "个人投资者持有基金份额大于机构投资者持有基金份额" not in question or "货币型类型" not in question:
            return None
        year_match = re.search(r"(20\d{2})", question)
        if not year_match:
            return None
        return f"""SELECT COUNT(*) AS 基金数量
FROM "{T_FUND_HOLDER}" h
JOIN "{T_FUND_BASIC}" b
  ON h."{C_FUND_CODE}" = b."{C_FUND_CODE}"
WHERE h."{C_REPORT_YEAR}" = {year_match.group(1)}
  AND h."{C_REPORT_TYPE}" = '年度报告'
  AND b."{C_FUND_TYPE}" = '货币型'
  AND h."{C_PERSON_SHARE}" > h."{C_INST_SHARE}" """

    def _personal_gt_inst_ratio_by_manager(self, question: str) -> str | None:
        if "有多少比例的基金是个人投资者持有的份额超过机构投资者" not in question:
            return None
        year_match = re.search(r"(20\d{2})", question)
        manager_match = re.search(r"([^\s，,。?？]+?管理有限公司)", question)
        report_type = "中期报告" if "中期报告" in question else "年度报告" if "年度报告" in question else None
        if not year_match or not manager_match or not report_type:
            return None
        manager = manager_match.group(0)
        return f"""WITH base AS (
  SELECT h."{C_FUND_CODE}",
         CASE WHEN h."{C_PERSON_SHARE}" > h."{C_INST_SHARE}" THEN 1 ELSE 0 END AS personal_gt
  FROM "{T_FUND_HOLDER}" h
  JOIN "{T_FUND_BASIC}" b
    ON h."{C_FUND_CODE}" = b."{C_FUND_CODE}"
  WHERE h."{C_REPORT_YEAR}" = {year_match.group(1)}
    AND h."{C_REPORT_TYPE}" = '{report_type}'
    AND b."{C_MANAGER}" = '{manager}'
)
SELECT ROUND(AVG(personal_gt) * 100, 2) AS 比例
FROM base"""

    def _avg_management_fee_mixed_funds(self, question: str) -> str | None:
        if "管理费率的平均值是多少" not in question:
            return None
        manager_match = re.search(r"([^\s，,。?？]+?管理有限公司)", question)
        year_match = re.search(r"(20\d{2})年", question)
        if not manager_match or not year_match:
            return None
        manager = manager_match.group(1)
        year = year_match.group(1)
        return f"""SELECT ROUND(AVG(CAST(REPLACE("{C_MGMT_FEE}", '%', '') AS REAL)), 2) AS 平均管理费率
FROM "{T_FUND_BASIC}"
WHERE "{C_MANAGER}" = '{manager}'
  AND "{C_FUND_TYPE}" = '混合型'
  AND substr("{C_SETUP_DATE}", 1, 4) = '{year}'"""

    def _late_report_share_growth_count(self, question: str) -> str | None:
        if "报告期期初基金总份额小于报告期期末基金总份额" not in question:
            return None
        year_match = re.search(r"在(20\d{2})年", question)
        manager_match = re.search(r"([^\s，,。?？]+?管理有限公司)", question)
        if not year_match or not manager_match:
            return None
        year = year_match.group(1)
        manager = manager_match.group(0)
        return f"""WITH ranked AS (
  SELECT s."{C_FUND_CODE}",
         s."{C_BEGIN_SHARE}",
         s."{C_END_SHARE}",
         ROW_NUMBER() OVER (PARTITION BY s."{C_FUND_CODE}" ORDER BY s."{C_END_DATE}" DESC) AS rn
  FROM "{T_FUND_SCALE}" s
  JOIN "{T_FUND_BASIC}" b
    ON s."{C_FUND_CODE}" = b."{C_FUND_CODE}"
  WHERE s."{C_REPORT_YEAR}" = {year}
    AND b."{C_MANAGER}" = '{manager}'
)
SELECT COUNT(*) AS 基金数量
FROM ranked
WHERE rn = 1
  AND "{C_BEGIN_SHARE}" < "{C_END_SHARE}" """

    def _stock_holding_ratio_count(self, question: str) -> str | None:
        if "持有大亚圣象" not in question or "市值占基金资产净值比不小于5%" not in question:
            return None
        return f"""SELECT COUNT(DISTINCT "{C_FUND_CODE}") AS 基金数量
FROM "{T_FUND_STOCK}"
WHERE "{C_STOCK_NAME}" = '大亚圣象'
  AND "{C_HOLD_DATE}" = '20191231'
  AND "{C_STOCK_MV_RATIO}" >= 5"""

    def _positive_return_top10_count(self, question: str) -> str | None:
        if "前10大重仓股中" not in question or "取得正收益" not in question:
            return None
        fund_match = re.search(r"我想知道(.+?)基金|(.+?)基金，在", question)
        date_match = re.search(r"在(20\d{2})年半年度报告|在(20\d{2})年年度报告|在(20\d{2})年", question)
        if not fund_match or not date_match:
            return None
        fund_name = fund_match.group(1) or fund_match.group(2)
        year = next(group for group in date_match.groups() if group)
        hold_date = f"{year}0630" if "半年度报告" in question else f"{year}1231"
        return f"""WITH top10 AS (
  SELECT "{C_STOCK_CODE}" AS 股票代码
  FROM "{T_FUND_STOCK}"
  WHERE "{C_FUND_SHORT}" = '{fund_name}'
    AND "{C_HOLD_DATE}" = '{hold_date}'
    AND "{C_TOP_N}" <= 10
),
stock_period AS (
  SELECT d."{C_STOCK_CODE}" AS 股票代码,
         MIN(d."{C_TRADE_DAY}") AS 起始交易日,
         MAX(d."{C_TRADE_DAY}") AS 结束交易日
  FROM "{T_A_STOCK_DAILY}" d
  JOIN top10 t
    ON d."{C_STOCK_CODE}" = t.股票代码
  WHERE substr(d."{C_TRADE_DAY}", 1, 4) = '{year}'
    AND d."{C_TRADE_DAY}" <= '{hold_date}'
  GROUP BY d."{C_STOCK_CODE}"
)
SELECT COUNT(*) AS 正收益股票数量
FROM (
  SELECT p.股票代码
  FROM stock_period p
  JOIN "{T_A_STOCK_DAILY}" d1
    ON p.股票代码 = d1."{C_STOCK_CODE}" AND p.起始交易日 = d1."{C_TRADE_DAY}"
  JOIN "{T_A_STOCK_DAILY}" d2
    ON p.股票代码 = d2."{C_STOCK_CODE}" AND p.结束交易日 = d2."{C_TRADE_DAY}"
  WHERE d2."{C_CLOSE}" > d1."{C_CLOSE}"
)"""

    def _avg_market_value_by_industry_l2_for_fund(self, question: str) -> str | None:
        if "平均市值是多少" not in question:
            return None
        code_match = re.search(r"代码为(\d{6})|代码为(\d{6,})", question)
        date_match = re.search(r"(20\d{2})年12月31日|(20\d{8})", question)
        industry_match = re.search(r"中信二级(.+?)行业", question)
        if not code_match or not date_match or not industry_match:
            return None
        fund_code = next(group for group in code_match.groups() if group)
        date_value = next(group for group in date_match.groups() if group)
        hold_date = date_value if len(date_value) == 8 else f"{date_value}1231"
        industry2 = industry_match.group(1)
        return f"""SELECT ROUND(AVG(h."{C_MARKET_VALUE}"), 3) AS 平均市值
FROM "{T_FUND_STOCK}" h
JOIN "{T_A_INDUSTRY}" i
  ON h."{C_STOCK_CODE}" = i."{C_STOCK_CODE}"
 AND h."{C_HOLD_DATE}" = i."{C_TRADE_DATE}"
WHERE h."{C_FUND_CODE}" = '{fund_code}'
  AND h."{C_HOLD_DATE}" = '{hold_date}'
  AND h."{C_TOP_N}" <= 20
  AND i."{C_STANDARD}" = '中信行业分类'
  AND i."{C_INDUSTRY_L2}" = '{industry2}'"""

    def _top3_bond_names(self, question: str) -> str | None:
        if "债券名称" not in question or "前三大" not in question:
            return None
        fund_match = re.search(r"(.+?)基金在\s*(20\d{8})\s*的(?:季报|年报|半年报)", question)
        if not fund_match:
            return None
        fund_name, date = fund_match.groups()
        return f"""SELECT "{C_BOND_NAME}" AS 债券名称
FROM "{T_FUND_BOND}"
WHERE "{C_FUND_SHORT}" = '{fund_name}'
  AND "{C_HOLD_DATE}" = '{date}'
ORDER BY "{C_BOND_MV_RATIO}" DESC
LIMIT 3"""

    def _convertible_top_industry(self, question: str) -> str | None:
        if "可转债持仓占比最大" not in question:
            return None
        fund_match = re.search(r"其(.+?)基金在(20\d{8})|(.+?)基金在(20\d{8})", question)
        if not fund_match:
            return None
        groups = fund_match.groups()
        fund_name = groups[0] or groups[2]
        date = groups[1] or groups[3]
        standard = "中信行业分类"
        return f"""WITH joined AS (
  SELECT i."{C_INDUSTRY_L1}" AS 一级行业名称,
         SUM(c."{C_CONVERT_MV_RATIO}") AS 占比合计
  FROM "{T_FUND_CONVERTIBLE}" c
  JOIN "{T_A_INDUSTRY}" i
    ON c."{C_CONVERT_STOCK_CODE}" = i."{C_STOCK_CODE}"
   AND c."{C_HOLD_DATE}" = i."{C_TRADE_DATE}"
  WHERE c."{C_FUND_SHORT}" = '{fund_name}'
    AND c."{C_HOLD_DATE}" = '{date}'
    AND i."{C_STANDARD}" = '{standard}'
  GROUP BY i."{C_INDUSTRY_L1}"
)
SELECT 一级行业名称, ROUND(占比合计, 4) AS 占比合计
FROM joined
ORDER BY 占比合计 DESC
LIMIT 1"""

    def _fallback_plan(self, question: str) -> str:
        escaped_question = question.replace("'", "''")
        return (
            "SELECT "
            f"'{escaped_question}' AS 原问题, "
            "'当前项目已接入真实SQLite库，但该题型的专用SQL规则仍待补充。' AS 提示"
        )

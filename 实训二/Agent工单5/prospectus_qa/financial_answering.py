"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class FinancialAnswer:
    answer: str
    sql: str
    route: str = "financial_db"
    confidence: float = 0.94


class FinancialDatabaseAnswerer:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._fund_names_cache: list[str] | None = None
        self._manager_names_cache: list[str] | None = None
        self._indexes_ready = False

    @property
    def is_ready(self) -> bool:
        return self.db_path.exists() and self.db_path.stat().st_size > 0

    def answer(self, question: str) -> FinancialAnswer | None:
        if not self.is_ready:
            return None
        if not self._indexes_ready:
            self._ensure_indexes()

        handlers = [
            self._answer_stock_max_change_in_industry,
            self._answer_industry_rise_count,
            self._answer_limit_up_days,
            self._answer_industry_volume_sum,
            self._answer_industry_amount_sum,
            self._answer_industry_amount_max_stock,
            self._answer_stock_close_price,
            self._answer_manager_fund_count,
            self._answer_manager_product_count,
            self._answer_manager_low_fee_fund_count,
            self._answer_manager_type_most,
            self._answer_net_redeem_summary,
            self._answer_net_subscribe_summary,
            self._answer_fund_nav,
            self._answer_manager_and_nav,
            self._answer_holder_more_count,
            self._answer_holder_personal_more_type_count,
            self._answer_holder_personal_more_ratio,
            self._answer_holder_ratio_threshold_summary,
            self._answer_holder_personal_ratio_below_count,
            self._answer_mixed_fund_fee_avg,
            self._answer_fund_fee_rate_or_custodian,
            self._answer_scale_growth_count,
            self._answer_scale_drop_count,
            self._answer_heavy_holding_count,
            self._answer_zero_redeem_count,
            self._answer_report_diff_max_fund,
            self._answer_fund_nav_and_unit,
            self._answer_fund_type_top_bond_names,
            self._answer_bond_type_max,
            self._answer_bond_market_value_type_max,
            self._answer_convertible_max_industry,
            self._answer_manager_bond_holding_count,
            self._answer_top10_positive_return_count,
            self._answer_top_n_stock_return,
            self._answer_top_n_holding_stock_code,
            self._answer_top_n_holding_stock_code_name,
            self._answer_top_n_market_count,
            self._answer_top_n_same_bond_count,
            self._answer_stock_in_top_n_count,
            self._answer_top20_avg_market_value_by_industry,
            self._answer_fund_stock_industry_list,
            self._answer_latest_industry_level2,
            self._answer_stock_industry_on_date,
            self._answer_industry_company_count,
            self._answer_industry_company_most,
            self._answer_daily_return_best_stock,
            self._answer_industry_amount_avg,
            self._answer_industry_volatility_max,
            self._answer_industry_daily_volatility_min,
            self._answer_open_gt_prev_close_days,
            self._answer_open_gt_prev_high_count,
            self._answer_low_volume_days,
            self._answer_top3_amount_codes,
            self._answer_highest_close_price,
            self._answer_annualized_return,
            self._answer_hk_down_count,
            self._answer_hk_amplitude,
        ]
        for handler in handlers:
            result = handler(question)
            if result is not None:
                return result
        return None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_indexes(self) -> None:
        statements = [
            'CREATE INDEX IF NOT EXISTS "idx_a_stock_code_date" ON "A股票日行情表"("股票代码", "交易日")',
            'CREATE INDEX IF NOT EXISTS "idx_a_stock_date" ON "A股票日行情表"("交易日")',
            'CREATE INDEX IF NOT EXISTS "idx_industry_code_date" ON "A股公司行业划分表"("股票代码", "交易日期")',
            'CREATE INDEX IF NOT EXISTS "idx_industry_date_std_l1" ON "A股公司行业划分表"("交易日期", "行业划分标准", "一级行业名称")',
            'CREATE INDEX IF NOT EXISTS "idx_industry_date_std_l2" ON "A股公司行业划分表"("交易日期", "行业划分标准", "二级行业名称")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_basic_code" ON "基金基本信息"("基金代码")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_basic_name" ON "基金基本信息"("基金简称")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_basic_manager_year" ON "基金基本信息"("管理人", "成立日期", "基金类型")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_daily_code_date" ON "基金日行情表"("基金代码", "交易日期")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_stock_name_date" ON "基金股票持仓明细"("基金简称", "持仓日期", "报告类型", "第N大重仓股")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_stock_code_date" ON "基金股票持仓明细"("基金代码", "持仓日期", "报告类型", "第N大重仓股")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_stock_stockname_date" ON "基金股票持仓明细"("股票名称", "持仓日期", "第N大重仓股")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_bond_name_date" ON "基金债券持仓明细"("基金简称", "持仓日期", "报告类型", "债券类型")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_conv_name_date" ON "基金可转债持仓明细"("基金简称", "持仓日期", "报告类型")',
            'CREATE INDEX IF NOT EXISTS "idx_fund_conv_code_date" ON "基金可转债持仓明细"("基金代码", "持仓日期", "报告类型", "第N大重仓股")',
            'CREATE INDEX IF NOT EXISTS "idx_scale_date_year" ON "基金规模变动表"("截止日期", "定期报告所属年度")',
            'CREATE INDEX IF NOT EXISTS "idx_scale_code_date" ON "基金规模变动表"("基金代码", "截止日期")',
            'CREATE INDEX IF NOT EXISTS "idx_holder_year_type" ON "基金份额持有人结构"("定期报告所属年度", "报告类型")',
            'CREATE INDEX IF NOT EXISTS "idx_holder_code_year_type" ON "基金份额持有人结构"("基金代码", "定期报告所属年度", "报告类型")',
            'CREATE INDEX IF NOT EXISTS "idx_hk_stock_code_date" ON "港股票日行情表"("股票代码", "交易日")',
            'CREATE INDEX IF NOT EXISTS "idx_hk_stock_date" ON "港股票日行情表"("交易日")',
        ]
        try:
            with self._connect() as conn:
                for statement in statements:
                    conn.execute(statement)
                conn.commit()
        except sqlite3.OperationalError:
            # 只读/锁表环境下继续答题，避免索引初始化阻塞主流程。
            pass
        self._indexes_ready = True

    def _fund_names(self) -> list[str]:
        if self._fund_names_cache is None:
            with self._connect() as conn:
                rows = conn.execute(
                    'SELECT DISTINCT "基金简称" AS name FROM "基金基本信息" WHERE "基金简称" IS NOT NULL'
                ).fetchall()
            self._fund_names_cache = sorted(
                [row["name"] for row in rows if row["name"]],
                key=len,
                reverse=True,
            )
        return self._fund_names_cache

    def _manager_names(self) -> list[str]:
        if self._manager_names_cache is None:
            with self._connect() as conn:
                rows = conn.execute(
                    'SELECT DISTINCT "管理人" AS name FROM "基金基本信息" WHERE "管理人" IS NOT NULL'
                ).fetchall()
            self._manager_names_cache = sorted(
                [row["name"] for row in rows if row["name"]],
                key=len,
                reverse=True,
            )
        return self._manager_names_cache

    def _execute_one(self, sql: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(sql).fetchone()

    def _execute_all(self, sql: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(sql).fetchall()

    def _normalize_date(self, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) == 8:
            return digits
        raise ValueError(f"Unsupported date format: {value}")

    def _extract_first_date(self, question: str) -> str | None:
        match = re.search(r"(20\d{2}[年/-]?\d{1,2}[月/-]?\d{1,2}日?|20\d{6})", question)
        if not match:
            return None
        try:
            return self._normalize_date(match.group(1))
        except ValueError:
            return None

    def _extract_year(self, question: str) -> str | None:
        match = re.search(r"(20\d{2})年", question)
        if match:
            return match.group(1)
        match = re.search(r"(20\d{2})", question)
        if match:
            return match.group(1)
        return None

    def _extract_month(self, question: str) -> str | None:
        match = re.search(r"(20\d{2})年(\d{1,2})月", question)
        if match:
            return f"{match.group(1)}{int(match.group(2)):02d}"
        return None

    def _extract_stock_code(self, question: str) -> str | None:
        match = re.search(r"股票代码(?:为|是)?\s*([0-9]{5,6})", question)
        if match:
            return match.group(1).zfill(6)
        match = re.search(r"\b([0-9]{6})股票", question)
        if match:
            return match.group(1)
        match = re.search(r"股票\s*([0-9]{6})", question)
        if match:
            return match.group(1)
        match = re.search(r"代码为\s*([0-9]{5,6})", question)
        if match:
            return match.group(1).zfill(6)
        match = re.search(r"\b([0-9]{6})\b", question)
        if match:
            return match.group(1)
        match = re.search(r"代码为\s*([0-9]{5})\b", question)
        if match:
            return match.group(1)
        return None

    def _extract_fund_code(self, question: str) -> str | None:
        match = re.search(r"基金代码\s*([0-9]{6})", question)
        if match:
            return match.group(1)
        match = re.search(r"代码为\s*([0-9]{6})的基金", question)
        if match:
            return match.group(1)
        return None

    def _extract_company_name(self, question: str, suffix: str) -> str | None:
        if suffix == "有限公司":
            for name in self._manager_names():
                if name in question:
                    return name
        match = re.search(rf"([\u4e00-\u9fffA-Za-z0-9（）()·\-]+{suffix})", question)
        return match.group(1) if match else None

    def _extract_fund_name(self, question: str) -> str | None:
        for name in self._fund_names():
            if name in question:
                return name
        patterns = [
            r"([\u4e00-\u9fffA-Za-z0-9()（）\-+/.]+基金)在\d",
            r"([\u4e00-\u9fffA-Za-z0-9()（）\-+/.]+基金)，?在\d",
            r"请给出([\u4e00-\u9fffA-Za-z0-9()（）\-+/.]+基金)的",
            r"([\u4e00-\u9fffA-Za-z0-9()（）\-+/.]+基金)",
        ]
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                name = match.group(1).strip("，。?？ ")
                if "管理有限公司" not in name and len(name) >= 3:
                    return name
        return None

    def _extract_bond_name(self, question: str) -> str | None:
        match = re.search(r"持有([\u4e00-\u9fffA-Za-z0-9]+)且是前10大重仓股", question)
        return match.group(1) if match else None

    def _extract_stock_name(self, question: str) -> str | None:
        patterns = [
            r"持有([\u4e00-\u9fffA-Za-z0-9]+)这一股票",
            r"([\u4e00-\u9fffA-Za-z0-9]+)在多少只基金",
            r"股票名称是什么\??",
        ]
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                return match.group(1)
        return None

    def _report_type_like(self, question: str, for_holder: bool = False) -> str | None:
        if for_holder:
            if "中期报告" in question or "半年度报告" in question or "半年报" in question:
                return "中期报告"
            if "年度报告" in question or "年报" in question:
                return "年度报告"
            return None
        if "季报" in question or "季度" in question or "Q1" in question or "Q2" in question or "Q3" in question or "Q4" in question:
            return "季报"
        if "年报" in question or "半年报" in question or "半年度报告" in question or "年报(含半年报)" in question:
            return "年报(含半年报)"
        if "报告" in question:
            return "其他"
        return None

    def _industry_standard(self, question: str) -> str:
        if "申万" in question:
            return "申万行业分类"
        if "中信" in question:
            return "中信行业分类"
        industry_name = self._extract_industry_name(question)
        if industry_name:
            if industry_name in self.SW_LEVEL1 or industry_name in self.SW_ALIAS:
                return "申万行业分类"
            if industry_name in self.CITIC_LEVEL1 or industry_name in self.CITIC_ALIAS:
                return "中信行业分类"
        return "中信行业分类"

    def _industry_level_column(self, question: str) -> str:
        if "二级行业" in question or "中信二级" in question or "申万二级" in question:
            return "二级行业名称"
        return "一级行业名称"

    def _extract_industry_name(self, question: str) -> str | None:
        patterns = [
            r"一级行业为([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)的股票",
            r"二级行业为([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)的股票",
            r"([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)一级行业涨幅",
            r"([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)二级行业涨幅",
            r"([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)一级行业的所有股票",
            r"([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)二级行业的所有股票",
            r"一级行业为([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)行业",
            r"二级行业为([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)行业",
            r"属于中信二级([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)行业",
            r"属于申万二级([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)行业",
            r"属于中信二级([\u4e00-\u9fffA-Za-z0-9Ⅱ及]+)行业",
            r"属于申万二级([\u4e00-\u9fffA-Za-z0-9Ⅱ及]+)行业",
            r"申万行业分类里一级行业为([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)行业",
            r"中信行业分类里一级行业为([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)行业",
            r"([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)一级行业有多少",
            r"([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)二级行业的A股股票",
            r"([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)一级行业中",
            r"([^\s，。,？?]+)一级行业中",
            r"([^\s，。,？?]+)二级行业的A股股票",
            r"在([\u4e00-\u9fffA-Za-z0-9Ⅱ]+)行业",
        ]
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                name = match.group(1).strip().rstrip("的")
                return name
        return None

    def _resolve_industry_name(self, question: str, industry_name: str) -> str:
        standard = self._industry_standard(question)
        if standard == "申万行业分类":
            return self.SW_ALIAS.get(industry_name, industry_name)
        return self.CITIC_ALIAS.get(industry_name, industry_name)

    def _format_number(self, value: float, digits: int = 2) -> str:
        text = f"{value:.{digits}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text

    def _escape(self, value: str) -> str:
        return value.replace("'", "''")

    def _quarter_bounds(self, date_text: str) -> tuple[str, str] | None:
        match = re.search(r"(20\d{2}).*?(Q([1-4])|([一二三四])季度|([一二三四])季度|([一二三四])季报)", date_text)
        if not match:
            return None
        year = match.group(1)
        quarter_token = match.group(3) or match.group(4) or match.group(5) or match.group(6)
        quarter_map = {"1": 1, "2": 2, "3": 3, "4": 4, "一": 1, "二": 2, "三": 3, "四": 4}
        quarter = quarter_map[quarter_token]
        bounds = {
            1: (f"{year}0101", f"{year}0331"),
            2: (f"{year}0401", f"{year}0630"),
            3: (f"{year}0701", f"{year}0930"),
            4: (f"{year}1001", f"{year}1231"),
        }
        return bounds[quarter]

    def _fund_holding_report_date(self, question: str) -> str | None:
        date = self._extract_first_date(question)
        if date:
            return date
        month = self._extract_month(question)
        if month:
            month_end_map = {
                "03": "31",
                "06": "30",
                "09": "30",
                "12": "31",
            }
            mm = month[4:6]
            if mm in month_end_map:
                return f"{month}{month_end_map[mm]}"
        year = self._extract_year(question)
        if not year:
            return None
        if "半年度报告" in question or "半年报" in question or "中期报告" in question:
            return f"{year}0630"
        if "年度报告" in question or "年报" in question:
            return f"{year}1231"
        if "Q1" in question or "一季度" in question:
            return f"{year}0331"
        if "Q2" in question or "二季度" in question or "半年度报告" in question or "半年报" in question:
            return f"{year}0630"
        if "Q3" in question or "三季度" in question:
            return f"{year}0930"
        if "Q4" in question or "四季度" in question or "年报" in question or "年度报告" in question:
            return f"{year}1231"
        return None

    def _answer_stock_close_price(self, question: str) -> FinancialAnswer | None:
        if "收盘价" not in question or "股票" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        trade_date = self._extract_first_date(question)
        if not stock_code or not trade_date:
            return None
        sql = (
            'SELECT ROUND("收盘价(元)", 3) AS close_price '
            'FROM "A股票日行情表" '
            f'WHERE "股票代码" = "{stock_code}" AND "交易日" = "{trade_date}" '
            "LIMIT 1"
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"股票{stock_code}在{trade_date}的收盘价是{float(row['close_price']):.3f}。",
            sql=sql,
        )

    def _answer_stock_max_change_in_industry(self, question: str) -> FinancialAnswer | None:
        if "涨跌幅最大股票" not in question:
            return None
        trade_date = self._extract_first_date(question)
        industry_name = self._extract_industry_name(question)
        if not trade_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        level = self._industry_level_column(question)
        standard = self._industry_standard(question)
        sql = (
            'SELECT a."股票代码" AS stock_code, '
            'ROUND((a."收盘价(元)" - a."昨收盘(元)") / a."昨收盘(元)" * 100, 2) AS change_pct '
            'FROM "A股票日行情表" a '
            'JOIN "A股公司行业划分表" b '
            'ON a."股票代码" = b."股票代码" '
            f'AND b."交易日期" = "{trade_date}" '
            f'WHERE a."交易日" = "{trade_date}" '
            'AND a."昨收盘(元)" > 0 '
            f'AND b."行业划分标准" = "{standard}" '
            f'AND b."{level}" = "{industry_name}" '
            'ORDER BY change_pct DESC, a."股票代码" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}在{standard}下，{industry_name}行业涨跌幅最大的股票代码是{row['stock_code']}，涨跌幅是{float(row['change_pct']):.2f}%。",
            sql=sql,
        )

    def _answer_industry_rise_count(self, question: str) -> FinancialAnswer | None:
        if "涨幅超过5%" not in question:
            return None
        trade_date = self._extract_first_date(question)
        industry_name = self._extract_industry_name(question)
        if not trade_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        sql = (
            'SELECT COUNT(*) AS cnt '
            'FROM "A股票日行情表" a '
            'JOIN "A股公司行业划分表" b ON a."股票代码" = b."股票代码" '
            f'AND b."交易日期" = "{trade_date}" '
            f'WHERE a."交易日" = "{trade_date}" '
            f'AND b."行业划分标准" = "{self._industry_standard(question)}" '
            f'AND b."{self._industry_level_column(question)}" = "{industry_name}" '
            'AND a."昨收盘(元)" > 0 '
            'AND ((a."收盘价(元)" - a."昨收盘(元)") / a."昨收盘(元)") > 0.05'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}涨幅超过5%的股票数量是{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_limit_up_days(self, question: str) -> FinancialAnswer | None:
        if "涨停天数" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        year = self._extract_year(question)
        if not stock_code or not year:
            return None
        start_date = f"{year}0101"
        end_date = f"{year}1231"
        sql = (
            'SELECT COUNT(*) AS cnt FROM "A股票日行情表" '
            f'WHERE "股票代码" = "{stock_code}" '
            f'AND "交易日" BETWEEN "{start_date}" AND "{end_date}" '
            'AND "昨收盘(元)" > 0 '
            'AND ("收盘价(元)" / "昨收盘(元)" - 1) >= 0.098'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"股票{stock_code}在{year}年度的涨停天数是{int(row['cnt'])}天。",
            sql=sql,
        )

    def _answer_industry_volume_sum(self, question: str) -> FinancialAnswer | None:
        if "成交量合计" not in question:
            return None
        trade_date = self._extract_first_date(question)
        industry_name = self._extract_industry_name(question)
        if not trade_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        sql = (
            'SELECT ROUND(SUM(a."成交量(股)"), 0) AS total_volume '
            'FROM "A股票日行情表" a '
            'JOIN "A股公司行业划分表" b ON a."股票代码" = b."股票代码" '
            f'AND b."交易日期" = "{trade_date}" '
            f'WHERE a."交易日" = "{trade_date}" '
            f'AND b."行业划分标准" = "{self._industry_standard(question)}" '
            f'AND b."{self._industry_level_column(question)}" = "{industry_name}"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}{industry_name}行业股票成交量合计是{int(row['total_volume'] or 0)}。",
            sql=sql,
        )

    def _answer_industry_amount_sum(self, question: str) -> FinancialAnswer | None:
        if "成交金额合计" not in question:
            return None
        trade_date = self._extract_first_date(question)
        industry_name = self._extract_industry_name(question)
        if not trade_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        sql = (
            'SELECT ROUND(SUM(a."成交金额(元)"), 0) AS total_amount '
            'FROM "A股票日行情表" a '
            'JOIN "A股公司行业划分表" b ON a."股票代码" = b."股票代码" '
            f'AND b."交易日期" = "{trade_date}" '
            f'WHERE a."交易日" = "{trade_date}" '
            f'AND b."行业划分标准" = "{self._industry_standard(question)}" '
            f'AND b."{self._industry_level_column(question)}" = "{industry_name}"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}{industry_name}行业股票成交金额合计是{int(row['total_amount'] or 0)}。",
            sql=sql,
        )

    def _answer_industry_amount_max_stock(self, question: str) -> FinancialAnswer | None:
        if "成交金额" not in question or "最多的股票的代码" not in question:
            return None
        trade_date = self._extract_first_date(question)
        industry_name = self._extract_industry_name(question)
        if not trade_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        sql = (
            'SELECT a."股票代码" AS stock_code, ROUND(a."成交金额(元)", 2) AS amount_value '
            'FROM "A股票日行情表" a '
            'JOIN "A股公司行业划分表" b ON a."股票代码" = b."股票代码" '
            f'AND b."交易日期" = "{trade_date}" '
            f'WHERE a."交易日" = "{trade_date}" '
            f'AND b."行业划分标准" = "{self._industry_standard(question)}" '
            f'AND b."{self._industry_level_column(question)}" = "{industry_name}" '
            'ORDER BY a."成交金额(元)" DESC, a."股票代码" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}{industry_name}行业成交金额最多的股票代码是{row['stock_code']}，成交金额是{self._format_number(float(row['amount_value']), 2)}元。",
            sql=sql,
        )

    def _answer_manager_fund_count(self, question: str) -> FinancialAnswer | None:
        if "成立了多少基金" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        year = self._extract_year(question)
        if not manager or not year:
            return None
        sql = (
            'SELECT COUNT(*) AS cnt FROM "基金基本信息" '
            f'WHERE "管理人" = "{self._escape(manager)}" '
            f'AND substr("成立日期", 1, 4) = "{year}"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{manager}在{year}年成立了{int(row['cnt'])}只基金。",
            sql=sql,
        )

    def _answer_manager_product_count(self, question: str) -> FinancialAnswer | None:
        if "产品的数量有多少" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        type_match = re.search(r"管理的(债券型|股票型|混合型|货币型|其他型)产品", question)
        if not manager or not type_match:
            return None
        fund_type = type_match.group(1)
        sql = (
            'SELECT COUNT(*) AS cnt FROM "基金基本信息" '
            f'WHERE "管理人" = "{self._escape(manager)}" AND "基金类型" = "{fund_type}"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{manager}管理的{fund_type}产品数量是{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_manager_low_fee_fund_count(self, question: str) -> FinancialAnswer | None:
        if "管理费率小于0.8%" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        year = self._extract_year(question)
        if not manager or not year:
            return None
        sql = (
            'SELECT COUNT(*) AS cnt FROM "基金基本信息" '
            f'WHERE "管理人" = "{self._escape(manager)}" '
            f'AND substr("成立日期", 1, 4) = "{year}" '
            'AND CAST(REPLACE("管理费率", "%", "") AS REAL) < 0.8'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{manager}在{year}年成立且管理费率小于0.8%的基金有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_manager_type_most(self, question: str) -> FinancialAnswer | None:
        if "成立哪种类型的基金个数最多" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        year = self._extract_year(question)
        if not manager or not year:
            return None
        sql = (
            'SELECT "基金类型" AS fund_type, COUNT(*) AS cnt '
            'FROM "基金基本信息" '
            f'WHERE "管理人" = "{self._escape(manager)}" '
            f'AND substr("成立日期", 1, 4) = "{year}" '
            'GROUP BY "基金类型" ORDER BY cnt DESC, "基金类型" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{manager}在{year}年成立数量最多的基金类型是{row['fund_type']}，共有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_net_redeem_summary(self, question: str) -> FinancialAnswer | None:
        if "净赎回" not in question:
            return None
        year = self._extract_year(question)
        report_date = self._fund_holding_report_date(question)
        if not year:
            return None
        if report_date:
            month_end = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
            sql = (
                'SELECT COUNT(*) AS cnt, ROUND(SUM("报告期基金总赎回份额" - "报告期基金总申购份额"), 2) AS total '
                'FROM "基金规模变动表" '
                f'WHERE date("截止日期") = date("{month_end}") '
                'AND "报告期基金总赎回份额" > "报告期基金总申购份额"'
            )
        else:
            sql = (
                'SELECT COUNT(*) AS cnt, ROUND(SUM("报告期基金总赎回份额" - "报告期基金总申购份额"), 2) AS total '
                'FROM "基金规模变动表" '
                f'WHERE "定期报告所属年度" = {year} '
                'AND "报告期基金总赎回份额" > "报告期基金总申购份额"'
            )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"发生净赎回的基金有{int(row['cnt'] or 0)}家，总共净赎回{float(row['total'] or 0):.2f}份。",
            sql=sql,
        )

    def _answer_net_subscribe_summary(self, question: str) -> FinancialAnswer | None:
        if "净申购" not in question:
            return None
        year = self._extract_year(question)
        report_date = self._fund_holding_report_date(question)
        if not year:
            return None
        if report_date:
            month_end = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
            sql = (
                'SELECT COUNT(*) AS cnt, ROUND(SUM("报告期基金总申购份额" - "报告期基金总赎回份额"), 2) AS total '
                'FROM "基金规模变动表" '
                f'WHERE date("截止日期") = date("{month_end}") '
                'AND "报告期基金总申购份额" > "报告期基金总赎回份额"'
            )
        else:
            sql = (
                'SELECT COUNT(*) AS cnt, ROUND(SUM("报告期基金总申购份额" - "报告期基金总赎回份额"), 2) AS total '
                'FROM "基金规模变动表" '
                f'WHERE "定期报告所属年度" = {year} '
                'AND "报告期基金总申购份额" > "报告期基金总赎回份额"'
            )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"净申购基金有{int(row['cnt'] or 0)}家，净申购份额合计{float(row['total'] or 0):.2f}份。",
            sql=sql,
        )

    def _answer_fund_nav(self, question: str) -> FinancialAnswer | None:
        if "资产净值和单位净值" not in question:
            return None
        return self._answer_fund_nav_and_unit(question)

    def _answer_fund_nav_and_unit(self, question: str) -> FinancialAnswer | None:
        if "资产净值" not in question or "单位净值" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        trade_date = self._extract_first_date(question)
        if not fund_name or not trade_date:
            return None
        sql = (
            'SELECT a."资产净值" AS asset_value, a."单位净值" AS unit_value '
            'FROM "基金日行情表" a '
            'JOIN "基金基本信息" b ON a."基金代码" = b."基金代码" '
            f'WHERE b."基金简称" = "{self._escape(fund_name)}" AND a."交易日期" = "{trade_date}" '
            'LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{trade_date}的资产净值是{self._format_number(float(row['asset_value']), 2)}，单位净值是{self._format_number(float(row['unit_value']), 4)}。",
            sql=sql,
        )

    def _answer_manager_and_nav(self, question: str) -> FinancialAnswer | None:
        if "请给出" not in question or ("累计单位净值" not in question and "单位净值" not in question) or "管理人" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        trade_date = self._extract_first_date(question)
        if not fund_name or not trade_date:
            return None
        nav_column = "累计单位净值" if "累计单位净值" in question else "单位净值"
        sql = (
            f'SELECT b."管理人" AS manager, a."{nav_column}" AS nav_value '
            'FROM "基金日行情表" a '
            'JOIN "基金基本信息" b ON a."基金代码" = b."基金代码" '
            f'WHERE b."基金简称" = "{self._escape(fund_name)}" AND a."交易日期" = "{trade_date}" '
            'LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{trade_date}的管理人是{row['manager']}，{nav_column}是{self._format_number(float(row['nav_value']), 4)}。",
            sql=sql,
        )

    def _answer_holder_more_count(self, question: str) -> FinancialAnswer | None:
        if "机构投资者持有份额比个人投资者多" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        year = self._extract_year(question)
        report_type = self._report_type_like(question, for_holder=True)
        if not manager or not year or not report_type:
            return None
        sql = (
            'SELECT COUNT(*) AS cnt '
            'FROM "基金份额持有人结构" h '
            'JOIN "基金基本信息" b ON h."基金代码" = b."基金代码" '
            f'WHERE b."管理人" = "{self._escape(manager)}" '
            f'AND h."定期报告所属年度" = {year} '
            f'AND h."报告类型" = "{report_type}" '
            'AND h."机构投资者持有的基金份额" > h."个人投资者持有的基金份额"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{year}年{report_type}里，{manager}管理的基金中，机构投资者持有份额比个人投资者多的基金有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_holder_personal_more_type_count(self, question: str) -> FinancialAnswer | None:
        if "个人投资者持有基金份额大于机构投资者持有基金份额的基金属于" not in question:
            return None
        year = self._extract_year(question)
        report_type = self._report_type_like(question, for_holder=True)
        type_match = re.search(r"基金属于(货币型|混合型|债券型|股票型|其他型)类型", question)
        if not year or not report_type or not type_match:
            return None
        fund_type = type_match.group(1)
        sql = (
            'SELECT COUNT(*) AS cnt '
            'FROM "基金份额持有人结构" h '
            'JOIN "基金基本信息" b ON h."基金代码" = b."基金代码" '
            f'WHERE h."定期报告所属年度" = {year} '
            f'AND h."报告类型" = "{report_type}" '
            f'AND b."基金类型" = "{fund_type}" '
            'AND h."个人投资者持有的基金份额" > h."机构投资者持有的基金份额"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{year}年{report_type}中，个人投资者持有份额大于机构投资者且属于{fund_type}的基金有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_holder_personal_more_ratio(self, question: str) -> FinancialAnswer | None:
        if "个人投资者持有的份额超过机构投资者" not in question or "比例" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        year = self._extract_year(question)
        report_type = self._report_type_like(question, for_holder=True)
        if not manager or not year or not report_type:
            return None
        sql = (
            'SELECT ROUND(100.0 * SUM(CASE WHEN h."个人投资者持有的基金份额" > h."机构投资者持有的基金份额" THEN 1 ELSE 0 END) / COUNT(*), 2) AS ratio_pct '
            'FROM "基金份额持有人结构" h '
            'JOIN "基金基本信息" b ON h."基金代码" = b."基金代码" '
            f'WHERE b."管理人" = "{self._escape(manager)}" '
            f'AND h."定期报告所属年度" = {year} '
            f'AND h."报告类型" = "{report_type}"'
        )
        row = self._execute_one(sql)
        if not row or row["ratio_pct"] is None:
            return None
        return FinancialAnswer(
            answer=f"{year}年{report_type}里，{manager}管理基金中个人投资者持有份额超过机构投资者的比例是{float(row['ratio_pct']):.2f}%。",
            sql=sql,
        )

    def _answer_holder_ratio_threshold_summary(self, question: str) -> FinancialAnswer | None:
        if "机构投资者持有的份额占比超过" not in question:
            return None
        year = self._extract_year(question)
        report_type = self._report_type_like(question, for_holder=True)
        threshold_match = re.search(r"占比超过(\d+)%", question)
        if not year or not report_type or not threshold_match:
            return None
        threshold = float(threshold_match.group(1))
        sql = (
            'SELECT COUNT(*) AS cnt, ROUND(SUM("机构投资者持有的基金份额"), 2) AS total_share '
            'FROM "基金份额持有人结构" '
            f'WHERE "定期报告所属年度" = {year} '
            f'AND "报告类型" = "{report_type}" '
            f'AND "机构投资者持有的基金份额占总份额比例" > {threshold}'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{year}年{report_type}中，机构投资者持有份额占比超过{int(threshold)}%的基金有{int(row['cnt'] or 0)}家，机构持有份额合计{float(row['total_share'] or 0):.2f}。",
            sql=sql,
        )

    def _answer_holder_personal_ratio_below_count(self, question: str) -> FinancialAnswer | None:
        if "个人投资者持有份额占比不足" not in question:
            return None
        year = self._extract_year(question)
        report_type = self._report_type_like(question, for_holder=True)
        threshold_match = re.search(r"不足(\d+)%", question)
        if not year or not report_type or not threshold_match:
            return None
        threshold = float(threshold_match.group(1))
        sql = (
            'SELECT COUNT(*) AS cnt '
            'FROM "基金份额持有人结构" '
            f'WHERE "定期报告所属年度" = {year} '
            f'AND "报告类型" = "{report_type}" '
            f'AND "个人投资者持有的基金份额占总份额比例" < {threshold}'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{year}年{report_type}中，个人投资者持有份额占比不足{int(threshold)}%的基金有{int(row['cnt'])}家。",
            sql=sql,
        )

    def _answer_mixed_fund_fee_avg(self, question: str) -> FinancialAnswer | None:
        if "平均值" not in question and "平均数" not in question:
            return None
        if "管理费率" not in question and "托管费率" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        year = self._extract_year(question)
        if not manager or not year:
            return None
        fee_column = "托管费率" if "托管费率" in question else "管理费率"
        sql = (
            f'SELECT ROUND(AVG(CAST(REPLACE("{fee_column}", "%", "") AS REAL)), 2) AS avg_fee '
            'FROM "基金基本信息" '
            f'WHERE "管理人" = "{self._escape(manager)}" '
            f'AND substr("成立日期", 1, 4) = "{year}" '
            + ('AND "基金类型" = "混合型" ' if "混合型基金" in question or "混合型" in question else "")
            + ('AND "托管人" = "中国民生银行股份有限公司" ' if "托管人为中国民生银行股份有限公司" in question else "")
        )
        row = self._execute_one(sql)
        if not row or row["avg_fee"] is None:
            return None
        return FinancialAnswer(
            answer=f"{manager}{year}年相关基金的{fee_column}平均值是{float(row['avg_fee']):.2f}%。",
            sql=sql,
        )

    def _answer_fund_fee_rate_or_custodian(self, question: str) -> FinancialAnswer | None:
        fund_code = self._extract_fund_code(question)
        if not fund_code:
            return None
        if "管理费率是" in question:
            sql = (
                'SELECT "管理费率" AS fee_rate FROM "基金基本信息" '
                f'WHERE "基金代码" = "{fund_code}" LIMIT 1'
            )
            row = self._execute_one(sql)
            if not row:
                return None
            return FinancialAnswer(
                answer=f"基金代码{fund_code}的管理费率是{row['fee_rate']}。",
                sql=sql,
            )
        if "托管人是" in question:
            sql = (
                'SELECT "托管人" AS custodian FROM "基金基本信息" '
                f'WHERE "基金代码" = "{fund_code}" LIMIT 1'
            )
            row = self._execute_one(sql)
            if not row:
                return None
            return FinancialAnswer(
                answer=f"基金代码{fund_code}的托管人是{row['custodian']}。",
                sql=sql,
            )
        if "基金类型是" in question or "基金类型" in question:
            sql = (
                'SELECT "基金类型" AS fund_type FROM "基金基本信息" '
                f'WHERE "基金代码" = "{fund_code}" LIMIT 1'
            )
            row = self._execute_one(sql)
            if not row:
                return None
            return FinancialAnswer(
                answer=f"基金代码{fund_code}的基金类型是{row['fund_type']}。",
                sql=sql,
            )
        return None

    def _answer_scale_growth_count(self, question: str) -> FinancialAnswer | None:
        if "报告期期初基金总份额小于报告期期末基金总份额" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        year = self._extract_year(question)
        if not manager or not year:
            return None
        sql = (
            'WITH latest AS ('
            '  SELECT s.* FROM "基金规模变动表" s '
            '  JOIN ('
            '    SELECT "基金代码", MAX(date("截止日期")) AS latest_date '
            '    FROM "基金规模变动表" '
            f'    WHERE "定期报告所属年度" = {year} '
            '    GROUP BY "基金代码"'
            '  ) t ON s."基金代码" = t."基金代码" AND date(s."截止日期") = t.latest_date '
            f'  WHERE s."定期报告所属年度" = {year}'
            ') '
            'SELECT COUNT(*) AS cnt '
            'FROM latest l JOIN "基金基本信息" b ON l."基金代码" = b."基金代码" '
            f'WHERE b."管理人" = "{self._escape(manager)}" '
            'AND l."报告期期初基金总份额" < l."报告期期末基金总份额"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{year}年{manager}已发行基金中，报告期期初基金总份额小于报告期期末基金总份额的有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_scale_drop_count(self, question: str) -> FinancialAnswer | None:
        if "基金总份额降低" not in question:
            return None
        report_date = self._fund_holding_report_date(question)
        if not report_date:
            return None
        report_date_fmt = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
        sql = (
            'SELECT COUNT(*) AS cnt FROM "基金规模变动表" '
            f'WHERE date("截止日期") = date("{report_date_fmt}") '
            'AND "报告期期末基金总份额" < "报告期期初基金总份额"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"截止{report_date}的报告期间，基金总份额降低的基金数量是{int(row['cnt'])}个。",
            sql=sql,
        )

    def _answer_heavy_holding_count(self, question: str) -> FinancialAnswer | None:
        if "市值占基金资产净值比不小于5%" not in question:
            return None
        stock_name = self._extract_stock_name(question)
        report_date = self._fund_holding_report_date(question)
        report_type = self._report_type_like(question)
        if not stock_name or not report_date or not report_type:
            return None
        sql = (
            'SELECT COUNT(DISTINCT "基金代码") AS cnt FROM "基金股票持仓明细" '
            f'WHERE "股票名称" = "{self._escape(stock_name)}" '
            f'AND "持仓日期" = "{report_date}" '
            f'AND "报告类型" = "{report_type}" '
            'AND "市值占基金资产净值比" >= 0.05'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{report_date}对应报告中，持有{stock_name}且市值占基金资产净值比不小于5%的基金有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_zero_redeem_count(self, question: str) -> FinancialAnswer | None:
        if "基金总赎回份额为零" not in question:
            return None
        report_date = self._fund_holding_report_date(question)
        if not report_date:
            return None
        report_date_fmt = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:]}"
        sql = (
            'SELECT COUNT(*) AS cnt FROM "基金规模变动表" '
            f'WHERE date("截止日期") = date("{report_date_fmt}") '
            'AND "报告期基金总赎回份额" = 0'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"截止{report_date}的基金定期报告中，基金总赎回份额为零的基金有{int(row['cnt'])}个。",
            sql=sql,
        )

    def _answer_report_diff_max_fund(self, question: str) -> FinancialAnswer | None:
        if "差额最大的一只基金" not in question:
            return None
        month = self._extract_month(question)
        if not month:
            return None
        sql = (
            'SELECT "基金简称" AS fund_name, '
            'ROUND(ABS("报告期基金总申购份额" - "报告期基金总赎回份额"), 2) AS diff_value '
            'FROM "基金规模变动表" '
            f'WHERE strftime("%Y%m", "截止日期") = "{month}" '
            'ORDER BY diff_value DESC, "基金代码" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{month}报告中，申购与赎回份额差额最大的基金简称是{row['fund_name']}，差额是{float(row['diff_value']):.2f}。",
            sql=sql,
        )

    def _answer_fund_type_top_bond_names(self, question: str) -> FinancialAnswer | None:
        if "前三大持仓占比的债券名称" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        report_type = self._report_type_like(question)
        if not fund_name or not report_date or not report_type:
            return None
        sql = (
            'SELECT "债券名称" AS bond_name '
            'FROM "基金债券持仓明细" '
            f'WHERE "基金简称" = "{self._escape(fund_name)}" '
            f'AND "持仓日期" = "{report_date}" '
            f'AND "报告类型" = "{report_type}" '
            'ORDER BY "市值占基金资产净值比" DESC, "债券名称" ASC LIMIT 3'
        )
        rows = self._execute_all(sql)
        if not rows:
            return None
        names = "、".join(row["bond_name"] for row in rows)
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}的{report_type}里，前三大持仓占比的债券名称分别是{names}。",
            sql=sql,
        )

    def _answer_bond_type_max(self, question: str) -> FinancialAnswer | None:
        if "持有最大仓位的债券类型" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        report_type = self._report_type_like(question)
        if not fund_name or not report_date or not report_type:
            return None
        sql = (
            'SELECT "债券类型" AS bond_type, SUM("持债市值") AS total_mv '
            'FROM "基金债券持仓明细" '
            f'WHERE "基金简称" = "{self._escape(fund_name)}" '
            f'AND "持仓日期" = "{report_date}" '
            f'AND "报告类型" = "{report_type}" '
            'GROUP BY "债券类型" ORDER BY total_mv DESC, "债券类型" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}的{report_type}中，持有最大仓位的债券类型是{row['bond_type']}。",
            sql=sql,
        )

    def _answer_bond_market_value_type_max(self, question: str) -> FinancialAnswer | None:
        if "哪类债券市值最高" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        report_type = self._report_type_like(question)
        if not fund_name or not report_date or not report_type:
            return None
        sql = (
            'SELECT "债券类型" AS bond_type, SUM("持债市值") AS total_mv '
            'FROM "基金债券持仓明细" '
            f'WHERE "基金简称" = "{self._escape(fund_name)}" '
            f'AND "持仓日期" = "{report_date}" '
            f'AND "报告类型" = "{report_type}" '
            'GROUP BY "债券类型" ORDER BY total_mv DESC, "债券类型" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}且报告类型为{report_type}的持债市值中，市值最高的债券类型是{row['bond_type']}。",
            sql=sql,
        )

    def _answer_convertible_max_industry(self, question: str) -> FinancialAnswer | None:
        if "可转债持仓占比最大" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        if not fund_name or not report_date:
            return None
        level = "一级行业名称" if "一级行业" in question else "二级行业名称"
        standard = self._industry_standard(question)
        sql = (
            f'SELECT i."{level}" AS industry_name, SUM(c."市值占基金资产净值比") AS total_ratio '
            'FROM "基金可转债持仓明细" c '
            'JOIN "A股公司行业划分表" i ON c."对应股票代码" = i."股票代码" '
            f'AND i."交易日期" = "{report_date}" '
            f'WHERE c."基金简称" = "{self._escape(fund_name)}" '
            f'AND c."持仓日期" = "{report_date}" '
            f'AND c."报告类型" = "{self._report_type_like(question)}" '
            f'AND i."行业划分标准" = "{standard}" '
            f'AND i."{level}" IS NOT NULL '
            'GROUP BY i."' + level + '" ORDER BY total_ratio DESC, industry_name ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}报告中，可转债持仓占比最大的{standard}{'一级' if level == '一级行业名称' else '二级'}行业是{row['industry_name']}。",
            sql=sql,
        )

    def _answer_manager_bond_holding_count(self, question: str) -> FinancialAnswer | None:
        if "持有过" not in question or "基金有多少只" not in question:
            return None
        manager = self._extract_company_name(question, "有限公司")
        year = self._extract_year(question)
        if not manager or not year:
            return None
        bond_type = None
        if "同业存单" in question:
            bond_type = "同业存单"
        elif "可交换公司债券" in question:
            bond_type = "可交换债"
        elif "可转换债券" in question:
            bond_type = "可转债"
        elif "国债现货" in question:
            bond_type = "国债"
        elif "非公开发行公司债" in question:
            bond_type = "公司债"
        if not bond_type:
            return None
        sql = (
            'SELECT COUNT(DISTINCT d."基金代码") AS cnt '
            'FROM "基金债券持仓明细" d '
            'JOIN "基金基本信息" b ON d."基金代码" = b."基金代码" '
            f'WHERE b."管理人" = "{self._escape(manager)}" '
            'AND b."基金类型" = "债券型" '
            f'AND substr(d."持仓日期", 1, 4) = "{year}" '
            f'AND d."债券类型" LIKE "%{bond_type}%"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{manager}在{year}年管理的债券型基金中，持有过{bond_type}的基金有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_top10_positive_return_count(self, question: str) -> FinancialAnswer | None:
        if "前10大重仓股中" not in question or "正收益" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        report_type = self._report_type_like(question)
        if not fund_name or not report_date or not report_type:
            return None
        quarter = self._quarter_bounds(question)
        if quarter is None:
            if report_date.endswith("0630"):
                quarter = (report_date[:4] + "0101", report_date)
            elif report_date.endswith("1231"):
                quarter = (report_date[:4] + "0101", report_date)
            else:
                quarter = None
        start_date, end_date = quarter if quarter else (report_date, report_date)
        sql = (
            'WITH holdings AS ('
            '  SELECT "股票代码", "股票名称" '
            '  FROM "基金股票持仓明细" '
            f'  WHERE "基金简称" = "{self._escape(fund_name)}" '
            f'  AND "持仓日期" = "{report_date}" '
            f'  AND "报告类型" = "{report_type}" '
            '  AND "第N大重仓股" <= 10'
            '), perf AS ('
            '  SELECT h."股票代码", '
            '  (SELECT "收盘价(元)" FROM "A股票日行情表" s WHERE s."股票代码" = h."股票代码" AND s."交易日" >= "' + start_date + '" ORDER BY s."交易日" ASC LIMIT 1) AS start_close, '
            '  (SELECT "收盘价(元)" FROM "A股票日行情表" e WHERE e."股票代码" = h."股票代码" AND e."交易日" <= "' + end_date + '" ORDER BY e."交易日" DESC LIMIT 1) AS end_close '
            '  FROM holdings h'
            ') '
            'SELECT COUNT(*) AS cnt FROM perf '
            'WHERE start_close IS NOT NULL AND end_close IS NOT NULL AND end_close > start_close'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}对应报告的前10大重仓股中，报告期内取得正收益的股票有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_top_n_stock_return(self, question: str) -> FinancialAnswer | None:
        if "第" not in question or "大重股" not in question or "涨跌幅" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        report_type = self._report_type_like(question)
        rank_match = re.search(r"第(\d+)大重股", question)
        quarter = self._quarter_bounds(question)
        if not fund_name or not report_date or not report_type or not rank_match or not quarter:
            return None
        rank = int(rank_match.group(1))
        start_date, end_date = quarter
        sql = (
            'WITH target AS ('
            '  SELECT "股票代码", "股票名称" FROM "基金股票持仓明细" '
            f'  WHERE "基金简称" = "{self._escape(fund_name)}" '
            f'  AND "持仓日期" = "{report_date}" '
            f'  AND "报告类型" = "{report_type}" '
            f'  AND "第N大重仓股" = {rank} LIMIT 1'
            ') '
            'SELECT t."股票代码" AS stock_code, t."股票名称" AS stock_name, '
            'ROUND((('
            f'  SELECT "收盘价(元)" FROM "A股票日行情表" WHERE "股票代码" = t."股票代码" AND "交易日" <= "{end_date}" ORDER BY "交易日" DESC LIMIT 1'
            ')-('
            f'  SELECT "收盘价(元)" FROM "A股票日行情表" WHERE "股票代码" = t."股票代码" AND "交易日" >= "{start_date}" ORDER BY "交易日" ASC LIMIT 1'
            ')) / ('
            f'  SELECT "收盘价(元)" FROM "A股票日行情表" WHERE "股票代码" = t."股票代码" AND "交易日" >= "{start_date}" ORDER BY "交易日" ASC LIMIT 1'
            ') * 100, 2) AS change_pct '
            'FROM target t'
        )
        row = self._execute_one(sql)
        if not row or row["change_pct"] is None:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}对应报告中的第{rank}大重仓股是{row['stock_name']}（{row['stock_code']}），该股票当季度涨跌幅是{float(row['change_pct']):.2f}%。",
            sql=sql,
        )

    def _answer_top_n_holding_stock_code(self, question: str) -> FinancialAnswer | None:
        if "第" not in question or "大重仓股的代码" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        report_type = self._report_type_like(question)
        rank_match = re.search(r"第(\d+)大重仓股的代码", question)
        if not fund_name or not report_date or not report_type or not rank_match:
            return None
        rank = int(rank_match.group(1))
        sql = (
            'SELECT "股票代码" AS stock_code FROM "基金股票持仓明细" '
            f'WHERE "基金简称" = "{self._escape(fund_name)}" '
            f'AND "持仓日期" = "{report_date}" '
            f'AND "报告类型" = "{report_type}" '
            f'AND "第N大重仓股" = {rank} LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}对应报告中的第{rank}大重仓股代码是{row['stock_code']}。",
            sql=sql,
        )

    def _answer_top_n_holding_stock_code_name(self, question: str) -> FinancialAnswer | None:
        if "第" not in question or "大重仓股的代码和股票名称" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        report_type = self._report_type_like(question)
        rank_match = re.search(r"第([一二三四五六七八九十0-9]+)大重仓股", question)
        if not fund_name or not report_date or not report_type or not rank_match:
            return None
        zh_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        rank_token = rank_match.group(1)
        rank = int(rank_token) if rank_token.isdigit() else zh_map.get(rank_token, 1)
        sql = (
            'SELECT "股票代码" AS stock_code, "股票名称" AS stock_name FROM "基金股票持仓明细" '
            f'WHERE "基金简称" = "{self._escape(fund_name)}" '
            f'AND "持仓日期" = "{report_date}" '
            f'AND "报告类型" = "{report_type}" '
            f'AND "第N大重仓股" = {rank} LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}对应报告中的第{rank}大重仓股代码是{row['stock_code']}，股票名称是{row['stock_name']}。",
            sql=sql,
        )

    def _answer_top_n_market_count(self, question: str) -> FinancialAnswer | None:
        if "持有市值最多的前10只股票中" not in question or "所在证券市场是" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        market_match = re.search(r"所在证券市场是([\u4e00-\u9fffA-Za-z]+)的有几个", question)
        if not fund_name or not report_date or not market_match:
            return None
        market = market_match.group(1)
        sql = (
            'SELECT COUNT(*) AS cnt FROM "基金股票持仓明细" '
            f'WHERE "基金简称" = "{self._escape(fund_name)}" '
            f'AND "持仓日期" = "{report_date}" '
            'AND "第N大重仓股" <= 10 '
            f'AND "所在证券市场" = "{market}"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}前10只市值最多股票中，所在证券市场是{market}的有{int(row['cnt'])}个。",
            sql=sql,
        )

    def _answer_top_n_same_bond_count(self, question: str) -> FinancialAnswer | None:
        if "第一大重仓可转债同期还有多少只基金也进行了持仓" not in question:
            return None
        fund_code = self._extract_fund_code(question)
        report_date = self._fund_holding_report_date(question)
        if not fund_code or not report_date:
            return None
        sql = (
            'WITH target AS ('
            '  SELECT "债券名称" AS bond_name FROM "基金可转债持仓明细" '
            f'  WHERE "基金代码" = "{fund_code}" AND "持仓日期" = "{report_date}" '
            '  AND "第N大重仓股" = 1 LIMIT 1'
            ') '
            'SELECT COUNT(DISTINCT c."基金代码") - 1 AS cnt '
            'FROM "基金可转债持仓明细" c JOIN target t ON c."债券名称" = t.bond_name '
            f'WHERE c."持仓日期" = "{report_date}"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        count = max(int(row["cnt"] or 0), 0)
        return FinancialAnswer(
            answer=f"{fund_code}基金第一大重仓可转债在同期还有{count}只基金也进行了持仓。",
            sql=sql,
        )

    def _answer_stock_in_top_n_count(self, question: str) -> FinancialAnswer | None:
        if "在多少只基金的前" not in question:
            return None
        stock_name = self._extract_stock_name(question)
        report_date = self._fund_holding_report_date(question)
        rank_match = re.search(r"前([一二三四五六七八九十0-9]+)大重仓股", question)
        if not stock_name or not report_date or not rank_match:
            return None
        zh_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        token = rank_match.group(1)
        rank = int(token) if token.isdigit() else zh_map.get(token, 10)
        sql = (
            'SELECT COUNT(DISTINCT "基金代码") AS cnt FROM "基金股票持仓明细" '
            f'WHERE "股票名称" = "{self._escape(stock_name)}" '
            f'AND "持仓日期" = "{report_date}" '
            f'AND "第N大重仓股" <= {rank}'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{stock_name}在{report_date}出现在{int(row['cnt'])}只基金的前{rank}大重仓股中。",
            sql=sql,
        )

    def _answer_top20_avg_market_value_by_industry(self, question: str) -> FinancialAnswer | None:
        if "前20大重仓股票中属于" not in question or "平均市值" not in question:
            return None
        fund_code = self._extract_fund_code(question)
        report_date = self._fund_holding_report_date(question)
        industry_name = self._extract_industry_name(question)
        if not fund_code or not report_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        standard = self._industry_standard(question)
        sql = (
            'SELECT ROUND(AVG(h."市值"), 3) AS avg_mv '
            'FROM "基金股票持仓明细" h '
            'JOIN "A股公司行业划分表" i ON h."股票代码" = i."股票代码" '
            f'AND i."交易日期" = "{report_date}" '
            f'WHERE h."基金代码" = "{fund_code}" '
            f'AND h."持仓日期" = "{report_date}" '
            'AND h."第N大重仓股" <= 20 '
            f'AND i."行业划分标准" = "{standard}" '
            f'AND i."{self._industry_level_column(question)}" = "{industry_name}"'
        )
        row = self._execute_one(sql)
        if not row or row["avg_mv"] is None:
            return None
        return FinancialAnswer(
            answer=f"基金{fund_code}在{report_date}前20大重仓股票中，属于{industry_name}行业的平均市值是{self._format_number(float(row['avg_mv']), 3)}。",
            sql=sql,
        )

    def _answer_fund_stock_industry_list(self, question: str) -> FinancialAnswer | None:
        if "投资的股票分别是哪些申万一级行业" not in question:
            return None
        fund_name = self._extract_fund_name(question)
        report_date = self._fund_holding_report_date(question)
        if not fund_name or not report_date:
            return None
        sql = (
            'SELECT DISTINCT i."一级行业名称" AS industry_name '
            'FROM "基金股票持仓明细" h '
            'JOIN "A股公司行业划分表" i ON h."股票代码" = i."股票代码" '
            f'AND i."交易日期" = "{report_date}" '
            f'WHERE h."基金简称" = "{self._escape(fund_name)}" '
            f'AND h."持仓日期" = "{report_date}" '
            'AND i."行业划分标准" = "申万行业分类" '
            'AND i."一级行业名称" IS NOT NULL '
            'ORDER BY i."一级行业名称"'
        )
        rows = self._execute_all(sql)
        if not rows:
            return None
        industries = "、".join(row["industry_name"] for row in rows)
        return FinancialAnswer(
            answer=f"{fund_name}在{report_date}报告里投资的股票涉及的申万一级行业有：{industries}。",
            sql=sql,
        )

    def _answer_latest_industry_level2(self, question: str) -> FinancialAnswer | None:
        if "申万行业分类下的二级行业是什么" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        if not stock_code:
            return None
        sql = (
            'SELECT "二级行业名称" AS industry_name, "交易日期" AS trade_date '
            'FROM "A股公司行业划分表" '
            f'WHERE "股票代码" = "{stock_code}" AND "行业划分标准" = "申万行业分类" '
            'AND "二级行业名称" IS NOT NULL '
            'ORDER BY "交易日期" DESC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"股票{stock_code}在最新申万行业分类数据中的二级行业是{row['industry_name']}（交易日期{row['trade_date']}）。",
            sql=sql,
        )

    def _answer_stock_industry_on_date(self, question: str) -> FinancialAnswer | None:
        if "属于哪个一级行业" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        trade_date = self._extract_first_date(question)
        if not stock_code or not trade_date:
            return None
        sql = (
            'SELECT "一级行业名称" AS industry_name '
            'FROM "A股公司行业划分表" '
            f'WHERE "股票代码" = "{stock_code}" '
            f'AND "交易日期" = "{trade_date}" '
            f'AND "行业划分标准" = "{self._industry_standard(question)}" '
            'LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"股票代码{stock_code}在{trade_date}按{self._industry_standard(question)}标准属于{row['industry_name']}一级行业。",
            sql=sql,
        )

    def _answer_industry_company_count(self, question: str) -> FinancialAnswer | None:
        if "行业的A股公司有多少" not in question and "一级行业有多少只A股股票" not in question:
            return None
        trade_date = self._extract_first_date(question)
        industry_name = self._extract_industry_name(question)
        if not trade_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        sql = (
            'SELECT COUNT(DISTINCT "股票代码") AS cnt FROM "A股公司行业划分表" '
            f'WHERE "交易日期" = "{trade_date}" '
            f'AND "行业划分标准" = "{self._industry_standard(question)}" '
            f'AND "{self._industry_level_column(question)}" = "{industry_name}"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}{industry_name}行业的A股公司有{int(row['cnt'])}家。",
            sql=sql,
        )

    def _answer_industry_company_most(self, question: str) -> FinancialAnswer | None:
        if "A股公司数量最多" not in question:
            return None
        trade_date = self._extract_first_date(question)
        if not trade_date:
            return None
        sql = (
            'SELECT "一级行业名称" AS industry_name, COUNT(DISTINCT "股票代码") AS cnt '
            'FROM "A股公司行业划分表" '
            f'WHERE "交易日期" = "{trade_date}" '
            f'AND "行业划分标准" = "{self._industry_standard(question)}" '
            'AND "一级行业名称" IS NOT NULL '
            'GROUP BY "一级行业名称" ORDER BY cnt DESC, "一级行业名称" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}按{self._industry_standard(question)}标准，A股公司数量最多的一级行业是{row['industry_name']}，共有{int(row['cnt'])}家。",
            sql=sql,
        )

    def _answer_daily_return_best_stock(self, question: str) -> FinancialAnswer | None:
        if "日均收益率最高" not in question:
            return None
        year = self._extract_year(question)
        industry_name = self._extract_industry_name(question)
        if not year or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        start_date = f"{year}0101"
        end_date = f"{year}1231"
        sql = (
            'WITH industry_stocks AS ('
            '  SELECT DISTINCT "股票代码" FROM "A股公司行业划分表" '
            f'  WHERE "交易日期" BETWEEN "{start_date}" AND "{end_date}" '
            f'  AND "行业划分标准" = "{self._industry_standard(question)}" '
            f'  AND "一级行业名称" = "{industry_name}"'
            ') '
            'SELECT a."股票代码" AS stock_code, '
            'AVG((a."收盘价(元)" - a."昨收盘(元)") / a."昨收盘(元)") AS avg_return '
            'FROM "A股票日行情表" a '
            'JOIN industry_stocks s ON a."股票代码" = s."股票代码" '
            f'WHERE a."交易日" BETWEEN "{start_date}" AND "{end_date}" '
            'AND a."昨收盘(元)" > 0 '
            'GROUP BY a."股票代码" ORDER BY avg_return DESC, a."股票代码" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{year}年{industry_name}一级行业里，日均收益率最高的股票代码是{row['stock_code']}。",
            sql=sql,
        )

    def _answer_industry_amount_avg(self, question: str) -> FinancialAnswer | None:
        if "平均成交金额" not in question:
            return None
        trade_date = self._extract_first_date(question)
        industry_name = self._extract_industry_name(question)
        if not trade_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        sql = (
            'SELECT ROUND(AVG(a."成交金额(元)"), 5) AS avg_amount '
            'FROM "A股票日行情表" a '
            'JOIN "A股公司行业划分表" i ON a."股票代码" = i."股票代码" '
            f'AND i."交易日期" = "{trade_date}" '
            f'WHERE a."交易日" = "{trade_date}" '
            f'AND i."行业划分标准" = "{self._industry_standard(question)}" '
            f'AND i."{self._industry_level_column(question)}" = "{industry_name}"'
        )
        row = self._execute_one(sql)
        if not row or row["avg_amount"] is None:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}{industry_name}行业A股股票的平均成交金额是{float(row['avg_amount']):.5f}。",
            sql=sql,
        )

    def _answer_industry_volatility_max(self, question: str) -> FinancialAnswer | None:
        if "收盘价波动最大" not in question:
            return None
        trade_date = self._extract_first_date(question)
        industry_name = self._extract_industry_name(question)
        if not trade_date or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        sql = (
            'SELECT a."股票代码" AS stock_code, '
            'ROUND(a."最高价(元)" - a."最低价(元)", 3) AS amplitude '
            'FROM "A股票日行情表" a '
            'JOIN "A股公司行业划分表" i ON a."股票代码" = i."股票代码" '
            f'AND i."交易日期" = "{trade_date}" '
            f'WHERE a."交易日" = "{trade_date}" '
            f'AND i."行业划分标准" = "{self._industry_standard(question)}" '
            f'AND i."一级行业名称" = "{industry_name}" '
            'ORDER BY amplitude DESC, a."股票代码" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}{industry_name}一级行业中，收盘价波动最大的股票代码是{row['stock_code']}，波动值是{self._format_number(float(row['amplitude']), 3)}。",
            sql=sql,
        )

    def _answer_industry_daily_volatility_min(self, question: str) -> FinancialAnswer | None:
        if "日均波动值最小" not in question:
            return None
        year = self._extract_year(question)
        industry_name = self._extract_industry_name(question)
        if not year or not industry_name:
            return None
        industry_name = self._resolve_industry_name(question, industry_name)
        sql = (
            'SELECT a."股票代码" AS stock_code, AVG(a."最高价(元)" - a."最低价(元)") AS avg_amp '
            'FROM "A股票日行情表" a '
            'JOIN "A股公司行业划分表" i ON a."股票代码" = i."股票代码" '
            'AND substr(a."交易日", 1, 4) = substr(i."交易日期", 1, 4) '
            f'WHERE substr(a."交易日", 1, 4) = "{year}" '
            f'AND i."行业划分标准" = "{self._industry_standard(question)}" '
            f'AND i."一级行业名称" = "{industry_name}" '
            'GROUP BY a."股票代码" ORDER BY avg_amp ASC, a."股票代码" ASC LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{year}年{industry_name}一级行业中，股票日均波动值最小的股票代码是{row['stock_code']}。",
            sql=sql,
        )

    def _answer_open_gt_prev_close_days(self, question: str) -> FinancialAnswer | None:
        if "今开盘高于昨收盘的天数" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        year = self._extract_year(question)
        if not stock_code or not year:
            return None
        start_date = f"{year}0101"
        end_date = f"{year}1231"
        sql = (
            'SELECT COUNT(*) AS cnt FROM "A股票日行情表" '
            f'WHERE "股票代码" = "{stock_code}" '
            f'AND "交易日" BETWEEN "{start_date}" AND "{end_date}" '
            'AND "今开盘(元)" > "昨收盘(元)"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"股票{stock_code}在{year}年今开盘高于昨收盘的天数是{int(row['cnt'])}天。",
            sql=sql,
        )

    def _answer_open_gt_prev_high_count(self, question: str) -> FinancialAnswer | None:
        if "开盘价较上一交易日最高价高的股票" not in question:
            return None
        trade_date = self._extract_first_date(question)
        if not trade_date:
            return None
        sql = (
            'SELECT COUNT(*) AS cnt FROM "A股票日行情表" '
            f'WHERE "交易日" = "{trade_date}" '
            'AND "今开盘(元)" > "最高价(元)"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}开盘价较上一交易日最高价高的股票有{int(row['cnt'])}只。",
            sql=sql,
        )

    def _answer_low_volume_days(self, question: str) -> FinancialAnswer | None:
        if "日成交量低于该股票当年平均日成交量" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        year = self._extract_year(question)
        if not stock_code or not year:
            return None
        start_date = f"{year}0101"
        end_date = f"{year}1231"
        sql = (
            'WITH avg_vol AS ('
            '  SELECT AVG("成交量(股)") AS avg_volume FROM "A股票日行情表" '
            f'  WHERE "股票代码" = "{stock_code}" AND "交易日" BETWEEN "{start_date}" AND "{end_date}"'
            ') '
            'SELECT COUNT(*) AS cnt FROM "A股票日行情表", avg_vol '
            f'WHERE "股票代码" = "{stock_code}" AND "交易日" BETWEEN "{start_date}" AND "{end_date}" '
            'AND "成交量(股)" < avg_volume'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"股票{stock_code}在{year}年内日成交量低于当年平均日成交量的交易日有{int(row['cnt'])}个。",
            sql=sql,
        )

    def _answer_top3_amount_codes(self, question: str) -> FinancialAnswer | None:
        if "成交金额最大的前三家上市公司" not in question:
            return None
        trade_date = self._extract_first_date(question)
        if not trade_date:
            return None
        sql = (
            'SELECT "股票代码" AS stock_code FROM "A股票日行情表" '
            f'WHERE "交易日" = "{trade_date}" '
            'ORDER BY "成交金额(元)" DESC, "股票代码" ASC LIMIT 3'
        )
        rows = self._execute_all(sql)
        if not rows:
            return None
        codes = "、".join(row["stock_code"] for row in rows)
        return FinancialAnswer(
            answer=f"{trade_date}成交金额最大的前三家上市公司股票代码依次是：{codes}。",
            sql=sql,
        )

    def _answer_highest_close_price(self, question: str) -> FinancialAnswer | None:
        if "最高日收盘价" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        year = self._extract_year(question)
        if not stock_code or not year:
            return None
        start_date = f"{year}0101"
        end_date = f"{year}1231"
        sql = (
            'SELECT ROUND(MAX("收盘价(元)"), 3) AS max_close FROM "A股票日行情表" '
            f'WHERE "股票代码" = "{stock_code}" AND "交易日" BETWEEN "{start_date}" AND "{end_date}"'
        )
        row = self._execute_one(sql)
        if not row or row["max_close"] is None:
            return None
        return FinancialAnswer(
            answer=f"股票{stock_code}在{year}年内最高日收盘价是{float(row['max_close']):.3f}。",
            sql=sql,
        )

    def _answer_annualized_return(self, question: str) -> FinancialAnswer | None:
        if "年化收益率" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        year = self._extract_year(question)
        if not stock_code or not year:
            return None
        start_date = f"{year}0101"
        end_date = f"{year}1231"
        sql = (
            'WITH prices AS ('
            f'  SELECT (SELECT "今开盘(元)" FROM "A股票日行情表" WHERE "股票代码" = "{stock_code}" AND "交易日" BETWEEN "{start_date}" AND "{end_date}" ORDER BY "交易日" ASC LIMIT 1) AS start_open, '
            f'         (SELECT "收盘价(元)" FROM "A股票日行情表" WHERE "股票代码" = "{stock_code}" AND "交易日" BETWEEN "{start_date}" AND "{end_date}" ORDER BY "交易日" DESC LIMIT 1) AS end_close'
            ') '
            'SELECT ROUND((end_close - start_open) / start_open * 100, 2) AS annual_return FROM prices'
        )
        row = self._execute_one(sql)
        if not row or row["annual_return"] is None:
            return None
        return FinancialAnswer(
            answer=f"股票{stock_code}在{year}年的年化收益率是{float(row['annual_return']):.2f}%。",
            sql=sql,
        )

    def _answer_hk_down_count(self, question: str) -> FinancialAnswer | None:
        if "港股下跌的股票家数" not in question:
            return None
        trade_date = self._extract_first_date(question)
        if not trade_date:
            return None
        sql = (
            'SELECT COUNT(*) AS cnt FROM "港股票日行情表" '
            f'WHERE "交易日" = "{trade_date}" AND "收盘价(元)" < "昨收盘(元)"'
        )
        row = self._execute_one(sql)
        if not row:
            return None
        return FinancialAnswer(
            answer=f"{trade_date}港股下跌的股票家数有{int(row['cnt'])}家。",
            sql=sql,
        )

    def _answer_hk_amplitude(self, question: str) -> FinancialAnswer | None:
        if "港股日价格振幅" not in question:
            return None
        stock_code = self._extract_stock_code(question)
        trade_date = self._extract_first_date(question)
        if not stock_code or not trade_date:
            return None
        sql = (
            'SELECT ROUND(("最高价(元)" - "最低价(元)") / "昨收盘(元)", 3) AS amp '
            'FROM "港股票日行情表" '
            f'WHERE "股票代码" = "{stock_code}" AND "交易日" = "{trade_date}" '
            'AND "昨收盘(元)" > 0 LIMIT 1'
        )
        row = self._execute_one(sql)
        if not row or row["amp"] is None:
            return None
        return FinancialAnswer(
            answer=f"港股{stock_code}在{trade_date}的日价格振幅是{float(row['amp']):.3f}。",
            sql=sql,
        )
    CITIC_LEVEL1 = {
        "交通运输", "传媒", "农林牧渔", "医药", "商贸零售", "国防军工", "基础化工",
        "家电", "建材", "建筑", "房地产", "有色金属", "机械", "汽车", "消费者服务",
        "煤炭", "电力及公用事业", "电力设备", "电力设备及新能源", "电子", "电子元器件",
        "石油石化", "纺织服装", "综合", "综合金融", "计算机", "轻工制造", "通信",
        "钢铁", "银行", "非银行金融", "食品饮料", "餐饮旅游",
    }
    SW_LEVEL1 = {
        "交通运输", "休闲服务", "传媒", "公用事业", "农林牧渔", "化工", "医药生物", "商业贸易",
        "国防军工", "家用电器", "建筑材料", "建筑装饰", "房地产", "有色金属", "机械设备",
        "汽车", "电子", "电气设备", "纺织服装", "综合", "计算机", "轻工制造", "通信",
        "采掘", "钢铁", "银行", "非银金融", "食品饮料",
    }
    CITIC_ALIAS = {
        "建筑材料": "建材",
        "非银金融": "非银行金融",
        "公用事业": "电力及公用事业",
        "机械设备": "机械",
        "家用电器": "家电",
        "医药生物": "医药",
        "商业贸易": "商贸零售",
        "休闲服务": "消费者服务",
        "电气设备": "电力设备",
        "采掘": "煤炭",
        "建筑装饰": "建筑",
    }
    SW_ALIAS = {
        "建材": "建筑材料",
        "非银行金融": "非银金融",
        "电力及公用事业": "公用事业",
        "机械": "机械设备",
        "家电": "家用电器",
        "医药": "医药生物",
        "商贸零售": "商业贸易",
        "消费者服务": "休闲服务",
        "电力设备": "电气设备",
        "煤炭": "采掘",
        "建筑": "建筑装饰",
        "餐饮旅游": "休闲服务",
    }

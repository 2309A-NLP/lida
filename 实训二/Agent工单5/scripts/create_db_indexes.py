"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import sqlite3


STATEMENTS = [
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


def main() -> None:
    conn = sqlite3.connect("dataset_raw/financial_data.db")
    for statement in STATEMENTS:
        conn.execute(statement)
    conn.commit()
    print(f"created_or_verified={len(STATEMENTS)}")


if __name__ == "__main__":
    main()

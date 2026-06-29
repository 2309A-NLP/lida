"""
工单编号：人工智能NLP-Agent数字人项目-记账本任务
记账本Agent - 业务逻辑（基于关键词，不依赖LLM）
"""
import re
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from backend.money_database import get_money_db

MEMBERS = ["爸爸", "妈妈", "女儿"]
MEMBER_ALIASES = {
    "爸": "爸爸", "父亲": "爸爸", "老爸": "爸爸", "爹": "爸爸",
    "妈": "妈妈", "母亲": "妈妈", "老妈": "妈妈", "娘": "妈妈",
    "闺女": "女儿", "孩子": "女儿", "丫头": "女儿"
}
CATEGORIES = ["买书", "吃饭", "交通", "购物", "娱乐", "教育", "医疗", "住房", "工资", "报销", "红包", "其他"]
INCOME_KEYWORDS = ["工资", "奖金", "报销", "收到", "红包", "转账", "退款", "收入"]

pending = {}


def _parse_member(text):
    for alias, name in MEMBER_ALIASES.items():
        if alias in text:
            return name
    for m in MEMBERS:
        if m in text:
            return m
    return None


def _parse_amount(text):
    # 先移除日期部分（如"7月5日"、"昨天"等），避免误匹配日期数字
    text_no_date = re.sub(r'\d{1,2}月\d{1,2}日?', '', text)
    text_no_date = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日?', '', text_no_date)

    # 找所有带"元/块"的数字
    matches_with_unit = re.findall(r'(\d+(?:\.\d+)?)\s*(?:元|块|円)', text_no_date)
    if matches_with_unit:
        # 取最大的金额（避免误匹配小数字）
        return max(float(m) for m in matches_with_unit)

    # 没有单位时，找所有数字，取最大且大于10的
    matches = re.findall(r'\d+(?:\.\d+)?', text_no_date)
    nums = [float(m) for m in matches]
    large = [n for n in nums if n >= 10]
    if large:
        return max(large)
    if nums:
        return max(nums)
    return None


def _parse_date(text):
    today = date.today()
    if "昨天" in text:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    if "前天" in text:
        return (today - timedelta(days=2)).strftime("%Y-%m-%d")
    if "明天" in text:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    m = re.search(r'(\d{1,2})月(\d{1,2})日?', text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        try:
            d = date(today.year, month, day)
            if d > today:
                d = date(today.year - 1, month, day)
            return d.strftime("%Y-%m-%d")
        except:
            pass

    return today.strftime("%Y-%m-%d")


def _parse_type(text):
    for kw in INCOME_KEYWORDS:
        if kw in text:
            return "收入"
    return "支出"


def _infer_category(text):
    mapping = {
        "书": "买书", "课": "教育", "学": "教育",
        "饭": "吃饭", "餐": "吃饭", "食": "吃饭",
        "车": "交通", "票": "交通", "路": "交通",
        "衣": "购物", "鞋": "购物", "包": "购物", "买": "购物",
        "医": "医疗", "药": "医疗", "院": "医疗",
        "房": "住房", "租": "住房",
        "工资": "工资", "报销": "报销", "红包": "红包",
        "电影": "娱乐", "游戏": "娱乐", "玩": "娱乐"
    }
    for kw, cat in mapping.items():
        if kw in text:
            return cat
    return "其他"


def _extract_item(text):
    text = re.sub(r'(今天|昨天|前天|明天|\d{1,2}月\d{1,2}日?)', '', text)
    text = re.sub(r'(爸爸|妈妈|女儿|爸|妈|父亲|母亲|老爸|老妈|闺女|孩子|丫头)', '', text)
    text = re.sub(r'(买了?|花了?|支出|收入|收到|工资|报销|红包)', '', text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:元|块)?', '', text)
    text = re.sub(r'[，。,.、\s]+', '', text)
    return text.strip() or "消费"


def process_money_message(text: str) -> str:
    text = text.strip()
    db = get_money_db()
    today = date.today()

    # 确认/取消
    if text in ("确认", "确定", "好", "是"):
        if "record" in pending:
            rec = pending.pop("record")
            db.add_record(**rec)
            return f"✅ 已记录：{rec['date_str']}，{rec['member']}，{rec['item']}，{rec['type_']}{rec['amount']}元"
        return "没有待确认的记录"
    if text in ("取消", "不", "算了"):
        pending.clear()
        return "❌ 已取消"
    if text in ("确认删除",):
        if "delete" in pending:
            rec = pending.pop("delete")
            db.delete_record(rec["id"])
            return f"✅ 已删除：{rec['date']}，{rec['member']}，{rec['item']}，{rec['amount']}元"
        return "没有待确认的删除"

    # 查询意图
    if any(kw in text for kw in ["花了多少", "明细", "记录", "汇总", "花了多钱", "消费"]):
        member = _parse_member(text)
        month_match = re.search(r'(\d+)月', text)
        if month_match:
            month = int(month_match.group(1))
            year = today.year
        else:
            year, month = today.year, today.month
        start = f"{year}-{month:02d}-01"
        end = f"{year}-{month:02d}-31"
        records = db.query_by_date_range(start, end, member)
        summary = db.get_summary(start, end, member)
        title = f"{year}年{month}月{''.join([member or '家庭'])}消费明细"
        if not records:
            return f"{title}：暂无记录"
        lines = [f"📊 {title}", f"总收入：{summary['收入']}元", f"总支出：{summary['支出']}元", f"净收入：{summary['净收入']}元", ""]
        for r in records[:10]:
            sign = "+" if r["type"] == "收入" else "-"
            lines.append(f"• {r['date']}，{r['member']}，{r['item']}，{sign}{r['amount']}元")
        if len(records) > 10:
            lines.append(f"...还有{len(records)-10}条")
        return "\n".join(lines)

    # 删除意图
    if any(kw in text for kw in ["删除", "去掉", "取消记录"]):
        item = _extract_item(text)
        records = db.query_by_item(item)
        if not records:
            return f"没有找到关于「{item}」的记录"
        rec = records[0]
        pending["delete"] = rec
        return f"⚠️ 确认删除：{rec['date']}，{rec['member']}，{rec['item']}，{rec['amount']}元\n回复「确认删除」确认，「取消」取消"

    # 清空意图
    if any(kw in text for kw in ["清空", "全部删除", "清除所有"]):
        records = db.query_by_date_range("2000-01-01", "2099-12-31")
        if not records:
            return "当前没有记录"
        return f"⚠️ 确认清空所有{len(records)}条记录？此操作不可恢复！\n回复「确认」确认，「取消」取消"

    # 记账意图（默认）
    amount = _parse_amount(text)
    if amount:
        member = _parse_member(text) or "我"
        date_str = _parse_date(text)
        type_ = _parse_type(text)
        category = _infer_category(text)
        item = _extract_item(text) or category

        pending["record"] = dict(date_str=date_str, member=member, category=category, item=item, amount=amount, type_=type_)
        return (f"📋 确认记录：\n"
                f"• 日期：{date_str}\n"
                f"• 成员：{member}\n"
                f"• 类别：{category}\n"
                f"• 项目：{item}\n"
                f"• {type_}：{amount}元\n"
                f"\n回复「确认」保存，「取消」放弃")

    return ("我可以帮您记账！请按格式输入：\n"
            "• 今天女儿买了双登山鞋499元\n"
            "• 7月5日妈妈收到报销1000元\n"
            "• 查询本月消费明细\n"
            "• 删除登山鞋记录")

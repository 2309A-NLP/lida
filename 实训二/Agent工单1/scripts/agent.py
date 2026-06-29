#!/usr/bin/env python3
"""
工单编号：人工智能NLP-Agent数字人项目-记账本任务
记账本Agent - 大模型驱动核心模块

功能：
1. 调用LLM理解用户自然语言输入
2. 结构化提取：意图、日期、成员、类别、金额、类型
3. 完整性引导：不完整信息引导补充
4. 确认流程：存储/删除前确认
5. 调用数据库进行增删改查
"""

import re
import json
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from database import get_db

# ============ LLM 配置 ============
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "tp-cxit9r7gak3n335w1vewzxjadh7f8d34ahecucld7514moj9")
LLM_MODEL = os.environ.get("LLM_MODEL", "mimo-v2.5-pro")

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

# ============ 开场白 ============
OPENING_MESSAGE = (
    "您好，欢迎使用咱们小家专属记账本！\n"
    '请按照"x年x月x日，谁做什么事收入/支出多少钱"的格式来输入。\n'
    "请告诉我你的账目需求吧~"
)

# ============ 成员信息 ============
MEMBERS = ["爸爸", "妈妈", "女儿"]

# ============ 系统提示词 ============
SYSTEM_PROMPT = """你是一个家庭记账本智能体。你的任务是理解用户的自然语言输入，并返回结构化的JSON。

## 你能做的事
1. **记账**：记录家庭成员的消费支出或收入
2. **查询**：按时间、成员、项目查询账目
3. **汇总**：统计某月/某成员的消费情况
4. **删除**：删除某条记录
5. **清空**：清空所有记录

## 家庭成员
- 爸爸（别名：爸、父亲、老爸、爹）
- 妈妈（别名：妈、母亲、老妈、娘）
- 女儿（别名：闺女、孩子、小孩、丫头）

## 输出格式
你必须返回一个严格的JSON对象，不要包含任何其他文字。格式如下：

```json
{
  "intent": "record|query|query_member|query_item|query_category|delete|clear_all|help|chat",
  "records": [
    {
      "date": "YYYY-MM-DD格式，没有则null",
      "member": "爸爸|妈妈|女儿|null",
      "category": "买书|吃饭|交通|购物|娱乐|教育|医疗|住房|工资|报销|红包|其他|null",
      "item": "具体项目名称，没有则null",
      "amount": 数字或null,
      "type": "收入|支出|null"
    }
  ],
  "missing": ["缺失字段列表"],
  "reply": "当intent为chat或help时，直接回复用户的内容"
}
```

**重要：当用户一句话中包含多条记账信息时（用"又"、"随后"、"然后"、"还"、"接着"等连接），必须拆分成records数组中的多个元素。例如"买了奔驰300000，又买了衣服1000"应该生成2条记录。**

## 规则
1. 今天是{today}。"今天"就是这个日期，"昨天"是前一天，以此类推。
2. "X月X日"默认为今年，如果日期在未来则为去年。
3. "这个月"/"本月"指当前月份。
4. 收入关键词：工资、奖金、报销、收到、红包、转账、退款。
5. 如果用户说了"删除"、"去掉"、"取消记录"，intent为delete。
6. 如果用户说了"清空"、"清空所有"、"清空全部"、"全部删除"、"清掉所有"、"清除所有"，intent为clear_all。
7. 如果用户问了"花了多少"、"花了多少钱"、"明细"、"记录"，intent为query或query_member或query_item。
8. 如果信息不完整（缺少成员、金额等），在missing数组中列出缺失项。
9. item字段要提取具体物品名，不要包含"买了"、"花了"等动词。例如"买了双登山鞋"→item="登山鞋"。
10. 类别根据物品/事件自动推断：鞋→购物，书→买书，报销→报销，等等。
11. 项目查询：当用户问"我哪天买的三体"时，intent=query_item，item="三体"。
12. 类别查询：当用户问"这个月买书花了多钱"时，intent=query_category，category="买书"。当用户指定了某个类别（买书、吃饭、交通等）并问花了多少钱时，用query_category。
13. missing数组中的值必须用中文，如"成员"、"金额"、"项目"、"日期"，不要用英文。
"""

# ============ 待确认缓存 ============
pending_confirmations = {}


def call_llm(user_message: str) -> Dict:
    """调用LLM解析用户输入"""
    today_str = date.today().strftime("%Y-%m-%d")
    system = SYSTEM_PROMPT.replace("{today}", today_str)

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        content = response.choices[0].message.content.strip()

        # 提取JSON（兼容markdown代码块包裹的情况）
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(content)
    except Exception as e:
        print(f"LLM调用失败: {e}")
        return {"intent": "chat", "reply": "抱歉，我暂时无法理解您的输入，请重试。"}


def handle_record(parsed: Dict) -> str:
    """处理记账请求（支持多条记录）"""
    missing = parsed.get("missing", [])
    records = parsed.get("records", [])

    if not records:
        return "抱歉，我没有理解您的记账信息。\n请按照以下格式输入：\n• 今天女儿买了双登山鞋499元\n• 7月5日妈妈收到报销1000元"

    today_str = date.today().strftime("%Y-%m-%d")
    valid_records = []
    has_missing = False

    for rec in records:
        # 补全日期默认值
        if not rec.get("date"):
            rec["date"] = today_str

        # 成员缺失时默认"我"
        if not rec.get("member"):
            rec["member"] = "我"

        # item缺失时用category补
        if not rec.get("item"):
            rec["item"] = rec.get("category") or "未知"

        # 检查金额是否缺失
        if not rec.get("amount"):
            has_missing = True

        valid_records.append(rec)

    # 如果有缺失金额，引导补充
    if has_missing:
        response = "我注意到有些记录缺少金额信息：\n"
        for i, rec in enumerate(valid_records, 1):
            if not rec.get("amount"):
                response += f"  第{i}条：{rec.get('member', '我')}，{rec.get('item', '未知')} — 请补充金额\n"
        pending_confirmations["last"] = {"records": valid_records}
        return response.strip()

    # 多条记录的确认流程
    if len(valid_records) == 1:
        rec = valid_records[0]
        type_str = rec.get("type", "支出")
        confirm_msg = f"📋 请确认记录信息：\n"
        confirm_msg += f"• 日期：{rec['date']}\n"
        confirm_msg += f"• 成员：{rec['member']}\n"
        confirm_msg += f"• 类别：{rec.get('category', '其他')}\n"
        confirm_msg += f"• 项目：{rec['item']}\n"
        confirm_msg += f"• {type_str}：{rec.get('amount', 0)}元\n"
        confirm_msg += '\n确认记录请回复"确认"，取消请回复"取消"'
    else:
        confirm_msg = f"📋 共识别到 {len(valid_records)} 条记录，请确认：\n\n"
        for i, rec in enumerate(valid_records, 1):
            type_str = rec.get("type", "支出")
            confirm_msg += f"【{i}】{rec['member']}，{rec.get('category', '其他')}，{rec['item']}，{type_str}{rec.get('amount', 0)}元\n"
        confirm_msg += f"\n日期：{valid_records[0]['date']}\n"
        confirm_msg += '\n确认全部记录请回复"确认"，取消请回复"取消"'

    pending_confirmations["last"] = {"records": valid_records}
    return confirm_msg


def confirm_record() -> str:
    """确认并保存记录（支持多条）"""
    if "last" not in pending_confirmations:
        return "没有待确认的记录"

    data = pending_confirmations.pop("last")
    records = data.get("records", [data])  # 兼容单条旧格式
    db = get_db()

    results = []
    for parsed in records:
        member = parsed.get("member") or "我"
        if member not in MEMBERS and member != "我":
            member = "我"

        db.add_record(
            date_str=parsed["date"],
            member=member,
            category=parsed.get("category", "其他"),
            item=parsed.get("item", "未知"),
            amount=float(parsed.get("amount", 0)),
            type_=parsed.get("type", "支出"),
        )

        type_str = "收入" if parsed.get("type") == "收入" else "支出"
        results.append(f"✅ 已记录：{parsed['date']}，{member}，{parsed.get('category', '其他')}，{parsed.get('item', '未知')}，{type_str}{parsed.get('amount', 0)}元")

    return "\n".join(results)


def cancel_record() -> str:
    """取消记录"""
    if "last" in pending_confirmations:
        pending_confirmations.pop("last")
    return "❌ 已取消记录"


def handle_query(parsed: Dict) -> str:
    """处理查询请求"""
    db = get_db()
    today = date.today()

    # 按月查询（家庭或成员）
    month_str = parsed.get("date")
    member = parsed.get("member")

    if month_str:
        # 从日期提取月份
        try:
            dt = datetime.strptime(month_str, "%Y-%m-%d")
            year, month = dt.year, dt.month
        except ValueError:
            year, month = today.year, today.month
    else:
        year, month = today.year, today.month

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year}-12-31"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    if member:
        records = db.query_by_date_range(start_date, end_date, member)
        summary = db.get_summary(start_date, end_date, member)
        title = f"📊 {year}年{month}月{member}的消费明细"
    else:
        records = db.query_by_date_range(start_date, end_date)
        summary = db.get_summary(start_date, end_date)
        title = f"📊 {year}年{month}月家庭消费明细"

    if not records:
        return f"{title}：暂无记录"

    lines = [title]
    lines.append(f"共 {len(records)} 笔记录")
    lines.append(f"总收入：{summary['收入']}元（{summary['收入笔数']}笔）")
    lines.append(f"总支出：{summary['支出']}元（{summary['支出笔数']}笔）")
    lines.append(f"净收入：{summary['净收入']}元")
    lines.append("")
    lines.append("记录：")
    for record in records[:10]:
        sign = "+" if record["type"] == "收入" else "-"
        lines.append(f"• {record['date']}，{record['member']}，{record['item']}，{sign}{record['amount']}元")

    if len(records) > 10:
        lines.append(f"...还有 {len(records) - 10} 条记录")

    return "\n".join(lines)


def handle_query_item(parsed: Dict) -> str:
    """处理按项目查询"""
    db = get_db()
    item = parsed.get("item", "")
    if not item:
        return "请告诉我您想查询什么项目的消费记录\n例如：我哪天买的三体"

    records = db.query_by_item(item)
    if not records:
        return f"没有找到关于「{item}」的消费记录"

    lines = [f"📋 找到 {len(records)} 条关于「{item}」的记录："]
    for record in records[:5]:
        sign = "+" if record["type"] == "收入" else "-"
        lines.append(f"• {record['date']}，{record['member']}，{record['item']}，{sign}{record['amount']}元")

    if len(records) > 5:
        lines.append(f"...还有 {len(records) - 5} 条记录")

    return "\n".join(lines)


def handle_query_category(parsed: Dict) -> str:
    """处理按类别查询（如：这个月买书花了多钱）"""
    db = get_db()
    today = date.today()
    category = parsed.get("category", "")
    member = parsed.get("member")

    if not category:
        return "请告诉我您想查询什么类别的消费\n例如：这个月买书花了多钱"

    # 解析月份
    month_str = parsed.get("date")
    if month_str:
        try:
            dt = datetime.strptime(month_str, "%Y-%m-%d")
            year, month = dt.year, dt.month
        except ValueError:
            year, month = today.year, today.month
    else:
        year, month = today.year, today.month

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year}-12-31"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    # 查询该类别下的记录
    all_records = db.query_by_date_range(start_date, end_date, member)
    records = [r for r in all_records if r["category"] == category]

    if not records:
        return f"{year}年{month}月暂无「{category}」类别的消费记录"

    total = sum(r["amount"] for r in records if r["type"] == "支出")
    income_total = sum(r["amount"] for r in records if r["type"] == "收入")

    lines = [f"📊 {year}年{month}月「{category}」消费明细"]
    lines.append(f"共 {len(records)} 笔记录")
    if total > 0:
        lines.append(f"总支出：{total}元")
    if income_total > 0:
        lines.append(f"总收入：{income_total}元")
    lines.append("")
    lines.append("记录：")
    for record in records[:10]:
        sign = "+" if record["type"] == "收入" else "-"
        lines.append(f"• {record['date']}，{record['member']}，{record['item']}，{sign}{record['amount']}元")

    return "\n".join(lines)


def handle_delete(parsed: Dict) -> str:
    """处理删除请求"""
    db = get_db()
    item = parsed.get("item", "")
    member = parsed.get("member")

    # 构建搜索关键词
    search_term = item or member or ""
    if not search_term:
        return "请告诉我您想删除哪条记录\n例如：删除登山鞋的费用"

    records = db.query_by_item(search_term)

    # 如果没找到，去掉常见后缀再试
    if not records:
        for suffix in ["费用", "记录", "的钱", "的费用", "花的"]:
            if search_term.endswith(suffix):
                shorter = search_term[:-len(suffix)]
                if shorter:
                    records = db.query_by_item(shorter)
                    if records:
                        search_term = shorter
                        break

    # 还没找到，用item中的核心词再试
    if not records and item:
        # 去掉"女儿"等成员前缀
        for prefix in ["女儿", "妈妈", "爸爸", "老妈", "老爸", "闺女"]:
            if item.startswith(prefix):
                shorter = item[len(prefix):]
                if shorter:
                    records = db.query_by_item(shorter)
                    if records:
                        search_term = shorter
                        break

    if not records:
        return f"没有找到关于「{search_term}」的记录"

    if len(records) == 1:
        record = records[0]
        type_str = "收入" if record["type"] == "收入" else "支出"
        confirm_msg = f"⚠️ 请确认删除：\n"
        confirm_msg += f"• 日期：{record['date']}\n"
        confirm_msg += f"• 成员：{record['member']}\n"
        confirm_msg += f"• 项目：{record['item']}\n"
        confirm_msg += f"• 金额：{type_str}{record['amount']}元\n"
        confirm_msg += '\n确认删除请回复"确认删除"，取消请回复"取消"'

        pending_confirmations["delete"] = record
        return confirm_msg
    else:
        lines = [f"找到 {len(records)} 条关于「{search_term}」的记录："]
        for i, record in enumerate(records[:5], 1):
            sign = "+" if record["type"] == "收入" else "-"
            lines.append(f"{i}. {record['date']}，{record['member']}，{record['item']}，{sign}{record['amount']}元")
        lines.append("\n请告诉我要删除第几条，或提供更具体的信息")
        return "\n".join(lines)


def confirm_delete() -> str:
    """确认删除"""
    if "delete" not in pending_confirmations:
        return "没有待确认的删除操作"

    record = pending_confirmations.pop("delete")
    db = get_db()
    db.delete_record(record["id"])

    return f"✅ 已删除：{record['date']}，{record['member']}，{record['item']}，{record['amount']}元"


def handle_clear_all() -> str:
    """处理清空所有记录请求（需确认）"""
    db = get_db()
    records = db.query_by_date_range("2000-01-01", "2099-12-31")
    if not records:
        return "📋 当前没有记录需要清空"

    total = len(records)
    total_income = sum(r["amount"] for r in records if r["type"] == "收入")
    total_expense = sum(r["amount"] for r in records if r["type"] == "支出")

    msg = "⚠️ 确认清空所有记录？此操作不可恢复！\n\n"
    msg += f"📊 当前共 {total} 条记录\n"
    msg += f"   💰 收入: ¥{total_income:.0f}\n"
    msg += f"   💸 支出: ¥{total_expense:.0f}\n\n"
    msg += '确认请回复"确认清空"，取消请回复"取消"'

    pending_confirmations["clear_all"] = True
    return msg


def confirm_clear_all() -> str:
    """确认清空所有记录"""
    if "clear_all" not in pending_confirmations:
        return "没有待确认的清空操作"

    pending_confirmations.pop("clear_all")
    db = get_db()
    count = db.clear_all_records()
    return f"✅ 已清空所有记录，共删除 {count} 条"


def handle_help() -> str:
    """显示帮助信息"""
    return """📖 记账本使用帮助

【记账】
• 今天女儿买了双登山鞋499元
• 7月5日妈妈收到报销1000元
• 昨天爸爸买书花了50元

【查询】
• 看下这个月家里花钱明细
• 这个月女儿花了多少钱？
• 我哪天买的三体

【删除】
• 删除登山鞋的费用
• 删除报销的记录

【清空】
• 清空所有记录
• 清空全部数据"""


def process_message(text: str) -> str:
    """处理用户消息（主入口）"""
    text = text.strip()
    if not text:
        return OPENING_MESSAGE

    # 处理确认/取消
    if text in ("确认", "确定", "好", "yes", "是"):
        return confirm_record()
    if text in ("确认删除", "确认删"):
        return confirm_delete()
    if text in ("清空确认", "确认清空"):
        return confirm_clear_all()
    if text in ("取消", "不要了", "算了", "no", "不"):
        # 同时清除记录、删除和清空的待确认
        if "delete" in pending_confirmations:
            pending_confirmations.pop("delete")
        return cancel_record()

    # 调用LLM解析
    parsed = call_llm(text)
    intent = parsed.get("intent", "chat")

    if intent == "record":
        return handle_record(parsed)
    elif intent in ("query", "query_member"):
        return handle_query(parsed)
    elif intent == "query_item":
        return handle_query_item(parsed)
    elif intent == "query_category":
        return handle_query_category(parsed)
    elif intent == "delete":
        return handle_delete(parsed)
    elif intent == "clear_all":
        return handle_clear_all()
    elif intent == "help":
        return handle_help()
    else:
        return parsed.get("reply", "抱歉，我没有理解您的意思。请输入记账、查询或删除相关的指令。")

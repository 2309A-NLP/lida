"""
业务逻辑服务层
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import json
import os

from models.database import (
    WorkOrder, WorkOrderMessage, WorkOrderLog, AgentTask,
    WorkOrderStatus, WorkOrderPriority, WorkOrderCategory
)
from models.schemas import (
    WorkOrderCreate, WorkOrderUpdate, MessageCreate,
    NLPAnalysisResponse, ChatRequest, ChatResponse, WorkOrderStats
)


class WorkOrderService:
    """工单管理服务"""

    def __init__(self, db: Session):
        self.db = db

    def create_workorder(self, workorder: WorkOrderCreate) -> WorkOrder:
        """创建新工单"""
        # 生成工单编号
        order_number = self._generate_order_number()

        # 创建工单对象
        db_workorder = WorkOrder(
            order_number=order_number,
            title=workorder.title,
            description=workorder.description,
            category=WorkOrderCategory(workorder.category),
            priority=WorkOrderPriority(workorder.priority),
            creator_name=workorder.creator_name,
            creator_contact=workorder.creator_contact,
            status=WorkOrderStatus.PENDING
        )

        # NLP分析
        nlp_service = NLPService(self.db)
        nlp_result = nlp_service.analyze_text(workorder.description)
        if nlp_result:
            db_workorder.intent = nlp_result.intent
            db_workorder.entities = json.dumps(nlp_result.entities, ensure_ascii=False) if nlp_result.entities else None
            db_workorder.sentiment = nlp_result.sentiment

        self.db.add(db_workorder)
        self.db.commit()
        self.db.refresh(db_workorder)

        # 记录日志
        self._add_log(db_workorder.id, "创建工单", f"工单已创建，编号：{order_number}", workorder.creator_name)

        return db_workorder

    def list_workorders(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        creator_name: Optional[str] = None,
        assigned_to: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[WorkOrder]:
        """获取工单列表（支持搜索和多条件筛选）"""
        query = self.db.query(WorkOrder)

        if status:
            query = query.filter(WorkOrder.status == WorkOrderStatus(status))
        if category:
            query = query.filter(WorkOrder.category == WorkOrderCategory(category))
        if priority:
            query = query.filter(WorkOrder.priority == WorkOrderPriority(priority))
        if creator_name:
            query = query.filter(WorkOrder.creator_name.like(f'%{creator_name}%'))
        if assigned_to:
            query = query.filter(WorkOrder.assigned_to.like(f'%{assigned_to}%'))

        # 搜索功能：在标题、描述、工单编号中搜索
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(
                (WorkOrder.title.like(search_pattern)) |
                (WorkOrder.description.like(search_pattern)) |
                (WorkOrder.order_number.like(search_pattern))
            )

        return query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit).all()

    def get_workorder(self, workorder_id: int) -> Optional[WorkOrder]:
        """获取工单详情"""
        return self.db.query(WorkOrder).filter(WorkOrder.id == workorder_id).first()

    def update_workorder(self, workorder_id: int, workorder: WorkOrderUpdate) -> Optional[WorkOrder]:
        """更新工单"""
        db_workorder = self.get_workorder(workorder_id)
        if not db_workorder:
            return None

        update_data = workorder.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field == "status" and value:
                value = WorkOrderStatus(value)
                if value == WorkOrderStatus.COMPLETED:
                    db_workorder.completed_at = datetime.utcnow()
            elif field == "category" and value:
                value = WorkOrderCategory(value)
            elif field == "priority" and value:
                value = WorkOrderPriority(value)

            setattr(db_workorder, field, value)

        db_workorder.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_workorder)

        # 记录日志
        self._add_log(workorder_id, "更新工单", f"工单信息已更新", "系统")

        return db_workorder

    def delete_workorder(self, workorder_id: int) -> bool:
        """删除工单"""
        db_workorder = self.get_workorder(workorder_id)
        if not db_workorder:
            return False

        self.db.delete(db_workorder)
        self.db.commit()
        return True

    def add_message(self, workorder_id: int, message: MessageCreate) -> WorkOrderMessage:
        """添加工单消息"""
        db_message = WorkOrderMessage(
            work_order_id=workorder_id,
            sender=message.sender or "用户",
            sender_type=message.sender_type,
            content=message.content
        )
        self.db.add(db_message)
        self.db.commit()
        self.db.refresh(db_message)
        return db_message

    def get_messages(self, workorder_id: int) -> List[WorkOrderMessage]:
        """获取工单消息列表"""
        return self.db.query(WorkOrderMessage).filter(
            WorkOrderMessage.work_order_id == workorder_id
        ).order_by(WorkOrderMessage.created_at.asc()).all()

    def get_statistics(self) -> WorkOrderStats:
        """获取工单统计信息"""
        total = self.db.query(WorkOrder).count()
        pending = self.db.query(WorkOrder).filter(WorkOrder.status == WorkOrderStatus.PENDING).count()
        processing = self.db.query(WorkOrder).filter(WorkOrder.status == WorkOrderStatus.PROCESSING).count()
        completed = self.db.query(WorkOrder).filter(WorkOrder.status == WorkOrderStatus.COMPLETED).count()
        cancelled = self.db.query(WorkOrder).filter(WorkOrder.status == WorkOrderStatus.CANCELLED).count()

        # 按类别统计
        by_category = {}
        for category in WorkOrderCategory:
            count = self.db.query(WorkOrder).filter(WorkOrder.category == category).count()
            by_category[category.value] = count

        # 按优先级统计
        by_priority = {}
        for priority in WorkOrderPriority:
            count = self.db.query(WorkOrder).filter(WorkOrder.priority == priority).count()
            by_priority[priority.value] = count

        # 平均完成时间
        completed_orders = self.db.query(WorkOrder).filter(
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.completed_at.isnot(None)
        ).all()

        avg_completion_time = None
        if completed_orders:
            total_time = sum(
                (order.completed_at - order.created_at).total_seconds() / 3600
                for order in completed_orders
            )
            avg_completion_time = total_time / len(completed_orders)

        return WorkOrderStats(
            total=total,
            total_count=total,
            pending=pending,
            pending_count=pending,
            processing=processing,
            processing_count=processing,
            completed=completed,
            completed_count=completed,
            cancelled=cancelled,
            by_category=by_category,
            by_priority=by_priority,
            avg_completion_time=avg_completion_time
        )

    def _generate_order_number(self) -> str:
        """生成工单编号"""
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")

        # 查询今天已有的工单数量
        today_start = datetime(now.year, now.month, now.day)
        today_count = self.db.query(WorkOrder).filter(
            WorkOrder.created_at >= today_start
        ).count()

        seq = today_count + 1
        return f"WO{date_str}{seq:04d}"

    def _add_log(self, workorder_id: int, action: str, description: str, operator: str):
        """添加操作日志"""
        log = WorkOrderLog(
            work_order_id=workorder_id,
            action=action,
            description=description,
            operator=operator
        )
        self.db.add(log)
        self.db.commit()


class NLPService:
    """NLP分析服务"""

    def __init__(self, db: Session):
        self.db = db
        self._intent_keywords = {
            "故障报修": ["故障", "坏了", "不能用", "修理", "报修", "错误", "异常"],
            "技术支持": ["如何", "怎么", "帮助", "支持", "咨询", "问题"],
            "业务咨询": ["业务", "流程", "申请", "办理", "查询"],
            "需求开发": ["开发", "新功能", "需求", "定制", "添加"],
            "投诉建议": ["投诉", "建议", "不满意", "反馈"]
        }

    def analyze_text(
        self,
        text: str,
        analyze_intent: bool = True,
        analyze_entities: bool = True,
        analyze_sentiment: bool = True
    ) -> NLPAnalysisResponse:
        """分析文本"""
        result = NLPAnalysisResponse()

        # 意图识别（基于关键词匹配的简化版本）
        if analyze_intent:
            intent, confidence = self._detect_intent(text)
            result.intent = intent
            result.intent_confidence = confidence

        # 实体识别（简化版本）
        if analyze_entities:
            result.entities = self._extract_entities(text)

        # 情感分析（简化版本）
        if analyze_sentiment:
            sentiment, score = self._analyze_sentiment(text)
            result.sentiment = sentiment
            result.sentiment_score = score

        # 关键词提取
        result.keywords = self._extract_keywords(text)

        return result

    def _detect_intent(self, text: str) -> tuple[Optional[str], Optional[float]]:
        """意图检测"""
        text_lower = text.lower()
        max_matches = 0
        detected_intent = None

        for intent, keywords in self._intent_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            if matches > max_matches:
                max_matches = matches
                detected_intent = intent

        confidence = min(max_matches * 0.3, 0.95) if max_matches > 0 else 0.5
        return detected_intent or "其他", confidence

    def _extract_entities(self, text: str) -> List[dict]:
        """实体提取"""
        entities = []
        # 简化版本：提取一些常见模式
        if "电话" in text or "手机" in text:
            entities.append({"type": "联系方式", "text": "电话/手机"})
        if "邮箱" in text or "@" in text:
            entities.append({"type": "联系方式", "text": "邮箱"})
        return entities

    def _analyze_sentiment(self, text: str) -> tuple[str, float]:
        """情感分析"""
        # 简化版本：基于关键词
        negative_words = ["不满", "差", "坏", "烂", "投诉", "问题", "错误", "失败"]
        positive_words = ["好", "满意", "感谢", "不错", "优秀", "完美"]

        negative_count = sum(1 for word in negative_words if word in text)
        positive_count = sum(1 for word in positive_words if word in text)

        if negative_count > positive_count:
            return "消极", 0.3
        elif positive_count > negative_count:
            return "积极", 0.8
        else:
            return "中性", 0.5

    def _extract_keywords(self, text: str) -> List[str]:
        """关键词提取"""
        # 简化版本：返回一些基本词汇
        words = text.split()
        return [w for w in words if len(w) > 1][:5]


class AgentService:
    """Agent自动化服务"""

    def __init__(self, db: Session):
        self.db = db

    async def process_workorder(self, workorder_id: int) -> dict:
        """Agent自动处理工单"""
        workorder = self.db.query(WorkOrder).filter(WorkOrder.id == workorder_id).first()
        if not workorder:
            return {"success": False, "message": "工单不存在"}

        # 创建Agent任务
        task = AgentTask(
            work_order_id=workorder_id,
            task_type="auto_process",
            status="running",
            started_at=datetime.utcnow()
        )
        self.db.add(task)
        self.db.commit()

        try:
            # 根据意图自动分配或处理
            if workorder.intent == "技术支持":
                workorder.assigned_to = "技术支持团队"
            elif workorder.intent == "故障报修":
                workorder.assigned_to = "运维团队"
            elif workorder.intent == "业务咨询":
                workorder.assigned_to = "客服团队"
            else:
                workorder.assigned_to = "综合服务团队"

            workorder.assigned_at = datetime.utcnow()
            workorder.status = WorkOrderStatus.PROCESSING
            workorder.updated_at = datetime.utcnow()

            # 添加系统消息
            message = WorkOrderMessage(
                work_order_id=workorder_id,
                sender="AI助手",
                sender_type="agent",
                content=f"工单已自动分配给 {workorder.assigned_to}，正在处理中..."
            )
            self.db.add(message)

            # 更新任务状态
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.output_data = json.dumps({"assigned_to": workorder.assigned_to}, ensure_ascii=False)

            self.db.commit()

            return {
                "success": True,
                "message": "工单已自动处理",
                "assigned_to": workorder.assigned_to
            }

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            self.db.commit()

            return {"success": False, "message": f"处理失败: {str(e)}"}


class ChatService:
    """智能对话服务"""

    def __init__(self, db: Session):
        self.db = db
        self.nlp_service = NLPService(db)
        self.workorder_service = WorkOrderService(db)

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """处理对话请求 - 智能路由到对应Agent"""
        message = request.message.strip()
        nlp_result = self.nlp_service.analyze_text(message)

        # 问候语识别
        greetings = ["你好", "您好", "hi", "hello", "嗨", "早上好", "下午好", "晚上好", "哈喽"]
        is_greeting = any(g in message.lower() for g in greetings) and len(message) <= 10

        # 招股书/金融问题识别
        finance_keywords = ["股份", "法人", "招股", "发起人", "上市", "证券", "募集", "配售", "承销",
                           "首发", "IPO", "股权", "董事", "监事", "高管", "注册资本", "变更设立"]
        is_finance = any(kw in message for kw in finance_keywords)

        # 基金数据问题识别
        fund_keywords = ["基金", "净值", "持仓", "债券持仓", "股票持仓", "股票行情", "涨跌幅",
                        "A股", "港股", "基金代码", "基金简称", "管理人", "成立日期",
                        "持仓明细", "重仓股", "基金规模", "基金份额", "日行情"]
        is_fund = any(kw in message for kw in fund_keywords) and not is_finance

        # 日程类问题识别
        schedule_keywords = ["日程", "提醒", "会议", "安排", "计划", "约会", "闹钟", "几点", "明天下午", "今天几点"]
        is_schedule = any(kw in message for kw in schedule_keywords)

        # 记账类问题识别
        money_keywords = ["花了", "消费", "记账", "支出", "收入", "账单", "报销", "工资", "买了", "元钱", "多少钱"]
        is_money = any(kw in message for kw in money_keywords)

        # 判断是否需要创建工单
        should_create_workorder = self._should_create_workorder(nlp_result)

        # ===== 基金数据问题 -> 直接调用基金Agent（优先于工单创建）=====
        if is_fund:
            try:
                from backend.fund_agent import process_fund_question
                result = process_fund_question(message)
                return ChatResponse(
                    message=result.get("answer", "基金数据查询完成"),
                    intent="基金查询",
                    suggested_action="已查询基金数据库",
                    work_order_created=False
                )
            except Exception as e:
                pass

        # ===== 招股书问题 -> 直接调用招股书Agent（优先于工单创建）=====
        if is_finance:
            try:
                from backend.prospectus_agent import process_prospectus_question
                result = process_prospectus_question(message)
                answer = result.get("answer", "")
                matched = result.get("matched_docs", 0)
                if matched > 0:
                    return ChatResponse(
                        message=answer,
                        intent="招股书查询",
                        suggested_action="已从招股书知识库检索",
                        work_order_created=False
                    )
                else:
                    return ChatResponse(
                        message=f"我已在招股书知识库中搜索「{message[:30]}」，{answer}",
                        intent="招股书查询",
                        suggested_action=None,
                        work_order_created=False
                    )
            except Exception as e:
                pass

        # ===== 日程问题 -> 直接调用日程Agent（优先于工单创建）=====
        if is_schedule:
            try:
                from backend.schedule_agent import process_schedule_message
                result = process_schedule_message(message)
                return ChatResponse(
                    message=result.get("answer", "日程操作完成"),
                    intent="日程管理",
                    suggested_action=result.get("intent", ""),
                    work_order_created=False
                )
            except Exception as e:
                pass

        # ===== 记账问题 -> 直接调用记账Agent（优先于工单创建）=====
        if is_money:
            try:
                from backend.money_agent import process_money_message
                reply = process_money_message(message)
                return ChatResponse(
                    message=reply,
                    intent="记账",
                    suggested_action="记账本操作",
                    work_order_created=False
                )
            except Exception as e:
                pass

        # ===== 工单创建流程 =====
        if should_create_workorder and not request.work_order_id:
            workorder_data = WorkOrderCreate(
                title=self._generate_title(message),
                description=message,
                category=nlp_result.intent or "其他",
                priority="中",
                creator_name=request.user_name or "访客",
                creator_contact=None
            )
            workorder = self.workorder_service.create_workorder(workorder_data)
            return ChatResponse(
                message=f"我已为您创建了工单（编号：{workorder.order_number}），我们的团队将尽快处理。请问还有其他需要帮助的吗？",
                intent=nlp_result.intent,
                suggested_action="工单已创建",
                work_order_created=True,
                work_order_id=workorder.id
            )

        elif request.work_order_id:
            message_data = MessageCreate(
                content=message,
                sender=request.user_name or "访客",
                sender_type="user"
            )
            self.workorder_service.add_message(request.work_order_id, message_data)
            response_message = self._generate_response(message, nlp_result, is_greeting, is_finance, is_schedule, is_money)
            ai_message_data = MessageCreate(
                content=response_message,
                sender="AI助手",
                sender_type="agent"
            )
            self.workorder_service.add_message(request.work_order_id, ai_message_data)
            return ChatResponse(
                message=response_message,
                intent=nlp_result.intent,
                suggested_action="继续对话",
                work_order_created=False,
                work_order_id=request.work_order_id
            )

        else:
            response_message = self._generate_response(message, nlp_result, is_greeting, is_finance, is_schedule, is_money)
            return ChatResponse(
                message=response_message,
                intent=nlp_result.intent,
                suggested_action=None,
                work_order_created=False
            )

    def _should_create_workorder(self, nlp_result: NLPAnalysisResponse) -> bool:
        """判断是否需要创建工单"""
        workorder_intents = ["故障报修", "需求开发", "技术支持", "业务咨询"]
        return nlp_result.intent in workorder_intents

    def _generate_title(self, message: str) -> str:
        return message[:30] + "..." if len(message) > 30 else message

    def _generate_response(self, message: str, nlp_result, is_greeting=False, is_finance=False, is_schedule=False, is_money=False) -> str:
        """生成智能回复"""
        # 问候语
        if is_greeting:
            return "您好！我是AI智能助手。我可以帮您：\n• 创建和管理工单（如：我的电脑坏了）\n• 记账管理（切换到「记账本Agent」）\n• 日程提醒（切换到「日程提醒Agent」）\n• 基金数据查询（切换到「基金数据问答」）\n• 招股书查询（切换到「招股书问答」）\n请问有什么可以帮助您？"

        # 招股书/金融专业问题
        if is_finance:
            return f"您好！您的问题「{message[:40]}」属于专业金融/招股书查询范畴。\n\n请点击页面顶部的「📄 招股书问答」标签，该模块专门处理招股书相关问题，包括：公司基本信息、法人信息、募集资金用途、股权结构等。\n\n[切换到招股书问答模块→]"

        # 日程相关
        if is_schedule:
            return "您好！日程相关功能请点击页面顶部的「📅 日程提醒Agent」标签。\n\n可以帮您添加、查询、修改和删除日程提醒。\n\n[切换到日程提醒模块→]"

        # 记账相关
        if is_money:
            return "您好！记账相关功能请点击页面顶部的「💰 记账本Agent」标签。\n\n支持记录收支、查询明细和统计分析。\n\n[切换到记账本模块→]"

        # 工单意图的固定回复
        intent_responses = {
            "故障报修": "我已经记录了您的故障信息，技术团队将尽快为您处理。如需进一步跟进，请提供：设备型号、故障现象、发生时间。",
            "技术支持": "我理解您需要技术支持，让我为您安排专业的技术人员协助。请描述您遇到的具体技术问题。",
            "业务咨询": "感谢您的咨询，我们的客服团队会详细为您解答。请提供您的联系方式，方便我们回复您。",
            "需求开发": "您的需求已收到，我们会评估并安排开发计划。请详细描述您的需求，包括功能、场景和优先级。",
            "投诉建议": "非常感谢您的反馈！您的意见对我们非常重要，我们会认真对待并及时改进。",
        }
        if nlp_result.intent in intent_responses:
            return intent_responses[nlp_result.intent]

        # 通用兜底 - 更友好的回复
        return (f"您好！我已收到您的消息：「{message[:50]}{'...' if len(message) > 50 else ''}」\n\n"
                "如果您有以下需求，请直接描述：\n"
                "• 报修/故障：描述问题即可自动创建工单\n"
                "• 技术支持、业务咨询、需求开发：同上\n"
                "• 金融/招股书查询：请切换到对应模块\n"
                "• 日程/记账：请切换到对应模块")

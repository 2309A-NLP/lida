"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

from .answering import ProspectusAnswerer
from .config import FINANCIAL_DB_PATH
from .financial_answering import FinancialDatabaseAnswerer
from .financial_routing import detect_financial_question, suggested_tables
from .models import AnswerResult, QuestionRecord


class QAPipeline:
    def __init__(self, prospectus_answerer: ProspectusAnswerer) -> None:
        self.prospectus_answerer = prospectus_answerer
        self.financial_answerer = FinancialDatabaseAnswerer(FINANCIAL_DB_PATH)

    def answer(self, question_record: QuestionRecord) -> AnswerResult:
        if detect_financial_question(question_record.question):
            financial_result = self.financial_answerer.answer(question_record.question)
            if financial_result is not None:
                return AnswerResult(
                    id=question_record.id,
                    question=question_record.question,
                    answer=financial_result.answer,
                    route=financial_result.route,
                    confidence=financial_result.confidence,
                    evidence=[
                        {
                            "source": str(FINANCIAL_DB_PATH),
                            "suggested_tables": suggested_tables(question_record.question),
                            "sql": financial_result.sql,
                        }
                    ],
                )
            if self.financial_answerer.is_ready:
                return AnswerResult(
                    id=question_record.id,
                    question=question_record.question,
                    answer="已识别为基金/股票/行业数据库题，当前数据库可用，但这道题还未匹配到稳定的自动求解规则。",
                    route="financial_db_rule_uncovered",
                    confidence=0.15,
                    evidence=[
                        {
                            "source": str(FINANCIAL_DB_PATH),
                            "suggested_tables": suggested_tables(question_record.question),
                        }
                    ],
                )
            return AnswerResult(
                id=question_record.id,
                question=question_record.question,
                answer="已识别为基金/股票/行业数据库题，但当前本地金融数据库文件尚未成功就绪，系统已保留自动接入能力。",
                route="financial_db_unavailable",
                confidence=0.1,
                evidence=[
                    {
                        "source": str(FINANCIAL_DB_PATH),
                        "suggested_tables": suggested_tables(question_record.question),
                    }
                ],
            )
        return self.prospectus_answerer.answer(question_record)

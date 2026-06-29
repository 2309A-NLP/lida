"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

from pathlib import Path
import re

from fund_qa.config import Settings
from fund_qa.data.schema import SchemaInspector
from fund_qa.models import QueryResult
from fund_qa.retrieval.prospectus import ProspectusRetriever
from fund_qa.service.router import route_question
from fund_qa.service.sql_engine import HeuristicSqlPlanner, SqlEngine, SqlEngineError


class FundQaService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.schema_inspector = SchemaInspector(settings.sqlite_db_path)
        self.sql_engine = SqlEngine(settings.sqlite_db_path, settings.max_sql_rows)
        self.prospectus = ProspectusRetriever(settings.prospectus_dir)
        self.sql_planner = HeuristicSqlPlanner(self.schema_inspector.as_text())

    def answer(self, question: str, question_id: int | None = None) -> QueryResult:
        question = self._normalize_question(question)
        route = route_question(question)
        if route == "prospectus":
            return self._answer_prospectus(question, question_id)
        return self._answer_sql(question, question_id)

    def _answer_sql(self, question: str, question_id: int | None) -> QueryResult:
        sql = self.sql_planner.plan(question)
        result = QueryResult(question_id=question_id, question=question, route="sql", answer="")
        result.sql = sql
        try:
            executed = self.sql_engine.execute(sql)
            result.rows = executed.rows
            if executed.rows:
                result.answer = self._format_rows(executed.rows)
            else:
                result.answer = "未查询到结果。"
        except SqlEngineError as exc:
            result.answer = "当前无法执行结构化查询，因为真实基金SQLite库尚未接入成功。"
            result.notes.append(str(exc))
        return result

    def _answer_prospectus(self, question: str, question_id: int | None) -> QueryResult:
        evidences = self.prospectus.search(question, top_k=5)
        result = QueryResult(question_id=question_id, question=question, route="prospectus", answer="")
        result.evidences = evidences
        result.answer = self.prospectus.answer_from_evidences(question, evidences)
        return result

    @staticmethod
    def _format_rows(rows: list[dict]) -> str:
        if len(rows) == 1:
            row = rows[0]
            return "；".join(f"{key}={value}" for key, value in row.items())
        preview = []
        for row in rows[:5]:
            preview.append("，".join(f"{key}={value}" for key, value in row.items()))
        return "\n".join(preview)

    @staticmethod
    def _normalize_question(question: str) -> str:
        return re.sub(r"\s+", " ", question).strip()


def build_service(settings: Settings | None = None) -> FundQaService:
    from fund_qa.config import settings as global_settings

    return FundQaService(settings or global_settings)

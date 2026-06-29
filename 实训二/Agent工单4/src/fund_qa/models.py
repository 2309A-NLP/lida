"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Evidence:
    source: str
    score: float
    snippet: str


@dataclass(slots=True)
class QueryResult:
    question_id: int | None
    question: str
    route: str
    answer: str
    sql: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    evidences: list[Evidence] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

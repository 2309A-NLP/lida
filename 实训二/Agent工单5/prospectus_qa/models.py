"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(slots=True)
class QuestionRecord:
    id: int
    question: str


@dataclass(slots=True)
class TextDocument:
    doc_id: str
    source_file: str
    company_name: str
    raw_text: str


@dataclass(slots=True)
class TextChunk:
    chunk_id: str
    doc_id: str
    source_file: str
    company_name: str
    text: str
    char_start: int
    char_end: int


@dataclass(slots=True)
class RetrievedChunk:
    chunk: TextChunk
    score: float
    bm25_score: float
    tfidf_score: float


@dataclass(slots=True)
class AnswerResult:
    id: int
    question: str
    answer: str
    route: str
    confidence: float
    evidence: list[dict[str, Any]]

    def submission_record(self) -> dict[str, Any]:
        return {"id": self.id, "question": self.question, "answer": self.answer}

    def detail_record(self) -> dict[str, Any]:
        return asdict(self)

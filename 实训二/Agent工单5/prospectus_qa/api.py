"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .answering import ProspectusAnswerer
from .data_access import DatasetDownloader
from .indexing import build_chunks, load_chunks, save_chunks
from .qa_pipeline import QAPipeline
from .retrieval import HybridRetriever
from .config import INDEX_DIR
from .models import QuestionRecord

app = FastAPI(title="Prospectus PDF QA Agent", version="1.0.0")
FRONTEND_PATH = Path(__file__).resolve().parent.parent / "web" / "index.html"
KNOWLEDGE_BASE_INFO = {
    "prospectus_texts": "dataset_raw/pdf_txt_file/*.txt",
    "prospectus_text_count": 80,
    "financial_db": "dataset_raw/financial_data.db",
    "dataset_source": "ModelScope bs_challenge_financial_14b_dataset",
}


class QuestionInput(BaseModel):
    question: str
    id: int = -1


@lru_cache(maxsize=1)
def get_answerer() -> QAPipeline:
    downloader = DatasetDownloader()
    downloader.download_metadata()
    downloader.download_financial_db()
    if not (INDEX_DIR / "chunks.jsonl").exists():
        downloader.download_text_files()
        save_chunks(build_chunks())
    chunks = load_chunks()
    return QAPipeline(ProspectusAnswerer(HybridRetriever(chunks)))


@lru_cache(maxsize=1)
def get_frontend_html() -> str:
    return FRONTEND_PATH.read_text(encoding="utf-8")


@app.on_event("startup")
def warmup() -> None:
    get_answerer()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(get_frontend_html())


@app.get("/meta")
def meta() -> dict[str, object]:
    return KNOWLEDGE_BASE_INFO


@app.post("/answer")
def answer_question(payload: QuestionInput) -> dict:
    t0 = time.perf_counter()
    result_obj = get_answerer().answer(QuestionRecord(id=payload.id, question=payload.question.strip()))
    result = result_obj.detail_record()
    result["id"] = payload.id
    result["question"] = payload.question
    result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return result

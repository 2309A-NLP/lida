"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prospectus_qa.answering import ProspectusAnswerer
from prospectus_qa.config import FINANCIAL_DB_PATH
from prospectus_qa.financial_answering import FinancialDatabaseAnswerer
from prospectus_qa.indexing import load_chunks
from prospectus_qa.models import QuestionRecord
from prospectus_qa.qa_pipeline import QAPipeline
from prospectus_qa.retrieval import HybridRetriever


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in Path("dataset_raw/question.json").open(encoding="utf-8")
        if line.strip()
    ]
    selected = rows[args.start : args.start + args.limit]

    chunks = load_chunks()
    pipeline = QAPipeline(ProspectusAnswerer(HybridRetriever(chunks)))
    db_answerer = FinancialDatabaseAnswerer(FINANCIAL_DB_PATH)

    for row in selected:
        question = row["question"]
        t0 = time.perf_counter()
        try:
            result = pipeline.answer(QuestionRecord(id=row["id"], question=question))
            elapsed = time.perf_counter() - t0
            print(f'{row["id"]}\t{elapsed:.3f}\t{result.route}\t{question}', flush=True)
            print(result.answer, flush=True)
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - t0
            print(f'{row["id"]}\t{elapsed:.3f}\tERROR\t{question}', flush=True)
            print(repr(exc), flush=True)
        print("---", flush=True)

        if "基金" in question or "股票" in question or "行业" in question:
            t1 = time.perf_counter()
            db_result = db_answerer.answer(question)
            elapsed = time.perf_counter() - t1
            print(f"db_only\t{elapsed:.3f}\t{bool(db_result)}", flush=True)
            if db_result:
                print(db_result.answer, flush=True)
            print("===", flush=True)


if __name__ == "__main__":
    main()

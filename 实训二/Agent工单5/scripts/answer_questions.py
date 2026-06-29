"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prospectus_qa.answering import ProspectusAnswerer
from prospectus_qa.data_access import DatasetDownloader, load_questions
from prospectus_qa.indexing import build_chunks, load_chunks, save_chunks
from prospectus_qa.models import AnswerResult, QuestionRecord
from prospectus_qa.qa_pipeline import QAPipeline
from prospectus_qa.retrieval import HybridRetriever
from prospectus_qa.config import INDEX_DIR, OUTPUT_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Answer prospectus questions and export jsonl results.")
    parser.add_argument("--limit", type=int, default=None, help="Answer only the first N questions.")
    parser.add_argument(
        "--include-unsupported",
        action="store_true",
        help="Deprecated compatibility flag. All questions are now always written to the output.",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start answering from this zero-based question index.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Write intermediate results every N answered questions.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing output files and append newly answered questions.",
    )
    args = parser.parse_args()

    downloader = DatasetDownloader()
    downloader.download_metadata()
    downloader.download_financial_db()
    if not (INDEX_DIR / "chunks.jsonl").exists():
        downloader.download_text_files()
        save_chunks(build_chunks())

    chunks = load_chunks()
    questions = load_questions()
    answerer = QAPipeline(ProspectusAnswerer(HybridRetriever(chunks)))

    if args.start:
        questions = questions[args.start :]
    if args.limit is not None:
        questions = questions[: args.limit]

    answers: list[AnswerResult] = []
    route_counter: Counter[str] = Counter()
    submission_path = OUTPUT_DIR / "answers.jsonl"
    detail_path = OUTPUT_DIR / "answers_with_evidence.jsonl"
    answered_ids: set[int] = set()

    if args.resume:
        answers = load_existing_results(detail_path)
        answered_ids = {item.id for item in answers}
        route_counter.update(item.route for item in answers)
        questions = [question for question in questions if question.id not in answered_ids]
        if answers:
            write_jsonl(submission_path, [item.submission_record() for item in answers])
            write_jsonl(detail_path, [item.detail_record() for item in answers])
    else:
        reset_jsonl(submission_path)
        reset_jsonl(detail_path)

    pending_results: list[AnswerResult] = []
    for index, question in enumerate(questions, start=1):
        try:
            result = answerer.answer(question)
        except Exception as exc:  # noqa: BLE001
            result = build_fallback_result(question, exc)
        pending_results.append(result)
        answers.append(result)
        route_counter[result.route] += 1
        if args.batch_size > 0 and index % args.batch_size == 0:
            append_jsonl(submission_path, [item.submission_record() for item in pending_results])
            append_jsonl(detail_path, [item.detail_record() for item in pending_results])
            pending_results = []

    if pending_results:
        append_jsonl(submission_path, [item.submission_record() for item in pending_results])
        append_jsonl(detail_path, [item.detail_record() for item in pending_results])

    print(f"Answered {len(answers)} questions.")
    for route, count in sorted(route_counter.items()):
        print(f"{route}: {count}")
    print(f"Submission file: {submission_path}")
    print(f"Detail file: {detail_path}")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def reset_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_existing_results(path: Path) -> list[AnswerResult]:
    if not path.exists():
        return []
    results: list[AnswerResult] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            results.append(AnswerResult(**item))
    return results


def build_fallback_result(question: QuestionRecord, error: Exception) -> AnswerResult:
    return AnswerResult(
        id=question.id,
        question=question.question,
        answer="自动回答过程中出现异常，当前已保留原问题和兜底结果，便于后续继续补齐答案。",
        route="pipeline_exception_fallback",
        confidence=0.0,
        evidence=[
            {
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        ],
    )


if __name__ == "__main__":
    main()

"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fund_qa.config import settings
from fund_qa.data.questions import load_questions
from fund_qa.service.answering import build_service


def _load_existing_answers(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    existing: dict[int, dict] = {}
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" not in item:
                continue
            existing[int(item["id"])] = item
    return existing


def main(limit: int | None = None, resume: bool = True) -> None:
    questions = load_questions(settings.question_file)
    if limit is not None:
        questions = questions[:limit]
    service = build_service()
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    answers_path = settings.outputs_dir / "answers.jsonl"
    existing = _load_existing_answers(answers_path) if resume else {}
    temp_path = answers_path.with_suffix(".jsonl.tmp")

    with temp_path.open("w", encoding="utf-8") as fh:
        for item in questions:
            payload = existing.get(item["id"])
            if payload is None:
                result = service.answer(item["question"], item["id"])
                payload = {
                    "id": item["id"],
                    "question": item["question"],
                    "answer": result.answer,
                    "route": result.route,
                    "sql": result.sql,
                    "notes": result.notes,
                }
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    temp_path.replace(answers_path)

    print(answers_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 question.json 对应的 answers.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-resume", action="store_true", help="忽略现有 answers.jsonl，强制全量重跑")
    args = parser.parse_args()
    main(limit=args.limit, resume=not args.no_resume)

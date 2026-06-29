"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

import json
from pathlib import Path

from fund_qa.service.answering import build_service


SAMPLE_IDS = [0, 1, 2, 11]


def main() -> None:
    service = build_service()
    questions_path = Path("dataset_partial/question.json")
    sample_questions: list[dict] = []

    with questions_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            item = json.loads(line)
            if item["id"] in SAMPLE_IDS:
                sample_questions.append(item)

    sample_questions.sort(key=lambda item: item["id"])

    for item in sample_questions:
        result = service.answer(item["question"], item["id"])
        if not result.answer.strip():
            raise RuntimeError(f"题目 {item['id']} 未生成答案")
        print(f"[PASS] id={item['id']} route={result.route} answer={result.answer[:120]}")


if __name__ == "__main__":
    main()

"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

import argparse
import json

from fund_qa.service.answering import build_service


def main() -> None:
    parser = argparse.ArgumentParser(description="基金数据问答智能体命令行入口")
    parser.add_argument("question", help="待查询的问题")
    parser.add_argument("--question-id", type=int, default=None)
    args = parser.parse_args()

    service = build_service()
    result = service.answer(args.question, args.question_id)
    print(
        json.dumps(
            {
                "question_id": result.question_id,
                "question": result.question,
                "route": result.route,
                "answer": result.answer,
                "sql": result.sql,
                "rows": result.rows,
                "notes": result.notes,
                "evidences": [
                    {"source": item.source, "score": item.score, "snippet": item.snippet}
                    for item in result.evidences
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

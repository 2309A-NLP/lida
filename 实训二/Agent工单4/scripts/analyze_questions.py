"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

from collections import Counter

from fund_qa.config import settings
from fund_qa.data.questions import load_questions
from fund_qa.service.router import route_question


def main() -> None:
    questions = load_questions(settings.question_file)
    counter = Counter(route_question(item["question"]) for item in questions)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    out = settings.outputs_dir / "question_route_summary.txt"
    lines = [f"题目总量: {len(questions)}"]
    for key, value in sorted(counter.items()):
        lines.append(f"{key}: {value}")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()

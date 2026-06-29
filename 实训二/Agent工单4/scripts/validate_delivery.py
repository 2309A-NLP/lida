"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fund_qa.config import settings


REQUIRED_TABLE_COUNT = 10
REQUIRED_QUESTION_COUNT = 1000
REQUIRED_PROSPECTUS_COUNT = 80
REQUIRED_OUTPUT_FILES = [
    settings.docs_dir / "db_schema.md",
    settings.docs_dir / "implementation_notes.md",
    settings.outputs_dir / "db_relationship_graph.png",
    settings.outputs_dir / "answers.jsonl",
]


def _check_tables() -> tuple[bool, str]:
    conn = sqlite3.connect(settings.sqlite_db_path)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    count = len(tables)
    return count == REQUIRED_TABLE_COUNT, f"sqlite_tables={count}"


def _check_questions() -> tuple[bool, str]:
    count = sum(1 for _ in settings.question_file.open(encoding="utf-8"))
    return count == REQUIRED_QUESTION_COUNT, f"question_lines={count}"


def _check_prospectus() -> tuple[bool, str]:
    count = len(list(settings.prospectus_dir.glob("*.txt")))
    return count == REQUIRED_PROSPECTUS_COUNT, f"prospectus_txt_files={count}"


def _check_answers() -> tuple[bool, str]:
    answers_path = settings.outputs_dir / "answers.jsonl"
    valid = 0
    bad = 0
    ids: list[int] = []
    with answers_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            valid += 1
            ids.append(int(item["id"]))
    missing = sorted(set(range(REQUIRED_QUESTION_COUNT)) - set(ids))
    ok = valid == REQUIRED_QUESTION_COUNT and bad == 0 and not missing
    return ok, f"answers_valid={valid}, answers_bad={bad}, missing={len(missing)}"


def _check_output_files() -> tuple[bool, str]:
    missing = [str(path) for path in REQUIRED_OUTPUT_FILES if not path.exists()]
    return not missing, "missing_files=" + (", ".join(missing) if missing else "0")


def main() -> None:
    checks = [
        ("tables", _check_tables),
        ("questions", _check_questions),
        ("prospectus", _check_prospectus),
        ("answers", _check_answers),
        ("outputs", _check_output_files),
    ]
    failed = False
    for name, check in checks:
        ok, detail = check()
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail}")
        if not ok:
            failed = True
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

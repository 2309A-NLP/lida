"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prospectus_qa.indexing import build_chunks, save_chunks


def main() -> None:
    chunks = build_chunks()
    output = save_chunks(chunks)
    print(f"Built {len(chunks)} chunks into {output}.")


if __name__ == "__main__":
    main()

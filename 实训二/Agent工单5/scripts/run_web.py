"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from prospectus_qa.api import app
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=False, log_level="info")


if __name__ == "__main__":
    main()

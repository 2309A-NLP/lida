"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(slots=True)
class Settings:
    project_root: Path
    dataset_root: Path
    question_file: Path
    prospectus_dir: Path
    sqlite_db_path: Path
    outputs_dir: Path
    docs_dir: Path
    max_sql_rows: int = 50

    @classmethod
    def load(cls) -> "Settings":
        root = Path(__file__).resolve().parents[2]
        dataset_root = Path(os.getenv("FUND_QA_DATASET_ROOT", root / "dataset_partial"))
        default_db_candidates = [
            dataset_root / "dataset" / "financial_fund_data.db",
            dataset_root / "dataset" / "博金杯比赛数据.db",
        ]
        env_db = os.getenv("FUND_QA_SQLITE_DB")
        if env_db:
            sqlite_db_path = Path(env_db)
        else:
            sqlite_db_path = next((item for item in default_db_candidates if item.exists()), default_db_candidates[0])
        return cls(
            project_root=root,
            dataset_root=dataset_root,
            question_file=Path(os.getenv("FUND_QA_QUESTION_FILE", dataset_root / "question.json")),
            prospectus_dir=Path(os.getenv("FUND_QA_PROSPECTUS_DIR", dataset_root / "pdf_txt_file")),
            sqlite_db_path=sqlite_db_path,
            outputs_dir=root / "outputs",
            docs_dir=root / "docs",
        )


settings = Settings.load()

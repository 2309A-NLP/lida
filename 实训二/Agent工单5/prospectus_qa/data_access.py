"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Iterator

import requests
from modelscope.hub.api import HubApi
from modelscope.msdatasets.download.download_config import DataDownloadConfig
from modelscope.msdatasets.utils.oss_utils import OssUtilities

from .config import (
    DATASET_DIR,
    FINANCIAL_DB_PATH,
    MODELSCOPE_DATASET_NAME,
    MODELSCOPE_NAMESPACE,
    PDF_TEXT_CSV,
    QUESTION_FILE,
    TEXT_DIR,
)
from .models import QuestionRecord, TextDocument
from .text_utils import best_company_name, normalize_text


class DatasetDownloader:
    def __init__(self) -> None:
        self.api = HubApi()

    def _download_file(
        self,
        remote_path: str,
        local_path: Path,
        timeout: int = 120,
        retries: int = 3,
    ) -> None:
        url = self.api.get_dataset_file_url(
            remote_path,
            MODELSCOPE_DATASET_NAME,
            MODELSCOPE_NAMESPACE,
        )
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(response.content)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == retries:
                    raise
                time.sleep(min(5 * attempt, 15))
        if last_error:
            raise last_error

    def download_metadata(self) -> None:
        DATASET_DIR.mkdir(parents=True, exist_ok=True)
        for remote_path in [
            "question.json",
            "pdf_txt_file.csv",
            "pdf_file.csv",
            "sqlite_db.csv",
            "bs_challenge_financial_14b_dataset.json",
            "dataset_infos.json",
        ]:
            target = DATASET_DIR / Path(remote_path).name
            if target.exists() and target.stat().st_size > 0:
                continue
            self._download_file(remote_path, target)

    def iter_text_remote_paths(self) -> Iterator[str]:
        with PDF_TEXT_CSV.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                yield row["PDF:FILE"]

    def financial_db_remote_path(self) -> str:
        sqlite_meta = DATASET_DIR / "sqlite_db.csv"
        with sqlite_meta.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            row = next(reader)
        return row["DB:FILE"]

    def download_text_file(self, remote_path: str) -> Path:
        target = DATASET_DIR / remote_path
        if target.exists() and target.stat().st_size > 0:
            return target
        self._download_file(remote_path, target)
        return target

    def download_text_files(
        self,
        limit: int | None = None,
        start_index: int = 0,
    ) -> list[Path]:
        downloaded: list[Path] = []
        for index, remote_path in enumerate(self.iter_text_remote_paths(), start=1):
            zero_based_index = index - 1
            if zero_based_index < start_index:
                continue
            if limit is not None and len(downloaded) >= limit:
                break
            downloaded.append(self.download_text_file(remote_path))
        return downloaded

    def download_financial_db(self, force: bool = False) -> Path | None:
        if FINANCIAL_DB_PATH.exists() and FINANCIAL_DB_PATH.stat().st_size > 0 and not force:
            return FINANCIAL_DB_PATH

        remote_path = self.financial_db_remote_path()
        config = DataDownloadConfig()
        config.cache_dir = str(DATASET_DIR / "_financial_db_cache")
        config.force_download = force
        config.split = None
        config.meta_args_map = {}
        oss = OssUtilities(
            dataset_name=MODELSCOPE_DATASET_NAME,
            namespace=MODELSCOPE_NAMESPACE,
            revision="master",
        )
        try:
            local_path = Path(oss.download(remote_path, config))
        except Exception:
            return None

        FINANCIAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        FINANCIAL_DB_PATH.write_bytes(local_path.read_bytes())
        return FINANCIAL_DB_PATH if FINANCIAL_DB_PATH.stat().st_size > 0 else None


def load_questions() -> list[QuestionRecord]:
    questions: list[QuestionRecord] = []
    with QUESTION_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            questions.append(QuestionRecord(id=int(item["id"]), question=item["question"]))
    return questions


def load_text_documents() -> list[TextDocument]:
    documents: list[TextDocument] = []
    for path in sorted(TEXT_DIR.glob("*.txt")):
        raw_text = normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
        if not raw_text:
            continue
        company_name = best_company_name(raw_text[:5000], fallback=path.stem)
        documents.append(
            TextDocument(
                doc_id=path.stem,
                source_file=path.name,
                company_name=company_name,
                raw_text=raw_text,
            )
        )
    return documents

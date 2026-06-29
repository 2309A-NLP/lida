"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset_raw"
TEXT_DIR = DATASET_DIR / "pdf_txt_file"
OUTPUT_DIR = BASE_DIR / "outputs"
INDEX_DIR = OUTPUT_DIR / "index"
QUESTION_FILE = DATASET_DIR / "question.json"
PDF_TEXT_CSV = DATASET_DIR / "pdf_txt_file.csv"
FINANCIAL_DB_PATH = DATASET_DIR / "financial_data.db"

MODELSCOPE_DATASET_ID = "BJQW14B/bs_challenge_financial_14b_dataset"
MODELSCOPE_NAMESPACE = "BJQW14B"
MODELSCOPE_DATASET_NAME = "bs_challenge_financial_14b_dataset"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 180
BM25_TOP_K = 12
TFIDF_TOP_K = 12
FINAL_TOP_K = 8

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

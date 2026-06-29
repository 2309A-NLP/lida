"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prospectus_qa.data_access import DatasetDownloader


def main() -> None:
    parser = argparse.ArgumentParser(description="Download prospectus knowledge base from ModelScope.")
    parser.add_argument("--limit", type=int, default=None, help="Only download the first N text files.")
    parser.add_argument("--start", type=int, default=0, help="Zero-based start index for resumed downloads.")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent text downloads.")
    parser.add_argument("--with-financial-db", action="store_true", help="Also try to download the financial sqlite database.")
    args = parser.parse_args()

    downloader = DatasetDownloader()
    downloader.download_metadata()
    if args.with_financial_db:
        db_path = downloader.download_financial_db()
        if db_path is None:
            print("Financial database download did not complete successfully.")
        else:
            print(f"Financial database ready at {db_path}")
    remote_paths = list(downloader.iter_text_remote_paths())
    selected = remote_paths[args.start :]
    if args.limit is not None:
        selected = selected[: args.limit]

    def fetch(remote_path: str) -> str:
        downloader.download_text_file(remote_path)
        return remote_path

    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(fetch, remote_path) for remote_path in selected]
        for future in as_completed(futures):
            remote_path = future.result()
            completed += 1
            print(f"[{completed}/{len(selected)}] ready {remote_path}")

    print(f"Downloaded or verified {completed} prospectus text files.")


if __name__ == "__main__":
    main()

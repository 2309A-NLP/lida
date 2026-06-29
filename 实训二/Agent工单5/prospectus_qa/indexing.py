"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .config import CHUNK_OVERLAP, CHUNK_SIZE, INDEX_DIR
from .data_access import load_text_documents
from .models import TextChunk
from .text_utils import chunk_text


def build_chunks() -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for document in load_text_documents():
        for idx, (start, end, text) in enumerate(
            chunk_text(document.raw_text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        ):
            chunks.append(
                TextChunk(
                    chunk_id=f"{document.doc_id}-{idx}",
                    doc_id=document.doc_id,
                    source_file=document.source_file,
                    company_name=document.company_name,
                    text=text,
                    char_start=start,
                    char_end=end,
                )
            )
    return chunks


def save_chunks(chunks: list[TextChunk], target: Path | None = None) -> Path:
    target = target or INDEX_DIR / "chunks.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
    return target


def load_chunks(path: Path | None = None) -> list[TextChunk]:
    path = path or INDEX_DIR / "chunks.jsonl"
    chunks: list[TextChunk] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            item = json.loads(line)
            chunks.append(TextChunk(**item))
    return chunks

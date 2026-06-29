"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import re
from typing import Iterable

import jieba

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；\n])")
MULTI_SPACE_RE = re.compile(r"[ \t]+")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
COMPANY_NAME_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()·]{4,80}?(?:集团股份有限公司|股份有限公司|有限责任公司|有限公司))"
)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = MULTI_SPACE_RE.sub(" ", text)
    text = MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    return parts or [text]


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[tuple[int, int, str]]:
    text = normalize_text(text)
    if len(text) <= chunk_size:
        return [(0, len(text), text)]

    sentences = split_sentences(text)
    chunks: list[tuple[int, int, str]] = []
    current = []
    current_start = 0
    current_len = 0
    cursor = 0

    for sentence in sentences:
        sentence_start = text.find(sentence, cursor)
        if sentence_start == -1:
            sentence_start = cursor
        sentence_end = sentence_start + len(sentence)
        cursor = sentence_end

        if current and current_len + len(sentence) > chunk_size:
            chunk_text_value = "".join(current).strip()
            chunk_end = current_start + len(chunk_text_value)
            chunks.append((current_start, chunk_end, chunk_text_value))
            overlap_text = chunk_text_value[-overlap:] if overlap > 0 else ""
            current = [overlap_text, sentence]
            current_start = max(0, sentence_start - len(overlap_text))
            current_len = len(overlap_text) + len(sentence)
        else:
            if not current:
                current_start = sentence_start
            current.append(sentence)
            current_len += len(sentence)

    if current:
        chunk_text_value = "".join(current).strip()
        chunk_end = current_start + len(chunk_text_value)
        chunks.append((current_start, chunk_end, chunk_text_value))

    return chunks


def tokenize_for_bm25(text: str) -> list[str]:
    text = normalize_text(text)
    return [token.strip() for token in jieba.lcut(text) if token.strip()]


def best_company_name(text: str, fallback: str) -> str:
    matches = COMPANY_NAME_RE.findall(text)
    if matches:
        ranked = []
        for name in dict.fromkeys(matches):
            frequency = text.count(name)
            first_index = text.find(name)
            penalty = 0
            if "保荐" in name or "证券" in name or "会计师事务所" in name:
                penalty += 5
            if len(name) < 8:
                penalty += 2
            ranked.append((frequency, len(name), -first_index, -penalty, name))
        ranked.sort(reverse=True)
        return ranked[0][4]
    return fallback


def extract_company_name(text: str) -> str | None:
    match = COMPANY_NAME_RE.search(text)
    if match:
        return match.group(1)
    return None


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)

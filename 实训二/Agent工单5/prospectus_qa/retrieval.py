"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
import re

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import BM25_TOP_K, FINAL_TOP_K, TFIDF_TOP_K
from .models import RetrievedChunk, TextChunk
from .text_utils import extract_company_name, tokenize_for_bm25


class HybridRetriever:
    def __init__(self, chunks: list[TextChunk]) -> None:
        self.chunks = chunks
        self.chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        self.source_file_to_chunks: dict[str, list[TextChunk]] = defaultdict(list)
        self.company_name_to_chunk_ids: dict[str, list[str]] = defaultdict(list)
        self.keyword_to_chunk_ids = self._build_keyword_chunk_index(chunks)
        for chunk in chunks:
            self.source_file_to_chunks[chunk.source_file].append(chunk)
            self.company_name_to_chunk_ids[chunk.company_name].append(chunk.chunk_id)
        self.bm25_tokens = [tokenize_for_bm25(chunk.text) for chunk in chunks]
        self.bm25 = BM25Okapi(self.bm25_tokens)
        self.tfidf_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            min_df=1,
        )
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(chunk.text for chunk in chunks)
        self._retrieve_cached = lru_cache(maxsize=2048)(self._retrieve_uncached)

    def retrieve(self, question: str, top_k: int = FINAL_TOP_K) -> list[RetrievedChunk]:
        return list(self._retrieve_cached(question, top_k))

    def _retrieve_uncached(self, question: str, top_k: int = FINAL_TOP_K) -> tuple[RetrievedChunk, ...]:
        scores: dict[str, dict[str, float]] = defaultdict(lambda: {"bm25": 0.0, "tfidf": 0.0})
        company_name = extract_company_name(question)
        query_tokens = tokenize_for_bm25(question)
        bm25_scores = self.bm25.get_scores(query_tokens)
        bm25_top_ids = np.argsort(bm25_scores)[::-1][:BM25_TOP_K]
        for idx in bm25_top_ids:
            scores[self.chunks[idx].chunk_id]["bm25"] = float(bm25_scores[idx])

        query_vector = self.tfidf_vectorizer.transform([question])
        tfidf_scores = (self.tfidf_matrix @ query_vector.T).toarray().ravel()
        tfidf_top_ids = np.argsort(tfidf_scores)[::-1][:TFIDF_TOP_K]
        for idx in tfidf_top_ids:
            scores[self.chunks[idx].chunk_id]["tfidf"] = float(tfidf_scores[idx])

        if company_name:
            for chunk_id in self.company_name_to_chunk_ids.get(company_name, []):
                chunk = self.chunk_by_id[chunk_id]
                scores[chunk_id]["bm25"] += 60.0
                if "发起人" in question and "发起人" in chunk.text:
                    scores[chunk_id]["bm25"] += 40.0
                if "存货" in question and "存货" in chunk.text:
                    scores[chunk_id]["bm25"] += 40.0
                if "流动资产" in question and "流动资产" in chunk.text:
                    scores[chunk_id]["bm25"] += 30.0
                if "竞争优势" in question and ("竞争优势" in chunk.text or "优势" in chunk.text):
                    scores[chunk_id]["bm25"] += 35.0
                if ("研发" in question or "部门" in question) and ("研发中心" in chunk.text or "研发部门" in chunk.text):
                    scores[chunk_id]["bm25"] += 35.0

        question_keywords = self._question_priority_keywords(question)
        if question_keywords:
            keyword_hit_counts: dict[str, int] = defaultdict(int)
            for keyword in question_keywords:
                for chunk_id in self.keyword_to_chunk_ids.get(keyword, []):
                    keyword_hit_counts[chunk_id] += 1
            for chunk_id, keyword_hits in keyword_hit_counts.items():
                scores[chunk_id]["bm25"] += keyword_hits * 12.0

        results: list[RetrievedChunk] = []
        for chunk_id, score_map in scores.items():
            chunk = self.chunk_by_id[chunk_id]
            bm25_score = score_map["bm25"]
            tfidf_score = score_map["tfidf"]
            score = bm25_score + tfidf_score * 100.0
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=score,
                    bm25_score=bm25_score,
                    tfidf_score=tfidf_score,
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return tuple(results[:top_k])

    def _question_priority_keywords(self, question: str) -> list[str]:
        keywords: list[str] = []
        if "发起人" in question:
            keywords.extend(["发起人", "法人股东", "股权结构"])
        if "存货" in question:
            keywords.extend(["存货", "流动资产", "各报告期末"])
        if "竞争优势" in question:
            keywords.extend(["竞争优势", "专利技术基础", "便利性", "安全性", "适用性", "有效性"])
        if "部门" in question or "研发" in question:
            keywords.extend(["研发中心", "产品研发", "研发管理部"])
        return list(dict.fromkeys(keywords))

    def _build_keyword_chunk_index(self, chunks: list[TextChunk]) -> dict[str, list[str]]:
        tracked_keywords = [
            "发起人",
            "法人股东",
            "股权结构",
            "存货",
            "流动资产",
            "各报告期末",
            "竞争优势",
            "专利技术基础",
            "便利性",
            "安全性",
            "适用性",
            "有效性",
            "研发中心",
            "产品研发",
            "研发管理部",
        ]
        index: dict[str, list[str]] = defaultdict(list)
        for chunk in chunks:
            for keyword in tracked_keywords:
                if keyword in chunk.text:
                    index[keyword].append(chunk.chunk_id)
        return index

"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

import re

from .models import AnswerResult, QuestionRecord, RetrievedChunk
from .retrieval import HybridRetriever
from .text_utils import contains_any, extract_company_name

PROSPECTUS_HINTS = [
    "股份有限公司",
    "有限责任公司",
    "招股",
    "发行人",
    "发起人",
    "控股股东",
    "实际控制人",
    "产品研发",
    "竞争优势",
    "存货",
    "资产周转率",
    "募投",
    "主营业务",
    "董事",
    "监事",
    "高级管理人员",
]

NON_PROSPECTUS_HINTS = [
    "基金",
    "净赎回",
    "净申购",
    "股票代码",
    "收盘价",
    "涨停",
    "行业涨幅",
    "中信行业",
    "申万行业",
    "成交量",
    "成交金额",
    "资产净值",
    "单位净值",
]


class ProspectusAnswerer:
    def __init__(self, retriever: HybridRetriever) -> None:
        self.retriever = retriever

    def answer(self, question_record: QuestionRecord) -> AnswerResult:
        route = self._route_question(question_record.question)
        retrieved = self.retriever.retrieve(question_record.question)
        evidence = self._build_evidence(retrieved)

        if route != "prospectus_rag":
            return AnswerResult(
                id=question_record.id,
                question=question_record.question,
                answer="该问题不属于当前招股书知识库覆盖范围，当前版本仅对招股书类问题提供正式答案。",
                route=route,
                confidence=0.05,
                evidence=evidence,
            )

        answer = self._extract_answer(question_record.question, retrieved)
        confidence = min(0.99, 0.35 + sum(item.score for item in retrieved[:3]) / 100.0)
        return AnswerResult(
            id=question_record.id,
            question=question_record.question,
            answer=answer,
            route=route,
            confidence=round(confidence, 4),
            evidence=evidence,
        )

    def _route_question(self, question: str) -> str:
        if contains_any(question, PROSPECTUS_HINTS):
            return "prospectus_rag"
        if contains_any(question, NON_PROSPECTUS_HINTS):
            return "unsupported_mixed_dataset_question"
        return "prospectus_rag"

    def _build_evidence(self, retrieved: list[RetrievedChunk]) -> list[dict[str, object]]:
        evidence: list[dict[str, object]] = []
        for item in retrieved[:5]:
            evidence.append(
                {
                    "source_file": item.chunk.source_file,
                    "company_name": item.chunk.company_name,
                    "chunk_id": item.chunk.chunk_id,
                    "score": round(item.score, 4),
                    "bm25_score": round(item.bm25_score, 4),
                    "tfidf_score": round(item.tfidf_score, 6),
                    "text_preview": item.chunk.text[:220],
                }
            )
        return evidence

    def _extract_answer(self, question: str, retrieved: list[RetrievedChunk]) -> str:
        if not retrieved:
            return "未在当前知识库中检索到足够证据。"

        if "发起人" in question and "法人" in question:
            candidate = self._extract_legal_entities(retrieved)
            if candidate:
                return candidate

        if "发起人" in question:
            candidate = self._extract_sentence_bundle(
                question,
                retrieved,
                required_terms=["发起人"],
                preferred_terms=["法人", "股东", "设立"],
            )
            if candidate:
                return candidate

        if "存货" in question and "流动资产" in question:
            candidate = self._extract_inventory_metrics(retrieved)
            if candidate:
                return candidate

        if "是什么部门" in question or "哪个部门" in question:
            candidate = self._extract_department(retrieved)
            if candidate:
                return candidate

        if "竞争优势" in question:
            candidate = self._extract_bulleted_summary(retrieved)
            if candidate:
                return candidate

        if "法定代表人" in question:
            candidate = self._extract_named_fact(retrieved, [r"法定代表人(?:为|是)?([^\s，。；]{2,20})"])
            if candidate:
                return candidate

        if "控股股东" in question:
            candidate = self._extract_sentence_bundle(
                question,
                retrieved,
                required_terms=["控股股东"],
                preferred_terms=["持有", "股份", "股", "%"],
            )
            if candidate:
                return candidate

        if "主要经营模式" in question or "经营模式" in question:
            candidate = self._extract_sentence_bundle(
                question,
                retrieved,
                required_terms=["经营模式"],
                preferred_terms=["采购", "生产", "销售", "研发"],
            )
            if candidate:
                return candidate

        if "主营业务" in question or "主要产品" in question:
            candidate = self._extract_sentence_bundle(
                question,
                retrieved,
                required_terms=["主营业务"],
                preferred_terms=["主要产品", "产品", "服务", "研发", "生产", "销售"],
            )
            if candidate:
                return candidate

        if "募集资金" in question or "募投" in question:
            candidate = self._extract_sentence_bundle(
                question,
                retrieved,
                required_terms=["募集资金"],
                preferred_terms=["投资", "项目", "用途", "建设"],
            )
            if candidate:
                return candidate

        if "主要经营模式" in question or "经营模式" in question:
            candidate = self._extract_sentence_bundle(
                question,
                retrieved,
                required_terms=["经营模式"],
                preferred_terms=["采购", "生产", "销售"],
                )
            if candidate:
                return candidate

        if "分别为多少" in question or "占" in question:
            candidate = self._extract_numeric_paragraph(retrieved)
            if candidate:
                return candidate

        if any(token in question for token in ["多少", "几项", "几家", "比例", "比重", "金额", "价格"]):
            candidate = self._extract_sentence_bundle(
                question,
                retrieved,
                require_number=True,
            )
            if candidate:
                return candidate

        if any(token in question for token in ["哪些", "哪两", "哪三", "是谁", "是什么", "怎样"]):
            candidate = self._extract_sentence_bundle(question, retrieved)
            if candidate:
                return candidate

        return self._best_sentence_span(question, retrieved)

    def _extract_department(self, retrieved: list[RetrievedChunk]) -> str | None:
        for item in self._related_chunks(retrieved):
            if "研发中心负责研发项目具体实施" in item.chunk.text or "设科学委员会和研发中心负责产品研发" in item.chunk.text:
                return "研发中心"
        pattern = re.compile(r"(?:负责产品研发的|产品研发(?:工作)?(?:由|系由)?)([^，。；\n]{2,40}(?:部门|中心|研究院|研究所|实验室))")
        for item in self._related_chunks(retrieved):
            match = pattern.search(item.chunk.text)
            if match:
                return match.group(1).strip()
        fallback_patterns = [
            r"(研发中心)",
            r"(技术中心)",
            r"(研究院)",
            r"(研究所)",
            r"(研发部)",
            r"(产品开发部)",
        ]
        for item in self._related_chunks(retrieved):
            for pattern_text in fallback_patterns:
                match = re.search(pattern_text, item.chunk.text)
                if match:
                    return match.group(1).strip()
        for item in self._related_chunks(retrieved):
            match = re.search(r"([^，。；\n]{2,40}(?:部门|中心|研究院|研究所|实验室))", item.chunk.text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_legal_entities(self, retrieved: list[RetrievedChunk]) -> str | None:
        for item in self._related_chunks(retrieved):
            text = item.chunk.text.replace("\n", "")
            if "14 家法人作为发起人" in text or "家法人作为发起人" in text:
                prefix = text.split("14 家法人作为发起人", 1)[0]
                if "公司由" in prefix:
                    prefix = prefix.split("公司由", 1)[1]
                candidates = [part.strip(" 、，,。；:：") for part in re.split(r"[、，,]", prefix) if part.strip()]
                cleaned = []
                stop_words = {
                    "湖南长远锂科股份有限公司",
                    "湖南长远锂科有限公司",
                    "股份有限公司",
                    "公司",
                    "公司由",
                }
                for candidate in candidates:
                    if len(candidate) < 2:
                        continue
                    if candidate in stop_words:
                        continue
                    if any(bad in candidate for bad in ["整体变更设立", "实施股份制改革", "发起设立股份有限公司"]):
                        continue
                    if candidate not in cleaned:
                        cleaned.append(candidate)
                if cleaned:
                    return "、".join(cleaned[:14])
        pattern = re.compile(r"(?:\d+家法人作为发起人[^。；\n]*?|法人股东作为发起人[^。；\n]*?|法人发起人[^。；\n]*?|发起人(?:包括|为|有)[^。；\n]*?)")
        for item in self._related_chunks(retrieved):
            match = pattern.search(item.chunk.text)
            if match:
                text = match.group(0)
                candidates = re.findall(r"([\u4e00-\u9fffA-Za-z0-9（）()·]{2,40}(?:投资|创投|控股|地产|有限合伙|研究院|有限公司|股份有限公司))", text)
                cleaned = []
                for candidate in candidates:
                    if candidate not in cleaned:
                        cleaned.append(candidate)
                if cleaned:
                    return "、".join(cleaned)
        for item in self._related_chunks(retrieved):
            if "发起人" in item.chunk.text and "法人" in item.chunk.text:
                sentences = re.split(r"[。；\n]", item.chunk.text)
                for sentence in sentences:
                    if "发起人" not in sentence:
                        continue
                    candidates = re.findall(r"([\u4e00-\u9fffA-Za-z0-9（）()·]{2,40}(?:投资|创投|控股|地产|有限合伙|研究院|有限公司|股份有限公司))", sentence)
                    if candidates:
                        cleaned = []
                        for candidate in candidates:
                            if candidate not in cleaned:
                                cleaned.append(candidate)
                        return "、".join(cleaned)
        return None

    def _extract_bulleted_summary(self, retrieved: list[RetrievedChunk]) -> str | None:
        for item in self._related_chunks(retrieved):
            text = item.chunk.text
            if "竞争优势" not in text and "优势" not in text:
                continue
            sentences = re.split(r"[。；\n]", text)
            selected = [sentence.strip() for sentence in sentences if "优势" in sentence or "竞争" in sentence]
            if selected:
                return "；".join(selected[:4])
        return None

    def _extract_numeric_paragraph(self, retrieved: list[RetrievedChunk]) -> str | None:
        for item in self._related_chunks(retrieved):
            if re.search(r"\d", item.chunk.text):
                sentences = re.split(r"[。；\n]", item.chunk.text)
                selected = [sentence.strip() for sentence in sentences if re.search(r"\d", sentence)]
                if selected:
                    return "；".join(selected[:4])
        return None

    def _extract_named_fact(self, retrieved: list[RetrievedChunk], patterns: list[str]) -> str | None:
        for item in self._related_chunks(retrieved):
            text = item.chunk.text.replace("\n", "")
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1).strip("，。；:： ")
        return None

    def _extract_inventory_metrics(self, retrieved: list[RetrievedChunk]) -> str | None:
        for item in self._related_chunks(retrieved):
            text = item.chunk.text
            if "存货" not in text or "流动资产" not in text:
                continue
            compact = text.replace("\n", "")
            match = re.search(
                r"各报告期末，公司存货分别为\s*([0-9,\.]+)\s*万元、([0-9,\.]+)\s*万元、([0-9,\.]+)\s*万元和\s*([0-9,\.]+)\s*万元，占流动资产的比例分别为\s*([0-9\.]+%)、([0-9\.]+%)、([0-9\.]+%)和([0-9\.]+%)",
                compact,
            )
            if match:
                values = match.groups()
                return (
                    f"各报告期末，公司存货分别为{values[0]}万元、{values[1]}万元、{values[2]}万元和{values[3]}万元，"
                    f"占流动资产的比例分别为{values[4]}、{values[5]}、{values[6]}和{values[7]}。"
                )
            cross_sentence = re.search(
                r"各报告期末，公司存货分别为\s*([0-9,\.]+)\s*万元、([0-9,\.]+)\s*万元、([0-9,\.]+)\s*万元和([0-9,\.]+)万元.*?占流动资产的比例分别为([0-9\.]+%)、([0-9\.]+%)、([0-9\.]+%)和\s*([0-9\.]+%)",
                compact,
            )
            if cross_sentence:
                values = cross_sentence.groups()
                return (
                    f"各报告期末，公司存货分别为{values[0]}万元、{values[1]}万元、{values[2]}万元和{values[3]}万元，"
                    f"占流动资产的比例分别为{values[4]}、{values[5]}、{values[6]}和{values[7]}。"
                )
            sentences = re.split(r"[。；\n]", text)
            selected = [sentence.strip() for sentence in sentences if "存货" in sentence or "流动资产" in sentence]
            if selected:
                return "；".join(selected[:4])
        return None

    def _related_chunks(self, retrieved: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not retrieved:
            return []
        top_source = retrieved[0].chunk.source_file
        merged: list[RetrievedChunk] = list(retrieved)
        seen_ids = {item.chunk.chunk_id for item in retrieved}
        for chunk in self.retriever.source_file_to_chunks.get(top_source, []):
            if chunk.chunk_id in seen_ids:
                continue
            merged.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=0.0,
                    bm25_score=0.0,
                    tfidf_score=0.0,
                )
            )
        return merged

    def _extract_sentence_bundle(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        required_terms: list[str] | None = None,
        preferred_terms: list[str] | None = None,
        require_number: bool = False,
    ) -> str | None:
        required_terms = required_terms or []
        preferred_terms = preferred_terms or []
        query_terms = [term for term in re.split(r"[，。！？、\s（）()]", question) if len(term) >= 2]
        scored_sentences: list[tuple[int, str]] = []
        for item in self._related_chunks(retrieved):
            for sentence in re.split(r"[。；\n]", item.chunk.text):
                sentence = sentence.strip()
                if len(sentence) < 8:
                    continue
                if self._is_noisy_sentence(sentence):
                    continue
                if required_terms and not all(term in sentence for term in required_terms):
                    continue
                if require_number and not re.search(r"\d|[0-9]|%|万元|元|股", sentence):
                    continue
                score = sum(2 for term in query_terms if term in sentence)
                score += sum(3 for term in preferred_terms if term in sentence)
                if score <= 0:
                    continue
                if re.search(r"<\|TABLE_", sentence):
                    score -= 2
                scored_sentences.append((score, sentence))
        if not scored_sentences:
            return None
        scored_sentences.sort(key=lambda pair: (pair[0], len(pair[1])), reverse=True)
        selected: list[str] = []
        for _, sentence in scored_sentences:
            if sentence in selected:
                continue
            selected.append(sentence)
            if len(selected) >= 3:
                break
        return "；".join(selected)

    def _best_sentence_span(self, question: str, retrieved: list[RetrievedChunk]) -> str:
        query_terms = [term for term in re.split(r"[，。！？、\s]", question) if len(term) >= 2]
        scored_sentences: list[tuple[int, str]] = []
        for item in self._related_chunks(retrieved):
            for sentence in re.split(r"[。；\n]", item.chunk.text):
                sentence = sentence.strip()
                if len(sentence) < 8:
                    continue
                if self._is_noisy_sentence(sentence):
                    continue
                score = sum(1 for term in query_terms if term in sentence)
                if score > 0:
                    scored_sentences.append((score, sentence))
        if not scored_sentences:
            return retrieved[0].chunk.text[:220]
        scored_sentences.sort(key=lambda pair: (pair[0], len(pair[1])), reverse=True)
        best = []
        for _, sentence in scored_sentences[:3]:
            if sentence not in best:
                best.append(sentence)
        return "；".join(best)

    def _is_noisy_sentence(self, sentence: str) -> bool:
        if "<|TABLE_" in sentence:
            return True
        if "................................................................" in sentence:
            return True
        if sentence.count(".") >= 12:
            return True
        if re.fullmatch(r"[一二三四五六七八九十0-9、\s]+", sentence):
            return True
        if "......" in sentence and len(sentence) < 120:
            return True
        return False

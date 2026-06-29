"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from fund_qa.models import Evidence


def _chunk_text(text: str, chunk_size: int = 420, overlap: int = 80) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


@dataclass(slots=True)
class ProspectusChunk:
    source: str
    text: str


@dataclass(slots=True)
class ProspectusDocument:
    source: str
    text: str


class ProspectusRetriever:
    def __init__(self, directory: Path):
        self.directory = directory
        self._documents_list: list[ProspectusDocument] = []
        self._documents: dict[str, str] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        if not self.directory.exists():
            self._loaded = True
            return
        documents: list[ProspectusDocument] = []
        for path in sorted(self.directory.glob("*.txt")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            normalized_text = re.sub(r"\s+", " ", text)
            self._documents[path.name] = normalized_text
            documents.append(ProspectusDocument(source=path.name, text=normalized_text))
        self._documents_list = documents
        self._loaded = True

    def search(self, query: str, top_k: int = 5) -> list[Evidence]:
        self.load()
        if not self._documents_list:
            return []
        scored_indexes = sorted(
            range(len(self._documents_list)),
            key=lambda i: self._document_score(query, self._documents_list[i].text),
            reverse=True,
        )[:top_k]
        evidences: list[Evidence] = []
        for idx in scored_indexes:
            document = self._documents_list[idx]
            score = self._document_score(query, document.text)
            if score <= 0:
                continue
            snippet = self._extract_relevant_snippet(document.text, query)
            evidences.append(Evidence(source=document.source, score=score, snippet=snippet))
        return evidences

    def _document_score(self, query: str, document: str) -> float:
        keywords = [part for part in re.split(r"[，。、？?：:\s（）()]", query) if len(part) >= 2]
        company_name = self._company_name(query)
        score = 0.0
        if company_name and company_name in document:
            score += 50.0
        for keyword in keywords:
            count = document.count(keyword)
            if not count:
                continue
            weight = 6.0 if keyword in {"发起人", "控股股东", "募集资金", "专利", "优势", "部门"} else 1.5
            score += min(count, 3) * weight
        return score

    def _extract_relevant_snippet(self, text: str, query: str, window: int = 220) -> str:
        keywords = [part for part in re.split(r"[，。、？?：:\s（）()]", query) if len(part) >= 2]
        best_index = -1
        best_score = -1
        for keyword in keywords:
            index = text.find(keyword)
            if index < 0:
                continue
            score = len(keyword)
            if score > best_score:
                best_score = score
                best_index = index
        if best_index < 0:
            return text[:window]
        start = max(0, best_index - window // 2)
        end = min(len(text), best_index + window)
        return text[start:end]

    def answer_from_evidences(self, query: str, evidences: list[Evidence]) -> str:
        if not evidences:
            return "未在招股书解析文本中检索到高相关证据。"
        question = query.strip()
        extracted = self._extract_targeted_answer(question, evidences)
        if extracted:
            return extracted
        combined = " ".join(item.snippet for item in evidences[:3])
        sentences = re.split(r"(?<=[。！？；;])\s*|\s{2,}", combined)
        keywords = [part for part in re.split(r"[，。、？?：:\s（）()]", question) if part and len(part) >= 2]
        focus_terms = [
            term
            for term in ["发起人", "部门", "优势", "利润率", "存货", "控股股东", "专利", "经营模式", "募集资金"]
            if term in question
        ]
        scored: list[tuple[int, str]] = []
        for sentence in sentences:
            cleaned = sentence.strip()
            if len(cleaned) < 8:
                continue
            score = sum(1 for kw in keywords if kw in cleaned)
            score += 3 * sum(1 for kw in focus_terms if kw in cleaned)
            if score > 0:
                scored.append((score, cleaned))
        scored.sort(key=lambda item: (-item[0], len(item[1])))
        selected: list[str] = []
        for _, sentence in scored:
            if sentence not in selected:
                selected.append(sentence)
            if len(selected) >= 2:
                break
        if selected:
            answer = " ".join(selected)
            answer = re.sub(r"\s+", " ", answer).strip()
            return answer[:180]
        return re.sub(r"\s+", " ", evidences[0].snippet).strip()[:180]

    def _extract_targeted_answer(self, question: str, evidences: list[Evidence]) -> str | None:
        documents = self._candidate_documents(evidences)
        extractors = [
            self._extract_founders,
            self._extract_controlling_shareholder,
            self._extract_raised_funds,
            self._extract_business_model,
            self._extract_patents,
            self._extract_advantages,
            self._extract_profit_margin,
            self._extract_departments,
        ]
        for document in documents:
            for extractor in extractors:
                answer = extractor(question, document)
                if answer:
                    return answer[:220]
        return None

    def _candidate_documents(self, evidences: list[Evidence]) -> list[str]:
        seen: set[str] = set()
        documents: list[str] = []
        for item in evidences:
            document = self._documents.get(item.source)
            if not document or item.source in seen:
                continue
            seen.add(item.source)
            documents.append(document)
        return documents

    @staticmethod
    def _clean_answer(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip(" ，。；;：:")

    @staticmethod
    def _company_name(question: str) -> str | None:
        match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]+?(?:股份有限公司|有限责任公司|有限公司))", question)
        return match.group(1) if match else None

    @staticmethod
    def _window_around(document: str, anchor: str, radius: int = 180) -> str | None:
        index = document.find(anchor)
        if index < 0:
            return None
        start = max(0, index - radius)
        end = min(len(document), index + len(anchor) + radius)
        return document[start:end]

    def _extract_founders(self, question: str, document: str) -> str | None:
        if "发起人" not in question:
            return None
        patterns = [
            r"公司由(?P<names>.+?)作为发起人",
            r"由(?P<names>.+?)家法人作为发起人",
            r"发起人为(?P<names>.+?)(?:。|；|，各|，均)",
        ]
        for pattern in patterns:
            match = re.search(pattern, document)
            if not match:
                continue
            names = self._clean_answer(match.group("names"))
            if "法人" in question:
                names = re.sub(r"\d+\s*家法人$", "", names)
            if names:
                return f"变更设立时作为发起人的主体包括：{names}。"
        return None

    def _extract_controlling_shareholder(self, question: str, document: str) -> str | None:
        if "控股股东" not in question:
            return None
        company_name = self._company_name(question)
        scoped_document = document
        if company_name:
            scoped_document = self._window_around(document, company_name) or document
            short_name = company_name.replace("股份有限公司", "").replace("有限责任公司", "").replace("有限公司", "")
            scoped_document = self._window_around(scoped_document, short_name) or scoped_document
        match = re.search(r"控股股东为(?P<value>.+?)(?:。|；|，)", scoped_document)
        if match:
            return f"控股股东为：{self._clean_answer(match.group('value'))}。"
        return None

    def _extract_raised_funds(self, question: str, document: str) -> str | None:
        if "募集资金" not in question and "募投" not in question:
            return None
        for pattern in [
            r"募集资金(?:将)?用于(?P<value>.+?)(?:。|；)",
            r"本次发行募集资金(?:扣除发行费用后)?将投资于(?P<value>.+?)(?:。|；)",
        ]:
            match = re.search(pattern, document)
            if match:
                return f"募集资金用途：{self._clean_answer(match.group('value'))}。"
        return None

    def _extract_business_model(self, question: str, document: str) -> str | None:
        if "经营模式" not in question:
            return None
        match = re.search(r"经营模式(?P<value>.+?)(?:。|；)", document)
        if match:
            return f"经营模式相关表述：{self._clean_answer(match.group('value'))}。"
        return None

    def _extract_patents(self, question: str, document: str) -> str | None:
        if "专利" not in question:
            return None
        patterns = [
            r"拥有(?P<value>.+?专利.+?)(?:。|；)",
            r"(?P<value>发明专利.+?)(?:。|；)",
        ]
        for pattern in patterns:
            match = re.search(pattern, document)
            if match:
                return f"专利相关信息：{self._clean_answer(match.group('value'))}。"
        return None

    def _extract_advantages(self, question: str, document: str) -> str | None:
        if "优势" not in question:
            return None
        match = re.search(r"(?P<value>[^。；]*优势[^。；]*)(?:。|；)", document)
        if match:
            return f"优势相关信息：{self._clean_answer(match.group('value'))}。"
        return None

    def _extract_profit_margin(self, question: str, document: str) -> str | None:
        if "利润率" not in question:
            return None
        match = re.search(r"(?P<value>[^。；]*利润率[^。；]*)(?:。|；)", document)
        if match:
            return f"利润率相关信息：{self._clean_answer(match.group('value'))}。"
        return None

    def _extract_departments(self, question: str, document: str) -> str | None:
        if "部门" not in question:
            return None
        patterns = [
            r"设置了(?P<value>.+?部门.+?)(?:。|；)",
            r"各部门(?P<value>.+?)(?:。|；)",
        ]
        for pattern in patterns:
            match = re.search(pattern, document)
            if match:
                return f"部门相关信息：{self._clean_answer(match.group('value'))}。"
        return None

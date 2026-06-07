"""
评估模块 - RAG回答质量评估
提供精确率(Precision)、召回率(Recall)、F1分数、置信度等指标
"""
import re
import math


class RAGEvaluator:
    """RAG回答质量评估器"""

    def __init__(self, precision_threshold: float = 0.30, use_llm_judge: bool = True):
        self.precision_threshold = precision_threshold
        self.use_llm_judge = use_llm_judge
        self._llm_client = None

    def set_llm_client(self, client):
        self._llm_client = client

    def evaluate_retrieval(self, hits: list[dict], question: str) -> dict:
        """
        评估检索质量
        返回: precision, recall_estimate, f1, confidence, avg_score
        """
        if not hits:
            return {
                "precision": 0.0,
                "recall_estimate": 0.0,
                "f1": 0.0,
                "confidence": 0.0,
                "avg_similarity": 0.0,
                "relevant_count": 0,
                "total_retrieved": 0,
            }

        total = len(hits)
        scores = [h.get("score", 0.0) for h in hits]
        avg_score = sum(scores) / total

        # Precision: 相关性得分超过阈值的比例
        relevant = sum(1 for s in scores if s >= self.precision_threshold)
        precision = relevant / total if total > 0 else 0.0

        # 估计召回率: 基于得分分布 + 关键词覆盖率
        keyword_coverage = self._estimate_keyword_coverage(hits, question)
        score_factor = min(1.0, avg_score / 0.6)
        recall_estimate = round((keyword_coverage * 0.6 + score_factor * 0.4), 3)

        # F1
        f1 = 0.0
        if precision + recall_estimate > 0:
            f1 = round(2 * precision * recall_estimate / (precision + recall_estimate), 3)

        # 置信度: 综合指标
        confidence = round((avg_score * 0.4 + precision * 0.3 + recall_estimate * 0.3), 3)

        return {
            "precision": round(precision, 3),
            "recall_estimate": recall_estimate,
            "f1": f1,
            "confidence": confidence,
            "avg_similarity": round(avg_score, 3),
            "relevant_count": relevant,
            "total_retrieved": total,
        }

    def _estimate_keyword_coverage(self, hits: list[dict], question: str) -> float:
        """基于关键词在检索结果中的覆盖情况估算召回率"""
        import jieba
        jieba.setLogLevel(20)

        # 提取问题关键词
        stopwords = {'什么', '怎么', '哪些', '这个', '那个', '一个', '可以', '没有',
                     '我们', '他们', '你们', '自己', '如何', '为什么', '相关', '涉及',
                     '情况', '的', '了', '是', '在', '和', '与', '或', '及', '对', '为',
                     'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'what', 'how', 'which', 'why', 'who', 'where', 'when', 'does', 'do'}

        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', question))
        if is_chinese:
            words = [w for w in jieba.lcut(question) if len(w) >= 2 and w not in stopwords]
        else:
            words = [w.lower() for w in question.split()
                     if len(w) >= 3 and w.lower() not in stopwords]

        if not words:
            return 0.5  # 无法提取关键词时保守估计

        # 统计关键词在检索结果中的出现情况
        combined_text = " ".join([h.get("text", "") for h in hits]).lower()
        covered = sum(1 for w in words if w.lower() in combined_text)
        return covered / len(words)

    def llm_judge_relevance(self, question: str, answer: str, contexts: list[dict]) -> dict:
        """
        使用LLM评估回答质量
        返回: accuracy_score, answer_completeness, evidence_support
        """
        if not self._llm_client or not self.use_llm_judget:
            return {}

        context_preview = "\n\n".join([c["text"][:200] for c in contexts[:3]])

        prompt = (
            f"作为评估专家，请评估以下RAG问答系统的回答质量。\n\n"
            f"【问题】{question}\n\n"
            f"【检索到的上下文片段】\n{context_preview}\n\n"
            f"【系统回答】{answer}\n\n"
            f"请从以下维度评分（0-1之间的小数）：\n"
            f"1. accuracy: 回答是否准确，是否基于上下文\n"
            f"2. completeness: 回答是否完整覆盖了问题的各个角度\n"
            f"3. evidence_support: 回答是否充分引用了上下文中的证据\n\n"
            f"只返回JSON格式，例如：\n"
            f"{{\"accuracy\": 0.9, \"completeness\": 0.8, \"evidence_support\": 0.85}}"
        )

        try:
            resp = self._llm_client.generate(
                "你是一个严格的RAG回答质量评估专家。只输出JSON。",
                prompt
            )
            start = resp.find("{")
            end = resp.rfind("}")
            if start >= 0 and end >= 0:
                import json
                result = json.loads(resp[start:end+1])
                avg = (result.get("accuracy", 0) + result.get("completeness", 0)
                       + result.get("evidence_support", 0)) / 3
                result["overall"] = round(avg, 3)
                return result
        except Exception:
            pass
        return {"accuracy": 0, "completeness": 0, "evidence_support": 0, "overall": 0}

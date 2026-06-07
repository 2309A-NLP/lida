"""
Query理解模块 - 意图识别、消歧、分解、关键词提取
精简prompt，减少LLM调用开销
"""
import json


class QueryUnderstanding:
    """Query理解器，分析用户问题意图、提取关键词、消歧、分解"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def analyze(self, question: str) -> dict:
        """分析用户问题，返回结构化分析结果"""
        prompt = (
            f"分析这个招股说明书相关问题的意图。\n"
            f"问题：{question}\n\n"
            f"返回JSON格式：\n"
            f"{{\n"
            f"  \"intent\": \"factual|comparison|list|definition|calculation\",\n"
            f"  \"entities\": [\"关键实体名称\"],\n"
            f"  \"is_complex\": true/false,\n"
            f"  \"keywords\": [\"关键词\"],\n"
            f"  \"sub_questions\": [\"子问题1\", \"子问题2\"],\n"
            f"  \"ambiguities\": [\"可能的歧义\"],\n"
            f"  \"clarified_question\": \"消歧后的问题\"\n"
            f"}}\n"
            f"只返回JSON，不要其他文字。"
        )

        try:
            resp = self.llm.generate("你是一个专业的Query分析助手，只输出JSON。", prompt)
            # 提取 JSON
            start = resp.find("{")
            end = resp.rfind("}")
            if start >= 0 and end >= 0:
                result = json.loads(resp[start:end+1])
            else:
                result = self._default_analysis(question)
        except Exception:
            result = self._default_analysis(question)

        # 补全缺字段
        defaults = self._default_analysis(question)
        for k, v in defaults.items():
            if k not in result:
                result[k] = v

        return result

    def _default_analysis(self, question: str) -> dict:
        """兜底分析结果"""
        return {
            "intent": "factual",
            "entities": [],
            "is_complex": len(question) > 30,
            "keywords": [],
            "sub_questions": [],
            "ambiguities": [],
            "clarified_question": question,
        }

    def create_disambiguation_prompt(self, question: str, analysis: dict) -> str | None:
        """生成消歧追问"""
        ambiguities = analysis.get("ambiguities", [])
        if not ambiguities:
            return None
        return f"您的问题「{question}」中有以下歧义需要澄清：{'、'.join(ambiguities[:3])}"

    def format_analysis(self, analysis: dict) -> str:
        """格式化分析结果用于展示"""
        lines = [
            f"意图: {analysis.get('intent', '?')}",
            f"复杂问题: {'是' if analysis.get('is_complex') else '否'}",
        ]
        keywords = analysis.get("keywords", [])
        if keywords:
            lines.append(f"关键词: {', '.join(keywords)}")
        entities = analysis.get("entities", [])
        if entities:
            lines.append(f"实体: {', '.join(entities)}")
        sub_questions = analysis.get("sub_questions", [])
        if sub_questions:
            lines.append(f"子问题: {'; '.join(sub_questions)}")
        return "\n".join(lines)

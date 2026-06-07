"""
LLM客户端 - 支持OpenAI兼容接口（DeepSeek）
流式生成，Session复用，表格感知
"""
import os
import json
import requests
from openai import OpenAI


class LLMClient:
    """LLM客户端，封装大语言模型调用"""

    def __init__(self, provider: str = "deepseek", model: str = "deepseek-chat",
                 api_key: str = "", base_url: str = "https://api.deepseek.com",
                 temperature: float = 0.1, max_tokens: int = 512,
                 streaming: bool = True):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.streaming = streaming
        self._openai_client = None
        self._session = requests.Session()

    def _get_client(self) -> OpenAI:
        """懒加载OpenAI客户端"""
        if self._openai_client is not None:
            return self._openai_client
        key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        kwargs = {"api_key": key, "max_retries": 1, "timeout": 30}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._openai_client = OpenAI(**kwargs)
        return self._openai_client

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """非流式生成完整回答"""
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""

    def generate_stream(self, system_prompt: str, user_prompt: str):
        """流式生成，逐token产出"""
        client = self._get_client()
        stream = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def _build_rag_context(self, contexts: list[dict]) -> str:
        """构建RAG上下文，包含表格标记"""
        parts = []
        for c in contexts:
            text = c["text"]
            page_num = c.get("page_num", "?")
            has_table = "【表格数据】" in text
            label = f"[第{page_num}页{'·表格' if has_table else ''}]"
            parts.append(f"{label} {text}")
        return "\n\n---\n\n".join(parts)

    def generate_with_rag(self, question: str, contexts: list[dict]) -> str:
        """RAG生成：基于上下文的回答"""
        context_text = self._build_rag_context(contexts)

        has_tables = any("【表格数据】" in c["text"] for c in contexts)
        table_instruction = ""
        if has_tables:
            table_instruction = (
                "5. 如果上下文包含表格数据，请以Markdown表格形式输出\n"
                "6. 表格数据优先于正文文本中的描述性数据\n"
            )

        system_prompt = (
            "你是一个专业的招股说明书问答助手。请严格基于提供的招股说明书内容回答用户问题。\n"
            "要求：\n"
            "1. 只使用提供的上下文信息，不要编造\n"
            "2. 如果上下文中没有相关信息，请明确说明\n"
            "3. 回答简洁准确，引用具体数据时保留原始数值和单位\n"
            "4. 使用中文回答\n"
            + table_instruction
        )

        user_prompt = (
            f"## 招股说明书相关内容\n{context_text}\n\n"
            f"## 用户问题\n{question}\n\n"
            f"请基于上述招股说明书内容回答问题："
        )

        return self.generate(system_prompt, user_prompt)

    def generate_with_rag_stream(self, question: str, contexts: list[dict]):
        """流式RAG生成"""
        context_text = self._build_rag_context(contexts)

        has_tables = any("【表格数据】" in c["text"] for c in contexts)
        table_instruction = ""
        if has_tables:
            table_instruction = (
                "5. 如果上下文包含表格数据，请以Markdown表格形式输出\n"
                "6. 表格数据优先于正文文本中的描述性数据\n"
            )

        system_prompt = (
            "你是一个专业的招股说明书问答助手。请严格基于提供的招股说明书内容回答用户问题。\n"
            "要求：\n"
            "1. 只使用提供的上下文信息，不要编造\n"
            "2. 如果上下文中没有相关信息，请明确说明\n"
            "3. 回答简洁准确，引用具体数据时保留原始数值和单位\n"
            "4. 使用中文回答\n"
            + table_instruction
        )

        user_prompt = (
            f"## 招股说明书相关内容\n{context_text}\n\n"
            f"## 用户问题\n{question}\n\n"
            f"请基于上述招股说明书内容回答问题："
        )

        yield from self.generate_stream(system_prompt, user_prompt)

    def generate_directly(self, question: str) -> str:
        """纯LLM回答（不参考文档）"""
        system_prompt = "你是一个问答助手。请根据你的知识直接回答用户问题。如果不知道，就说不知道。"
        return self.generate(system_prompt, question)

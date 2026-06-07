"""
文本分割模块 - 按页分割PDF文档，保留页码信息，并拼接表格文本
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextChunker:
    """文本分割器，按页切分，每块保留来源页码，并融入表格文本"""

    def __init__(self, chunk_size: int = 300, chunk_overlap: int = 30,
                 separators: list[str] | None = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", "；", "，", " ", ""]

    def _format_table(self, table: list[list]) -> str:
        """将表格格式化为markdown样式文本"""
        if not table:
            return ""
        lines = []
        for row in table:
            cleaned = [str(cell).strip() if cell else "" for cell in row]
            lines.append(" | ".join(cleaned))
        return "\n".join(lines)

    def _page_text_with_tables(self, page_data: dict) -> str:
        """将页面文本和表格合并为一块文本"""
        text = page_data.get("text", "").strip()
        tables = page_data.get("tables", [])

        if not tables:
            return text

        table_texts = []
        for table in tables:
            formatted = self._format_table(table)
            if formatted:
                table_texts.append(formatted)

        if not table_texts:
            return text

        combined = text
        for tt in table_texts:
            combined += f"\n\n【表格数据】\n{tt}"

        return combined.strip()

    def split_document(self, parsed_pdf: dict) -> list[dict]:
        """按页分割PDF，每块保留page_num，合并表格数据"""
        result = []
        chunk_id = 0

        for page_data in parsed_pdf["pages"]:
            page_num = page_data["page_num"]
            page_text = self._page_text_with_tables(page_data)
            if not page_text:
                continue

            if len(page_text) < self.chunk_size * 0.6:
                result.append({
                    "chunk_id": chunk_id,
                    "text": page_text,
                    "source": parsed_pdf["file_name"],
                    "page_num": page_num,
                    "char_count": len(page_text),
                })
                chunk_id += 1
            else:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=self.separators,
                    length_function=len,
                )
                chunks = splitter.split_text(page_text)
                for chunk in chunks:
                    result.append({
                        "chunk_id": chunk_id,
                        "text": chunk,
                        "source": parsed_pdf["file_name"],
                        "page_num": page_num,
                        "char_count": len(chunk),
                    })
                    chunk_id += 1

        if not result and parsed_pdf.get("combined_text", "").strip():
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.separators,
                length_function=len,
            )
            for i, chunk in enumerate(splitter.split_text(parsed_pdf["combined_text"])):
                result.append({
                    "chunk_id": i,
                    "text": chunk,
                    "source": parsed_pdf["file_name"],
                    "page_num": None,
                    "char_count": len(chunk),
                })

        return result

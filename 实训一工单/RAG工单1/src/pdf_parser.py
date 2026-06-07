"""
PDF解析模块 - 解析招股说明书PDF，提取文字和表格
"""
import pdfplumber
import fitz
from pathlib import Path


class PDFParser:
    """PDF文档解析器，逐页提取文字和表格，保留页码信息"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {file_path}")

    def extract_text_with_pdfplumber(self) -> list[dict]:
        """逐页提取文字和表格"""
        pages_data = []
        with pdfplumber.open(self.file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                pages_data.append({
                    "page_num": i + 1,
                    "text": text,
                    "tables": tables,
                    "total_pages": len(pdf.pages),
                })
        return pages_data

    def _format_table(self, table: list[list]) -> str:
        """将表格格式化为可读文本"""
        if not table:
            return ""
        lines = []
        for row in table:
            cleaned = [str(cell).strip() if cell else "" for cell in row]
            lines.append(" | ".join(cleaned))
        return "\n".join(lines)

    def parse(self) -> dict:
        """综合解析PDF，返回结构化结果"""
        pages_data = self.extract_text_with_pdfplumber()

        table_texts = []
        for page_data in pages_data:
            for table in page_data["tables"]:
                formatted = self._format_table(table)
                if formatted:
                    table_texts.append(f"[第{page_data['page_num']}页表格]\n{formatted}")

        return {
            "file_name": self.file_path.name,
            "total_pages": len(pages_data),
            "pages": pages_data,
            "tables_text": "\n\n".join(table_texts),
            "combined_text": "\n\n".join([p["text"] for p in pages_data]),
        }

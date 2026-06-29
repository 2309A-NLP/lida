"""工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def main() -> None:
    pdf_path = Path("requirements.pdf")
    output_path = Path("outputs/requirements_text.txt")

    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"===== PAGE {index} =====\n{text.strip()}\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()

"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
import networkx as nx

from fund_qa.config import settings
from fund_qa.data.schema import SchemaInspector


def _configure_chinese_font() -> str | None:
    font_candidates = [
        "C:/Windows/Fonts/NotoSansSC-VF.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for font_path in font_candidates:
        if Path(font_path).exists():
            font_manager.fontManager.addfont(font_path)
            font_name = font_manager.FontProperties(fname=font_path).get_name()
            rcParams["font.sans-serif"] = [font_name]
            rcParams["font.family"] = "sans-serif"
            rcParams["axes.unicode_minus"] = False
            return font_name
    return None


def main() -> None:
    font_name = _configure_chinese_font()
    inspector = SchemaInspector(settings.sqlite_db_path)
    tables = inspector.inspect(include_row_counts=True)
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = settings.docs_dir / "db_schema.md"
    graph_path = settings.outputs_dir / "db_relationship_graph.png"
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)

    if not tables:
        markdown_path.write_text(
            "# 基金DB数据表关系图\n\n当前未检测到SQLite数据库文件，待 `dataset/博金杯比赛数据.db` 就位后可重新生成。\n",
            encoding="utf-8",
        )
        return

    graph = nx.DiGraph()
    for table in tables:
        graph.add_node(table.name)
        for src, dst_table, dst_col in table.foreign_keys:
            graph.add_edge(table.name, dst_table, label=f"{src}->{dst_col}")

    plt.figure(figsize=(18, 12))
    pos = nx.spring_layout(graph, seed=42, k=1.6)
    nx.draw_networkx_nodes(graph, pos, node_size=2600, node_color="#d9edf7")
    label_kwargs = {"font_size": 8}
    if font_name:
        label_kwargs["font_family"] = font_name
    nx.draw_networkx_labels(graph, pos, **label_kwargs)
    nx.draw_networkx_edges(graph, pos, arrows=True, arrowstyle="->", arrowsize=18, edge_color="#4a708b")
    edge_labels = nx.get_edge_attributes(graph, "label")
    if edge_labels:
        edge_kwargs = {"edge_labels": edge_labels, "font_size": 7}
        if font_name:
            edge_kwargs["font_family"] = font_name
        nx.draw_networkx_edge_labels(graph, pos, **edge_kwargs)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(graph_path, dpi=180)
    plt.close()

    lines = ["# 基金DB数据表关系图", "", f"共检测到 {len(tables)} 张表。", ""]
    for table in tables:
        lines.append(f"## {table.name}")
        lines.append(f"- 行数：{table.row_count}")
        for column in table.columns:
            lines.append(f"- 字段：`{column.name}` `{column.data_type}`")
        if table.foreign_keys:
            for src, dst_table, dst_col in table.foreign_keys:
                lines.append(f"- 外键：`{src}` -> `{dst_table}.{dst_col}`")
        lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

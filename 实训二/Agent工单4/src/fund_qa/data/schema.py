"""工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务。"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from pathlib import Path


@dataclass(slots=True)
class ColumnInfo:
    name: str
    data_type: str
    not_null: bool
    primary_key: bool


@dataclass(slots=True)
class TableInfo:
    name: str
    columns: list[ColumnInfo]
    foreign_keys: list[tuple[str, str, str]]
    row_count: int | None = None


class SchemaInspector:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._cache: dict[bool, list[TableInfo]] = {}

    def available(self) -> bool:
        return self.db_path.exists()

    def inspect(self, include_row_counts: bool = False) -> list[TableInfo]:
        if not self.available():
            return []
        if include_row_counts in self._cache:
            return self._cache[include_row_counts]
        conn = sqlite3.connect(self.db_path)
        try:
            table_names = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            tables: list[TableInfo] = []
            for table_name in table_names:
                columns = [
                    ColumnInfo(
                        name=row[1],
                        data_type=row[2],
                        not_null=bool(row[3]),
                        primary_key=bool(row[5]),
                    )
                    for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
                ]
                foreign_keys = [
                    (row[3], row[2], row[4])
                    for row in conn.execute(f'PRAGMA foreign_key_list("{table_name}")').fetchall()
                ]
                row_count = None
                if include_row_counts:
                    row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
                tables.append(
                    TableInfo(
                        name=table_name,
                        columns=columns,
                        foreign_keys=foreign_keys,
                        row_count=row_count,
                    )
                )
            self._cache[include_row_counts] = tables
            return tables
        finally:
            conn.close()

    def as_text(self, include_row_counts: bool = False) -> str:
        parts: list[str] = []
        for table in self.inspect(include_row_counts=include_row_counts):
            table_header = f"[{table.name}]"
            if include_row_counts and table.row_count is not None:
                table_header += f" rows={table.row_count}"
            parts.append(table_header)
            for column in table.columns:
                flags = []
                if column.primary_key:
                    flags.append("PK")
                if column.not_null:
                    flags.append("NOT NULL")
                suffix = f" ({', '.join(flags)})" if flags else ""
                parts.append(f"  - {column.name}: {column.data_type}{suffix}")
            if table.foreign_keys:
                parts.append("  - foreign_keys:")
                for src, dst_table, dst_col in table.foreign_keys:
                    parts.append(f"    {src} -> {dst_table}.{dst_col}")
        return "\n".join(parts)

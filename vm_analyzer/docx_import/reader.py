"""Чтение таблиц из DOCX. Только текст ячеек: макросы и вложения не выполняются."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


@dataclass
class RawTable:
    index: int                      # порядковый номер таблицы в документе (с 1)
    title: str                      # ближайший непустой абзац перед таблицей
    rows: list[list[str]]           # первая строка — заголовок
    merged_rows: set[int] = field(default_factory=set)  # номера строк (с 1) с объединёнными ячейками


def read_tables(path: str | Path) -> list[RawTable]:
    doc = Document(str(path))
    result: list[RawTable] = []
    last_text = ""
    n = 0
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = Paragraph(child, doc).text.strip()
            if text:
                last_text = text
        elif tag == "tbl":
            n += 1
            table = Table(child, doc)
            rows: list[list[str]] = []
            merged: set[int] = set()
            for r_i, row in enumerate(table.rows, start=1):
                cells = row.cells
                if len({id(c._tc) for c in cells}) < len(cells):
                    merged.add(r_i)
                rows.append([c.text.strip() for c in cells])
            result.append(RawTable(n, last_text, rows, merged))
            last_text = ""
    return result

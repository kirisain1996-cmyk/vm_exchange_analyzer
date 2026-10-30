"""Генерация синтетических данных по образцу: DOCX с таблицей и TXT обмена."""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document

HEADER = ["Слово данных", "Диапазон", "Название параметра", "Коэффициент", "Примечание"]
ROWS = [
    ["0", "15 – 8", "Счетчик 1", "-", "-"],
    ["0", "7 – 4", "Параметр А", "-", "1000 – Включен\n0000 – Отключен\nОстальное - ошибка"],
    ["0", "3 – 0", "Резерв", "", ""],
    ["1", "15 – 0", "Параметр Б", "-", ""],
    ["2", "15 – 0", "Резерв", "-", "-"],
    ["3", "15 – 0", "Резерв", "-", "-"],
    ["4", "15 – 8", "Температура Ф1", "0.0025", ""],
    ["4", "7 - 0", "Температура Ф2", "0.0025", "-"],
]
ARRAY_ID = 893

EXCHANGE = """Время\tУникальный номер массива\tСлова данных
17:15:12.531\t893\t0A80;FFFF;0000;0000;C8C8
17:15:12.631\t893\t0530;0001;0000;0000;1000
17:15:12.731\t893\t0200;0002;0000;0000;00FF
"""


def make_docx(path: Path, array_id: int = ARRAY_ID, rows=ROWS, header=HEADER) -> None:
    doc = Document()
    doc.add_paragraph(f"Таблица {array_id} – Название массива 1")
    t = doc.add_table(rows=1, cols=len(header))
    for c, h in zip(t.rows[0].cells, header):
        c.text = h
    for r in rows:
        cells = t.add_row().cells
        for c, v in zip(cells, r):
            c.text = v
    doc.save(str(path))


def make_all(out: Path) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    d, x = out / "sample_arrays.docx", out / "sample_exchange.txt"
    make_docx(d)
    x.write_text(EXCHANGE, encoding="utf-8")
    return d, x


if __name__ == "__main__":
    print(*make_all(Path(sys.argv[1] if len(sys.argv) > 1 else "samples")))

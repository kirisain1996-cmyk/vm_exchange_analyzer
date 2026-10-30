"""Чтение .txt-файлов обмена.

Формат строки:  ВРЕМЯ  НОМЕР_МАССИВА  СЛОВО;СЛОВО;СЛОВО;...
Время — ЧЧ:ММ:СС[.мс], номер — целое, слова — HEX (1–4 цифры), разделитель «;».
Колонки разделены пробелами/табуляцией. Строка заголовка («Время ...») пропускается.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path

_LINE = re.compile(r"^\s*(\d{1,2}):(\d{2}):(\d{2})(?:[.,](\d{1,6}))?\s+(\d+)\s+(.+?)\s*$")
_HEX = re.compile(r"^[0-9A-Fa-f]{1,4}$")


@dataclass
class Record:
    line_no: int
    time_text: str
    time: time
    array_id: int
    words: list[int]
    words_text: str = ""      # слова как в файле (для отображения)


@dataclass
class ReadIssue:
    line_no: int
    message: str

    def __str__(self) -> str:
        return f"строка {self.line_no}: {self.message}"


def parse_line(line: str, line_no: int, byte_order: str = "big") -> Record:
    m = _LINE.match(line)
    if not m:
        raise ValueError("строка не соответствует формату «время номер_массива слова;через;точку_с_запятой»")
    h, mi, s, frac, aid, words_txt = m.groups()
    if int(h) > 23 or int(mi) > 59 or int(s) > 59:
        raise ValueError(f"некорректное время {h}:{mi}:{s}")
    micro = int((frac or "0").ljust(6, "0"))
    words: list[int] = []
    for pos, tok in enumerate(words_txt.split(";"), start=1):
        tok = tok.strip()
        if tok == "" and pos > 1 and pos == len(words_txt.split(";")):
            continue  # допускаем завершающую «;»
        if not _HEX.match(tok):
            raise ValueError(f"слово №{pos} «{tok}» не является HEX-числом (1–4 цифры)")
        v = int(tok, 16)
        if byte_order == "little":
            v = ((v & 0xFF) << 8) | (v >> 8)
        words.append(v)
    return Record(line_no, m.group(0).split()[0], time(int(h), int(mi), int(s), micro), int(aid), words,
                  ";".join(t.strip() for t in words_txt.split(";") if t.strip()))


def read_exchange(path: str | Path, byte_order: str = "big",
                  encoding: str = "utf-8-sig") -> tuple[list[Record], list[ReadIssue]]:
    if byte_order not in ("big", "little"):
        raise ValueError("byte_order должен быть 'big' или 'little'")
    records: list[Record] = []
    issues: list[ReadIssue] = []
    with open(path, "r", encoding=encoding) as f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            if line.lstrip().lower().startswith("время"):
                continue
            try:
                records.append(parse_line(line, n, byte_order))
            except ValueError as e:
                issues.append(ReadIssue(n, str(e)))
    return records, issues

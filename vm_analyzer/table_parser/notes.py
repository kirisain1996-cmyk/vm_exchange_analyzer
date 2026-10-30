"""Разбор примечаний с расшифровкой кодов.

Синтаксис (v1): записи разделяются «;» или переводом строки,
код и описание — дефисом/тире (с пробелами вокруг). Специальный ключ
«Остальное» задаёт значение по умолчанию.

Код:
  0x1F / 0b1010          — явный префикс;
  только 0/1 и длина == ширине поля — двоичный;
  иначе — десятичный.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

DASHES = "-‐‑‒–—−"
_REST = re.compile(r"^остальное$", re.IGNORECASE)


@dataclass
class NoteResult:
    enum: dict[int, str] = field(default_factory=dict)
    default: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def has_rules(self) -> bool:
        return bool(self.enum) or self.default is not None


def is_empty(text: str) -> bool:
    t = text.strip()
    return t == "" or all(ch in DASHES + " " for ch in t)


def parse_code(code: str, width: int) -> int | None:
    c = code.strip()
    try:
        if c.lower().startswith("0x"):
            return int(c, 16)
        if c.lower().startswith("0b"):
            return int(c, 2)
        if re.fullmatch(r"[01]+", c) and len(c) == width:
            return int(c, 2)
        if re.fullmatch(r"\d+", c):
            return int(c, 10)
    except ValueError:
        pass
    return None


def parse_note(text: str, width: int) -> NoteResult:
    res = NoteResult()
    if is_empty(text):
        return res
    entries = [e.strip() for e in re.split(r"[;\n\r]+", text) if e.strip()]
    for entry in entries:
        parts = re.split(rf"\s+[{DASHES}]\s+|\s*[‒–—−]\s*", entry, maxsplit=1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            # допускаем «Остальное-ошибка» без пробелов
            m = re.match(rf"^(остальное)\s*[{DASHES}]\s*(.+)$", entry, re.IGNORECASE)
            if not m:
                res.problems.append(f"не удалось разобрать запись «{entry}»")
                continue
            parts = [m.group(1), m.group(2)]
        key, desc = parts[0].strip(), parts[1].strip()
        if _REST.match(key):
            if res.default is not None:
                res.problems.append("правило «Остальное» задано повторно")
            res.default = desc
            continue
        val = parse_code(key, width)
        if val is None:
            res.problems.append(f"неизвестный формат кода «{key}»")
            continue
        if val >= (1 << width):
            res.problems.append(f"код «{key}» не помещается в поле шириной {width} бит")
            continue
        if val in res.enum:
            res.problems.append(f"код «{key}» задан повторно")
            continue
        res.enum[val] = desc
    return res

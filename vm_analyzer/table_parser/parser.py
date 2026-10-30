"""Преобразование RawTable в ArrayConfig по формальному набору колонок."""
from __future__ import annotations

import re
from pathlib import Path

from ..config.model import ArrayConfig, Issue, Parameter
from ..docx_import.reader import RawTable
from .notes import DASHES, is_empty, parse_note

_COLUMN_ALIASES = {
    "word": {"словоданных", "слово"},
    "range": {"диапазон", "биты"},
    "name": {"названиепараметра", "название", "параметр"},
    "coef": {"коэффициент", "коэф"},
    "note": {"примечание", "примечания"},
}
_REQUIRED = {"word": "Слово данных", "range": "Диапазон", "name": "Название параметра"}
_TITLE = re.compile(rf"^\s*Таблица\s+(\d+)\s*[{DASHES}]\s*(.*?)\s*$", re.IGNORECASE)
_RANGE = re.compile(rf"^\s*(\d+)\s*(?:[{DASHES}]\s*(\d+))?\s*$")


def _norm_header(text: str) -> str:
    t = text.lower().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]", "", t)


def _num(text: str) -> float | None:
    try:
        return float(text.strip().replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def parse_table(table: RawTable, source_file: str = "",
                array_id: int | None = None) -> tuple[ArrayConfig | None, list[Issue]]:
    label = f"Таблица #{table.index}" + (f" «{table.title}»" if table.title else "")
    issues: list[Issue] = []

    def err(row, col, msg): issues.append(Issue("error", label, row, col, msg))
    def warn(row, col, msg): issues.append(Issue("warning", label, row, col, msg))

    if not table.rows:
        err(None, None, "таблица пуста")
        return None, issues

    # --- заголовок таблицы -> id и имя массива
    m = _TITLE.match(table.title)
    array_name = (m.group(2) if m and m.group(2) else table.title) or f"Массив {table.index}"
    if array_id is None and m:
        array_id = int(m.group(1))
    if array_id is None:
        err(None, None, "не удалось определить уникальный номер массива "
                        "(ожидается заголовок «Таблица N – Название»)")

    # --- колонки по нормализованным заголовкам
    cols: dict[str, int] = {}
    extra: list[str] = []
    for i, h in enumerate(table.rows[0]):
        key = next((k for k, al in _COLUMN_ALIASES.items() if _norm_header(h) in al), None)
        if key and key not in cols:
            cols[key] = i
        else:
            extra.append(h)
    for k, title in _REQUIRED.items():
        if k not in cols:
            err(1, title, "отсутствует обязательная колонка")
    if extra:
        warn(1, None, f"дополнительные колонки не используются: {', '.join(extra)}")
    if any(i.level == "error" for i in issues):
        return None, issues

    params: list[Parameter] = []
    used_bits: dict[int, int] = {}
    max_word = -1

    for r_i, row in enumerate(table.rows[1:], start=2):
        def cell(key: str) -> str:
            idx = cols.get(key)
            return row[idx] if idx is not None and idx < len(row) else ""

        word_txt, range_txt = cell("word").strip(), cell("range").strip()
        name = cell("name").strip()
        coef_txt, note_txt = cell("coef"), cell("note")
        if r_i in table.merged_rows:
            warn(r_i, None, "в строке есть объединённые ячейки; проверьте результат")

        word = int(word_txt) if re.fullmatch(r"\d+", word_txt) else None
        if word is not None:
            max_word = max(max_word, word)

        if name == "" or name.lower() == "резерв":
            continue  # строка игнорируется без ошибки

        ok = True
        if word is None:
            err(r_i, "Слово данных", f"неверный индекс слова «{word_txt}»"); ok = False
        rm = _RANGE.match(range_txt)
        hi = lo = 0
        if not rm:
            err(r_i, "Диапазон", f"неверный диапазон битов «{range_txt}»"); ok = False
        else:
            hi = int(rm.group(1)); lo = int(rm.group(2)) if rm.group(2) is not None else hi
            if lo > hi or hi > 15:
                err(r_i, "Диапазон", f"недопустимый диапазон {hi}–{lo}: нужно 15 ≥ верхний ≥ нижний ≥ 0")
                ok = False
        coef = None
        if not is_empty(coef_txt):
            coef = _num(coef_txt)
            if coef is None:
                err(r_i, "Коэффициент", f"коэффициент «{coef_txt}» не является числом"); ok = False
        if not ok:
            continue

        mask = ((1 << (hi - lo + 1)) - 1) << lo
        if used_bits.get(word, 0) & mask:
            err(r_i, "Диапазон", f"биты {hi}–{lo} слова {word} пересекаются с другим параметром")
            continue
        used_bits[word] = used_bits.get(word, 0) | mask

        note = parse_note(note_txt, hi - lo + 1)
        for p in note.problems:
            warn(r_i, "Примечание", p)
        if note.has_rules and coef is not None:
            warn(r_i, "Коэффициент", "у параметра заданы и коды, и коэффициент; коэффициент не применяется")
            coef = None
        params.append(Parameter(
            name=name, word_index=word, bit_high=hi, bit_low=lo, coefficient=coef,
            enum={str(k): v for k, v in note.enum.items()}, enum_default=note.default,
            source_note=note_txt.strip(), source_row=r_i))

    if any(i.level == "error" for i in issues):
        return None, issues  # никакого частичного сохранения
    if max_word < 0:
        err(None, None, "в таблице нет ни одного корректного индекса слова")
        return None, issues

    cfg = ArrayConfig(
        array_id=array_id, array_name=array_name, word_count=max_word + 1, parameters=params,
        source_file=Path(source_file).name if source_file else "", source_table=table.title,
        warnings=[str(i) for i in issues if i.level == "warning"])
    return cfg, issues

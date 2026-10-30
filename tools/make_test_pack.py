"""Генератор тестового набора: DOCX с массивами, файлы обмена и эталон ожидаемых значений.

Ожидаемые значения считаются здесь НЕЗАВИСИМО от декодера приложения (свои формулы,
явные числовые значения кодов), поэтому набор годится для настоящей сверки.

Запуск:  python -m tools.make_test_pack [папка] [число_строк_большого_файла]
"""
from __future__ import annotations

import csv
import random
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

HEADER = ["Слово данных", "Диапазон", "Название параметра", "Коэффициент", "Примечание"]


@dataclass
class P:
    word: int
    hi: int
    lo: int
    name: str                      # "Резерв" — игнорируется
    coef: str = "-"                # как в документе: "0.0025", "0,01", "-", ""
    codes: list = field(default_factory=list)   # [(текст_кода_в_документе, число, описание)]
    default: str | None = None     # текст «Остальное»
    note: str | None = None        # свой текст примечания (перекрывает codes)
    rng: str | None = None         # свой текст диапазона
    gen: str = "rand"              # rand | counter | low (малые значения)
    note_sep: str = "\n"

    @property
    def reserve(self) -> bool:
        return self.name.strip().lower() == "резерв"

    def range_text(self) -> str:
        return self.rng or f"{self.hi} – {self.lo}"

    def note_text(self) -> str:
        if self.note is not None:
            return self.note
        if not self.codes and self.default is None:
            return "-"
        parts = [f"{c} – {d}" for c, _, d in self.codes]
        if self.default is not None:
            parts.append(f"Остальное - {self.default}")
        return self.note_sep.join(parts)


@dataclass
class A:
    id: int
    name: str
    params: list
    merge_words: bool = False

    @property
    def word_count(self) -> int:
        return max(p.word for p in self.params) + 1


ONOFF = [("1", 1, "Включено"), ("0", 0, "Отключено")]

ARRAYS = [
    A(1, "Название массива 1", [   # точная копия образца
        P(0, 15, 8, "Счетчик 1", gen="counter"),
        P(0, 7, 4, "Параметр А", codes=[("1000", 8, "Включен"), ("0000", 0, "Отключен")], default="ошибка"),
        P(0, 3, 0, "Резерв", coef=""),
        P(1, 15, 0, "Параметр Б", note=""),
        P(2, 15, 0, "Резерв"), P(3, 15, 0, "Резерв"),
        P(4, 15, 8, "Температура Ф1", coef="0.0025", note=""),
        P(4, 7, 0, "Температура Ф2", coef="0.0025", rng="7 - 0"),
    ]),
    A(2, "Датчики давления", [
        P(0, 15, 0, "Давление 1", coef="0.01"),
        P(1, 15, 8, "Давление 2", coef="0,01"),                   # запятая
        P(1, 7, 0, "Температура корпуса", coef="0.5"),
        P(2, 15, 0, "Резерв"),
        P(3, 15, 12, "Режим", codes=[("0001", 1, "Ожидание"), ("0010", 2, "Работа"), ("0100", 4, "Тест")],
          default="неизвестно"),
        P(3, 11, 0, "Счетчик циклов", gen="counter"),
    ]),
    A(3, "Питание и нагреватели", [
        P(0, 15, 15, "Питание А", codes=ONOFF),
        P(0, 14, 14, "Питание Б", codes=ONOFF),
        P(0, 13, 13, "Нагреватель", codes=[("1", 1, "Включен"), ("0", 0, "Выключен")], default="ошибка"),
        P(0, 12, 8, "Резерв"),
        P(0, 7, 0, "Напряжение, В", coef="0.1"),
        P(1, 15, 0, "Ток, А", coef="0.001"),
        P(2, 15, 8, "Резерв"),
        P(2, 7, 0, "Температура БП", coef="1"),
    ]),
    A(4, "Состояния узлов", [
        P(0, 15, 14, "Узел 1", codes=[("00", 0, "Нет"), ("01", 1, "Первый"), ("10", 2, "Второй"), ("11", 3, "Оба")]),
        P(0, 13, 12, "Узел 2", codes=[("00", 0, "Нет"), ("01", 1, "Первый"), ("10", 2, "Второй"), ("11", 3, "Оба")]),
        P(0, 11, 8, "Резерв"),
        P(0, 7, 0, "Состояние контроллера",
          codes=[("0", 0, "Норма"), ("1", 1, "Предупреждение"), ("2", 2, "Авария")], default="Неизвестно"),
        P(1, 15, 0, "Код события", codes=[("0x0F00", 0x0F00, "Готов"), ("0xFFFF", 0xFFFF, "Сбой")],
          default="Прочее"),
    ]),
    A(5, "Частоты и масштабы", [
        P(0, 15, 0, "Частота, кГц", coef="0.001"),
        P(1, 15, 0, "Целый множитель", coef="10"),
        P(2, 15, 8, "Дробный множитель", coef="2.5"),
        P(2, 7, 0, "Малый множитель", coef="0.00001"),
        P(3, 15, 0, "Без коэффициента", coef=""),
    ]),
    A(6, "Минимальный", [P(0, 15, 0, "Единственный параметр", gen="counter")]),
    A(7, "Большой (10 слов)", [
        P(w, hi, lo, f"Поле {w}.{i}", gen="counter" if (w + i) % 5 == 0 else "rand")
        for w in range(10) for i, (hi, lo) in enumerate([(15, 12), (11, 8), (7, 4), (3, 0)])
    ]),
    A(8, "Разные тире и диапазоны", [
        P(0, 15, 8, "Старший байт", rng="15 – 8"),
        P(0, 7, 4, "Тетрада", rng="7 — 4"),
        P(0, 3, 1, "Три бита", rng="3-1"),
        P(0, 0, 0, "Один бит", rng="0", codes=[("0", 0, "Нет"), ("1", 1, "Да")]),
        P(1, 5, 5, "Бит 5", rng="5", codes=ONOFF),
        P(1, 15, 6, "Старшие", rng="15−6"),                       # знак минус U+2212
        P(1, 4, 0, "Младшие", rng="4 ‒ 0"),                       # цифровое тире U+2012
    ]),
    A(9, "Примечания в одну строку", [
        P(0, 15, 12, "Режим", note_sep="; ", codes=[("0001", 1, "А"), ("0010", 2, "Б"), ("0011", 3, "В")],
          default="Н/Д"),
        P(0, 11, 8, "Флаг", note="1 – Да; 0 – Нет; остальное – ошибка",
          codes=[("1", 1, "Да"), ("0", 0, "Нет")], default="ошибка"),
        P(0, 7, 0, "Канал", note="10 – Канал 10\n20 – Канал 20\n30 – Канал 30\nОстальное – другой",
          codes=[("10", 10, "Канал 10"), ("20", 20, "Канал 20"), ("30", 30, "Канал 30")], default="другой"),
    ]),
    A(10, "Объединённые ячейки слова", [
        P(0, 15, 8, "Канал А", gen="counter"),
        P(0, 7, 4, "Канал Б"),
        P(0, 3, 0, "Канал В"),
        P(1, 15, 8, "Канал Г", coef="0.5"),
        P(1, 7, 0, "Канал Д", coef="0.5"),
    ], merge_words=True),
    A(11, "Коды без «Остальное»", [
        P(0, 15, 12, "Тип", codes=[("0000", 0, "Нет"), ("0001", 1, "Один"), ("0010", 2, "Два")]),
        P(0, 11, 0, "Значение", gen="counter"),
    ]),
    A(893, "Образец из файла обмена", [
        P(0, 15, 8, "Счетчик", gen="counter"),
        P(0, 7, 4, "Параметр А", codes=[("1000", 8, "Включен"), ("0000", 0, "Отключен")], default="ошибка"),
        P(1, 15, 0, "Параметр Б"),
        P(4, 15, 8, "Температура Ф1", coef="0.0025"),
        P(4, 7, 0, "Температура Ф2", coef="0.0025"),
    ]),
]


# ----------------------------------------------------------------- DOCX
def _style(doc: Document) -> None:
    st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11)


def add_table(doc: Document, title: str, rows: list[list[str]], header=HEADER, merge_words=False) -> None:
    doc.add_paragraph(title)
    t = doc.add_table(rows=1, cols=len(header)); t.style = "Table Grid"
    for c, h in zip(t.rows[0].cells, header):
        c.text = h
    for r in rows:
        cells = t.add_row().cells
        for c, v in zip(cells, r):
            c.text = v
    for row in t.rows:
        for c, w in zip(row.cells, [2.8, 2.8, 3.4, 3.0, 4.4][:len(header)]):
            c.width = Cm(w)
    if merge_words:
        i = 1
        while i < len(t.rows):
            j = i
            while j + 1 < len(t.rows) and t.rows[j + 1].cells[0].text == t.rows[i].cells[0].text:
                j += 1
            if j > i:
                for k in range(i + 1, j + 1):
                    t.rows[k].cells[0].text = ""
                t.rows[i].cells[0].merge(t.rows[j].cells[0])
            i = j + 1
    doc.add_paragraph("")


def array_rows(a: A) -> list[list[str]]:
    return [[str(p.word), p.range_text(), p.name, p.coef, p.note_text()] for p in a.params]


def make_main_docx(path: Path) -> None:
    doc = Document(); _style(doc)
    doc.add_heading("Описание массивов обмена (тестовый набор)", level=1)
    for a in ARRAYS:
        add_table(doc, f"Таблица {a.id} – {a.name}", array_rows(a), merge_words=a.merge_words)
    doc.save(str(path))


def make_error_docx(path: Path) -> None:
    ok = [["0", "15 – 8", "Норма", "-", "-"], ["0", "7 – 0", "Норма 2", "0.5", ""]]
    doc = Document(); _style(doc)
    doc.add_heading("Тест валидации: таблицы с ошибками", level=1)
    add_table(doc, "Таблица 100 – Корректная таблица", ok)
    add_table(doc, "Таблица 101 – Нет колонки «Диапазон»",
              [["0", "Параметр", "-", "-"]], header=["Слово данных", "Название параметра", "Коэффициент", "Примечание"])
    add_table(doc, "Таблица 102 – Диапазон 3–8 (нижняя больше верхней)", [["0", "3 – 8", "Плохой", "-", "-"]])
    add_table(doc, "Таблица 103 – Бит 16 вне слова", [["0", "16 – 8", "Плохой", "-", "-"]])
    add_table(doc, "Таблица 104 – Коэффициент не число", [["0", "15 – 0", "Плохой", "abc", "-"]])
    add_table(doc, "Таблица 105 – Пересечение битов",
              [["0", "15 – 8", "А", "-", "-"], ["0", "10 – 4", "Б", "-", "-"]])
    add_table(doc, "Таблица 106 – Неверный индекс слова", [["x", "15 – 0", "Плохой", "-", "-"]])
    add_table(doc, "Заголовок без номера таблицы", [["0", "15 – 0", "Параметр", "-", "-"]])
    add_table(doc, "Таблица 108 – Предупреждения (примечание не разобрано)",
              [["0", "15 – 8", "Параметр", "-", "включено когда горит лампа"], ["0", "7 – 0", "Второй", "-", "-"]])
    add_table(doc, "Таблица 109 – Коэффициент вместе с кодами (предупреждение)",
              [["0", "3 – 0", "Параметр", "2", "1 – Да; 0 – Нет"]])
    add_table(doc, "Таблица 110 – Дополнительная колонка (предупреждение)",
              [["0", "15 – 0", "Параметр", "-", "-", "Ед. изм."]], header=HEADER + ["Единицы"])
    doc.save(str(path))


# ------------------------------------------------------------- обмены
def _fmt(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return "0" if s in ("-0", "") else s


def expected_text(p: P, raw: int) -> str:
    for _, val, desc in p.codes:
        if val == raw:
            return desc
    if p.codes or p.default is not None:
        return p.default if p.default is not None else str(raw)
    c = p.coef.strip().replace(",", ".")
    if c not in ("", "-"):
        return _fmt(Decimal(c) * raw)
    return str(raw)


def make_record(a: A, rng: random.Random, i: int):
    words = [0] * a.word_count
    covered = [0] * a.word_count
    expected = []
    for p in a.params:
        w = p.hi - p.lo + 1
        mask = ((1 << w) - 1) << p.lo
        if p.reserve:
            continue
        covered[p.word] |= mask
        if p.codes and rng.random() < 0.9:
            raw = rng.choice(p.codes)[1]
        elif p.gen == "counter":
            raw = (i * 3) % (1 << w)
        else:
            raw = rng.randrange(1 << w)
        words[p.word] |= raw << p.lo
        expected.append((p, raw))
    for k in range(a.word_count):                  # «Резерв» заполняем шумом — он обязан игнорироваться
        words[k] |= rng.getrandbits(16) & ~covered[k] & 0xFFFF
    return words, expected


def gen_exchange(n: int, seed: int, ids=None, with_expected=True):
    rng = random.Random(seed)
    arrays = [a for a in ARRAYS if ids is None or a.id in ids]
    lines, golden, ms = [], [], 0
    for i in range(n):
        a = rng.choice(arrays)
        words, exp = make_record(a, rng, i)
        ms += rng.choice([50, 100, 100, 100, 150])
        t = 17 * 3600 * 1000 + 15 * 60000 + 12000 + ms
        ts = f"{(t // 3600000) % 24:02d}:{(t // 60000) % 60:02d}:{(t // 1000) % 60:02d}.{t % 1000:03d}"
        lines.append((ts, a.id, words))
        if with_expected:
            for p, raw in exp:
                golden.append((ts, a.id, p, expected_text(p, raw)))
    return lines, golden


HEAD = "Время\tУникальный номер массива\tСлова данных"


def write_exchange(path: Path, lines, swap=False) -> None:
    def w(x): return ((x & 0xFF) << 8 | x >> 8) if swap else x
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEAD + "\n")
        for ts, aid, words in lines:
            f.write(f"{ts}\t{aid}\t{';'.join(f'{w(x):04X}' for x in words)}\n")


def write_golden(path: Path, lines, golden) -> None:
    """Эталон: номер строки файла (заголовок = 1) → значения параметров."""
    rows, ptr = [], 0
    for n, (ts, aid, _) in enumerate(lines, start=2):
        a = next(x for x in ARRAYS if x.id == aid)
        k = sum(1 for p in a.params if not p.reserve)
        for ts2, aid2, p, text in golden[ptr:ptr + k]:
            assert (ts2, aid2) == (ts, aid)
            rows.append((n, ts, aid, p.name, p.word, f"{p.hi}-{p.lo}", text))
        ptr += k
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.writer(f, delimiter=";")
        wr.writerow(["line", "time", "array_id", "parameter", "word", "bits", "expected_value"])
        wr.writerows(rows)


def make_error_exchange(path: Path) -> list[str]:
    L = [HEAD,                                                          # 1
         "17:15:12.100\t893\t0A80;FFFF;0000;0000;C8C8",                 # 2 ок
         "17:15:12.200\t893\t0A80;FFFF;0000;0000",                      # 3 мало слов (4 из 5)
         "17:15:12.300\t893\t0A80;FFFF;0000;0000;C8C8;0000",            # 4 много слов
         "17:15:12.400\t9999\t0001;0002",                               # 5 нет конфигурации
         "17:15:12.500\t893\t0A80;FFFF;0000;ABHB;C8C8",                 # 6 не HEX
         "25:61:00.000\t893\t0A80;FFFF;0000;0000;C8C8",                 # 7 время
         "17:15:12.700 893",                                            # 8 нет слов
         "17:15:12.800\t893\t0A80;FFFF;0000;0000;C8C8D",                # 9 5 HEX-цифр
         "просто мусор",                                                # 10
         "",                                                            # 11 пустая — пропуск
         "17:15:13.000\t893\t0A80;FFFF;0000;0000;C8C8;",                # 12 завершающая «;» — ок
         "17:15:13.100\t893\t0A80;;0000;0000;C8C8",                     # 13 пустое слово
         "17:15:13.200\t893\t0200;0001;0000;0000;0100"]                 # 14 ок
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return ["2: ок", "3: ошибка — 4 слова вместо 5", "4: ошибка — 6 слов вместо 5",
            "5: ошибка — нет конфигурации массива 9999", "6: ошибка формата — слово №4 не HEX",
            "7: ошибка формата — время 25:61:00", "8: ошибка формата — нет слов",
            "9: ошибка формата — слово из 5 HEX-цифр", "10: ошибка формата — мусор",
            "11: пустая строка — игнорируется", "12: ок (завершающая «;» допустима)",
            "13: ошибка формата — пустое слово №2", "14: ок"]


def main(out: Path, big_n: int = 50000) -> None:
    out.mkdir(parents=True, exist_ok=True)
    make_main_docx(out / "arrays_main.docx")
    make_error_docx(out / "arrays_with_errors.docx")

    lines, golden = gen_exchange(600, seed=2026)
    write_exchange(out / "exchange_all_arrays.txt", lines)
    write_golden(out / "exchange_all_arrays_expected.csv", lines, golden)
    write_exchange(out / "exchange_all_arrays_little_endian.txt", lines, swap=True)
    s_lines, _ = gen_exchange(30, seed=7, ids={1, 893}, with_expected=False)
    write_exchange(out / "exchange_small_1_and_893.txt", s_lines)
    big, _ = gen_exchange(big_n, seed=99, with_expected=False)
    write_exchange(out / "exchange_large.txt", big)
    expl = make_error_exchange(out / "exchange_with_errors.txt")

    (out / "README_test_pack.md").write_text(f"""# Тестовый набор

| Файл | Назначение |
|---|---|
| arrays_main.docx | 12 корректных таблиц (номера массивов: {', '.join(str(a.id) for a in ARRAYS)}); таблица 1 — копия образца; таблица 10 — с объединёнными ячейками |
| arrays_with_errors.docx | Таблицы с ошибками и предупреждениями (проверка валидации) |
| exchange_all_arrays.txt | 600 записей по всем массивам из arrays_main.docx |
| exchange_all_arrays_expected.csv | Эталон значений для exchange_all_arrays.txt (посчитан независимо от декодера) |
| exchange_all_arrays_little_endian.txt | Те же данные с перестановкой байтов в словах; декодировать с `--byte-order little`, результат = тому же эталону |
| exchange_small_1_and_893.txt | 30 записей, только массивы 1 и 893 |
| exchange_large.txt | {big_n} записей (нагрузочный тест) |
| exchange_with_errors.txt | Строки с ошибками формата (используется массив 893) |

## Ожидаемый результат импорта arrays_with_errors.docx
Принять: таблицы 100 (без замечаний), 108 (предупреждение: примечание не разобрано), 109 (предупреждение: коэффициент не применяется),
110 (предупреждение: дополнительная колонка). Отклонить: 101 (нет колонки), 102, 103, 104, 105, 106 и таблицу без номера в заголовке.

## Ожидаемый результат для exchange_with_errors.txt (номера строк файла, 1 = заголовок)
""" + "\n".join(f"- {e}" for e in expl) + "\n", encoding="utf-8")
    print("готово:", out)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "samples/test_pack"),
         int(sys.argv[2]) if len(sys.argv) > 2 else 50000)

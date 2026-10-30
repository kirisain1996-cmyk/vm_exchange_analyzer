"""Консольный интерфейс: импорт DOCX в JSON и декодирование обмена в CSV."""
from __future__ import annotations

import argparse
import csv
import socket
import sys
from pathlib import Path

from .config.model import ArrayConfig
from .decoder import decode_record
from .docx_import import read_tables
from .exchange_import import read_exchange
from .table_parser.parser import parse_table


def _block_network() -> None:
    """Страховка автономности: любая попытка открыть сокет — ошибка."""
    def _deny(*a, **k):
        raise RuntimeError("Сетевые обращения запрещены в VM Exchange Analyzer")
    socket.socket = _deny  # type: ignore[assignment]
    socket.create_connection = _deny  # type: ignore[assignment]


def cmd_import_docx(args) -> int:
    id_map = {}
    for item in args.array_id or []:
        t, _, a = item.partition("=")
        id_map[int(t)] = int(a)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    tables = read_tables(args.docx)
    if not tables:
        print("В документе не найдено таблиц", file=sys.stderr); return 1
    bad = 0
    for t in tables:
        cfg, issues = parse_table(t, args.docx, id_map.get(t.index))
        for i in issues:
            print(i)
        if cfg is None:
            print(f"  -> таблица #{t.index} отклонена"); bad += 1; continue
        path = out / f"array_{cfg.array_id}.json"
        cfg.save(path)
        print(f"  -> {path} (массив {cfg.array_id} «{cfg.array_name}», "
              f"слов: {cfg.word_count}, параметров: {len(cfg.parameters)})")
    return 1 if bad else 0


def cmd_decode(args) -> int:
    configs = {}
    for p in Path(args.configs).glob("*.json"):
        c = ArrayConfig.load(p); configs[c.array_id] = c
    if not configs:
        print("Конфигурации не найдены", file=sys.stderr); return 1
    records, read_issues = read_exchange(args.exchange, args.byte_order)
    for i in read_issues:
        print(f"[error] {i}")
    problems = len(read_issues)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["line", "time", "array_id", "array_name", "parameter", "word",
                    "bits", "word_hex", "raw", "value", "status"])
        for r in records:
            cfg = configs.get(r.array_id)
            if cfg is None:
                print(f"[error] строка {r.line_no}: нет конфигурации для массива {r.array_id}")
                problems += 1; continue
            try:
                values = decode_record(cfg, r.words)
            except ValueError as e:
                print(f"[error] строка {r.line_no}: {e}"); problems += 1; continue
            for v in values:
                p = v.parameter
                w.writerow([r.line_no, r.time_text, r.array_id, cfg.array_name, p.name,
                            p.word_index, f"{p.bit_high}-{p.bit_low}", f"{v.word:04X}",
                            v.raw, v.text, v.status])
    print(f"Записей: {len(records)}, проблем: {problems} -> {args.out}")
    return 1 if problems else 0


def main(argv=None) -> int:
    _block_network()
    ap = argparse.ArgumentParser(prog="vm_analyzer")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("import-docx", help="DOCX -> JSON-конфигурации")
    a.add_argument("docx"); a.add_argument("-o", "--out", default="configs")
    a.add_argument("--array-id", action="append", metavar="ТАБЛИЦА=НОМЕР",
                   help="переопределить номер массива для таблицы #N (по порядку в документе)")
    a.set_defaults(fn=cmd_import_docx)
    d = sub.add_parser("decode", help="TXT обмена + конфигурации -> CSV")
    d.add_argument("exchange"); d.add_argument("-c", "--configs", default="configs")
    d.add_argument("-o", "--out", default="decoded.csv")
    d.add_argument("--byte-order", choices=["big", "little"], default="big")
    d.set_defaults(fn=cmd_decode)
    args = ap.parse_args(argv)
    return args.fn(args)

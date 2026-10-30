import csv
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.make_sample import HEADER, ROWS, make_all, make_docx  # noqa: E402
from vm_analyzer.config.model import ArrayConfig  # noqa: E402
from vm_analyzer.decoder import decode_record, extract_bits  # noqa: E402
from vm_analyzer.docx_import import read_tables  # noqa: E402
from vm_analyzer.exchange_import import parse_line, read_exchange  # noqa: E402
from vm_analyzer.table_parser.notes import parse_note  # noqa: E402
from vm_analyzer.table_parser.parser import parse_table  # noqa: E402


def build(rows=ROWS, header=HEADER):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.docx"
        make_docx(p, rows=rows, header=header)
        return parse_table(read_tables(p)[0], str(p))


class Bits(unittest.TestCase):
    def test_ranges_inclusive(self):
        self.assertEqual(extract_bits(0xAB4B, 15, 8), 0xAB)
        self.assertEqual(extract_bits(0x00A0, 7, 4), 0xA)
        self.assertEqual(extract_bits(0xFFFF, 15, 0), 0xFFFF)
        self.assertEqual(extract_bits(0x8000, 15, 15), 1)


class Notes(unittest.TestCase):
    def test_example(self):
        r = parse_note("1000 – Включен\n0000 – Отключен\nОстальное - ошибка", 4)
        self.assertEqual(r.enum, {8: "Включен", 0: "Отключен"})
        self.assertEqual(r.default, "ошибка")
        self.assertEqual(r.problems, [])

    def test_semicolons_and_dashes(self):
        r = parse_note("1 — A; 2 – B; Остальное - C", 8)
        self.assertEqual(r.enum, {1: "A", 2: "B"})

    def test_decimal_when_width_differs(self):
        self.assertEqual(parse_note("10 - X", 8).enum, {10: "X"})
        self.assertEqual(parse_note("10 - X", 2).enum, {2: "X"})

    def test_unparseable_warns(self):
        r = parse_note("просто текст без кодов", 4)
        self.assertTrue(r.problems and not r.has_rules)

    def test_empty(self):
        for t in ("", "-", " – "):
            self.assertFalse(parse_note(t, 4).has_rules)


class Parser(unittest.TestCase):
    def test_sample(self):
        cfg, issues = build()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.array_id, 893)
        self.assertEqual(cfg.array_name, "Название массива 1")
        self.assertEqual(cfg.word_count, 5)
        self.assertEqual([p.name for p in cfg.parameters],
                         ["Счетчик 1", "Параметр А", "Параметр Б", "Температура Ф1", "Температура Ф2"])
        self.assertEqual([i for i in issues if i.level == "error"], [])

    def test_errors_reject_whole_table(self):
        bad = ROWS + [["5", "3 – 8", "Плохой", "-", ""]]
        cfg, issues = build(bad)
        self.assertIsNone(cfg)
        self.assertTrue(any("диапазон" in i.message.lower() and i.row == 10 for i in issues))

    def test_non_numeric_coef(self):
        cfg, issues = build([["0", "15 – 0", "X", "abc", ""]])
        self.assertIsNone(cfg)
        self.assertEqual(issues[0].column, "Коэффициент")

    def test_comma_coef(self):
        cfg, _ = build([["0", "15 – 0", "X", "0,5", ""]])
        self.assertEqual(cfg.parameters[0].coefficient, 0.5)

    def test_bit_overlap(self):
        cfg, issues = build([["0", "15 – 8", "A", "", ""], ["0", "9 – 4", "B", "", ""]])
        self.assertIsNone(cfg)

    def test_missing_required_column(self):
        cfg, issues = build(header=["Слово данных", "Название параметра", "Коэффициент", "Примечание", "X"])
        self.assertIsNone(cfg)
        self.assertTrue(any("Диапазон" == i.column for i in issues))

    def test_reordered_columns(self):
        hdr = ["Название параметра", "Диапазон", "Слово данных"]
        cfg, _ = build([["P", "7 - 0", "2"]], hdr)
        self.assertEqual((cfg.parameters[0].word_index, cfg.word_count), (2, 3))

    def test_coef_with_codes_warns(self):
        cfg, issues = build([["0", "3 – 0", "X", "2", "1 - on"]])
        self.assertIsNone(cfg.parameters[0].coefficient)
        self.assertTrue(any(i.level == "warning" for i in issues))

    def test_json_roundtrip(self):
        cfg, _ = build()
        with tempfile.TemporaryDirectory() as d:
            cfg.save(Path(d) / "a.json")
            self.assertEqual(ArrayConfig.load(Path(d) / "a.json"), cfg)


class Decode(unittest.TestCase):
    def setUp(self):
        self.cfg, _ = build()

    def dec(self, words):
        return {v.parameter.name: v for v in decode_record(self.cfg, [int(w, 16) for w in words])}

    def test_values(self):
        r = self.dec(["0A80", "FFFF", "0000", "0000", "C8C8"])
        self.assertEqual(r["Счетчик 1"].text, "10")
        self.assertEqual(r["Параметр А"].text, "Включен")
        self.assertEqual(r["Параметр Б"].text, "65535")
        self.assertEqual(r["Температура Ф1"].text, "0.5")
        self.assertEqual(r["Температура Ф2"].text, "0.5")

    def test_enum_default_and_off(self):
        self.assertEqual(self.dec(["0530", "0", "0", "0", "0"])["Параметр А"].text, "ошибка")
        self.assertEqual(self.dec(["0200", "0", "0", "0", "0"])["Параметр А"].text, "Отключен")

    def test_scaling_exact(self):
        r = self.dec(["0000", "0000", "0000", "0000", "0301"])
        self.assertEqual(r["Температура Ф1"].text, "0.0075")
        self.assertEqual(r["Температура Ф2"].text, "0.0025")

    def test_undecoded_without_default(self):
        cfg, _ = build([["0", "3 – 0", "X", "", "1 - on"]])
        v = decode_record(cfg, [5])[0]
        self.assertEqual((v.status, v.text), ("undecoded", "5"))

    def test_wrong_word_count(self):
        with self.assertRaises(ValueError):
            decode_record(self.cfg, [0, 0])


class Exchange(unittest.TestCase):
    def test_line(self):
        r = parse_line("17:15:12.531\t893\tABCD;01FE;0000", 1)
        self.assertEqual((r.array_id, r.words), (893, [0xABCD, 0x01FE, 0]))
        self.assertEqual(r.time.microsecond, 531000)

    def test_little_endian(self):
        self.assertEqual(parse_line("00:00:00 1 01FE", 1, "little").words, [0xFE01])

    def test_trailing_semicolon_and_spaces(self):
        self.assertEqual(parse_line("17:15:12.5  7  0001; 0002;", 1).words, [1, 2])

    def test_bad_hex(self):
        with self.assertRaises(ValueError):
            parse_line("17:15:12.531 893 ABHB;01FE", 1)

    def test_file_reports_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.txt"
            p.write_text("Время\tНомер\tСлова\n17:15:12.531\t893\t0001\nмусор\n", encoding="utf-8")
            recs, issues = read_exchange(p)
            self.assertEqual((len(recs), issues[0].line_no), (1, 3))


class EndToEnd(unittest.TestCase):
    def test_cli_pipeline_offline(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            docx, txt = make_all(d)
            py = [sys.executable, "-m", "vm_analyzer"]
            env = None
            r = subprocess.run(py + ["import-docx", str(docx), "-o", str(d / "cfg")],
                               capture_output=True, text=True, cwd=ROOT, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = subprocess.run(py + ["decode", str(txt), "-c", str(d / "cfg"), "-o", str(d / "o.csv")],
                               capture_output=True, text=True, cwd=ROOT, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            rows = list(csv.DictReader(open(d / "o.csv", encoding="utf-8-sig"), delimiter=";"))
            self.assertEqual(len(rows), 15)
            self.assertEqual(rows[1]["value"], "Включен")

    def test_network_is_blocked(self):
        from vm_analyzer import cli
        orig = socket.socket
        try:
            cli._block_network()
            with self.assertRaises(RuntimeError):
                socket.socket()
        finally:
            socket.socket = orig


if __name__ == "__main__":
    unittest.main()

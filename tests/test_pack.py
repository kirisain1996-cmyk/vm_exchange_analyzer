"""Сверка декодера с независимым эталоном из генератора тестового набора."""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import make_test_pack  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, "-m", "vm_analyzer", *args],
                          capture_output=True, text=True, cwd=ROOT)


def table(path, key_col):
    return {(r["line"], r["parameter"]): r[key_col]
            for r in csv.DictReader(open(path, encoding="utf-8-sig"), delimiter=";")}


class Pack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.d = Path(cls._tmp.name)
        make_test_pack.main(cls.d, big_n=2000)
        r = run("import-docx", str(cls.d / "arrays_main.docx"), "-o", str(cls.d / "cfg"))
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def check(self, exchange, *extra):
        out = self.d / "out.csv"
        r = run("decode", str(self.d / exchange), "-c", str(self.d / "cfg"), "-o", str(out), *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        exp = table(self.d / "exchange_all_arrays_expected.csv", "expected_value")
        got = table(out, "value")
        self.assertEqual(len(exp), len(got))
        self.assertEqual({k: (exp[k], got.get(k)) for k in exp if exp[k] != got.get(k)}, {})

    def test_big_endian(self):
        self.check("exchange_all_arrays.txt")

    def test_little_endian(self):
        self.check("exchange_all_arrays_little_endian.txt", "--byte-order", "little")

    def test_all_arrays_imported(self):
        self.assertEqual(len(list((self.d / "cfg").glob("*.json"))), 12)

    def test_error_docx(self):
        r = run("import-docx", str(self.d / "arrays_with_errors.docx"), "-o", str(self.d / "cfg_err"))
        self.assertEqual(r.returncode, 1)
        ids = sorted(int(p.stem.split("_")[1]) for p in (self.d / "cfg_err").glob("*.json"))
        self.assertEqual(ids, [100, 108, 109, 110])

    def test_error_exchange(self):
        r = run("decode", str(self.d / "exchange_with_errors.txt"), "-c", str(self.d / "cfg"),
                "-o", str(self.d / "e.csv"))
        self.assertEqual(r.returncode, 1)
        for n in (3, 4, 5, 6, 7, 8, 9, 10, 13):
            self.assertIn(f"строка {n}:", r.stdout)
        self.assertNotIn("строка 2:", r.stdout)
        self.assertNotIn("строка 12:", r.stdout)


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vm_analyzer.exchange_import import Record  # noqa: E402
from vm_analyzer.player.session import Player, Session, format_elapsed, format_speed  # noqa: E402


def rec(n, t, aid):
    return Record(n, "", t, aid, [0])


def sample():
    return Session([
        rec(2, time(17, 15, 12, 0), 1),
        rec(3, time(17, 15, 12, 100000), 2),
        rec(4, time(17, 15, 12, 100000), 1),     # то же время, что и предыдущая
        rec(5, time(17, 15, 13, 500000), 2),
        rec(6, time(17, 15, 14, 0), 1),
    ])


class SessionTests(unittest.TestCase):
    def test_timeline(self):
        s = sample()
        self.assertEqual(s.t_ms, [0, 100, 100, 1500, 2000])
        self.assertEqual(s.duration_ms, 2000)

    def test_index_at(self):
        s = sample()
        self.assertEqual([s.index_at(t) for t in (0, 99, 100, 1499, 1500, 9999)], [0, 0, 2, 2, 3, 4])
        self.assertEqual(s.index_at(-1), -1)

    def test_last_of_array_values_persist(self):
        s = sample()
        # массив 1: записи 0, 2, 4;  массив 2: записи 1, 3
        self.assertEqual([s.last_of_array(1, i) for i in range(5)], [0, 0, 2, 2, 4])
        self.assertEqual([s.last_of_array(2, i) for i in range(5)], [None, 1, 1, 3, 3])
        self.assertIsNone(s.last_of_array(7, 4))
        self.assertIsNone(s.last_of_array(1, -1))

    def test_midnight_rollover(self):
        s = Session([rec(1, time(23, 59, 59, 900000), 1), rec(2, time(0, 0, 0, 100000), 1)])
        self.assertEqual(s.t_ms, [0, 200])
        self.assertEqual(s.clock_text(200), "00:00:00.100")

    def test_small_backward_jitter_is_clamped(self):
        s = Session([rec(1, time(1, 0, 0, 500000), 1), rec(2, time(1, 0, 0, 400000), 1)])
        self.assertEqual(s.t_ms, [0, 0])

    def test_clock_text_and_formats(self):
        s = sample()
        self.assertEqual(s.clock_text(0), "17:15:12.000")
        self.assertEqual(s.clock_text(1500), "17:15:13.500")
        self.assertEqual(format_elapsed(65432), "01:05.432")
        self.assertEqual(format_elapsed(3_725_000), "1:02:05.000")
        self.assertEqual((format_speed(1), format_speed(0.25), format_speed(10)), ("×1", "×0.25", "×10"))

    def test_empty(self):
        s = Session([])
        self.assertEqual((s.duration_ms, s.index_at(0)), (0, -1))


class PlayerTests(unittest.TestCase):
    def test_realtime_one_second_per_second(self):
        p = Player(10_000); p.toggle()
        for _ in range(30):
            p.tick(1000 / 30)                    # 30 кадров = 1 секунда реального времени
        self.assertAlmostEqual(p.t, 1000, delta=1)

    def test_speed_steps(self):
        p = Player(10_000)
        self.assertEqual(p.speed, 1.0)
        p.faster(); p.faster()
        self.assertEqual(p.speed, 5.0)
        p.toggle(); p.tick(1000)
        self.assertAlmostEqual(p.t, 5000)
        for _ in range(20):
            p.slower()
        self.assertEqual(p.speed, 0.1)
        for _ in range(20):
            p.faster()
        self.assertEqual(p.speed, 100.0)

    def test_stops_at_end_and_restarts(self):
        p = Player(1000); p.toggle(); p.tick(5000)
        self.assertEqual((p.t, p.playing), (1000, False))
        p.toggle()
        self.assertEqual((p.t, p.playing), (0, True))

    def test_loop(self):
        p = Player(1000); p.loop = True; p.toggle(); p.tick(2500)
        self.assertAlmostEqual(p.t, 500); self.assertTrue(p.playing)

    def test_seek_clamped_and_paused_tick(self):
        p = Player(1000)
        p.seek(5000); self.assertEqual(p.t, 1000)
        p.seek(-5); self.assertEqual(p.t, 0)
        self.assertFalse(p.tick(100))

    def test_no_play_without_duration(self):
        p = Player(0); p.toggle()
        self.assertFalse(p.playing)


if __name__ == "__main__":
    unittest.main()

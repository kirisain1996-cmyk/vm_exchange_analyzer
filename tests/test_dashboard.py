import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_core import build  # noqa: E402
from vm_analyzer.dashboard.model import (  # noqa: E402
    ColorRule, DashboardLayout, default_position, param_key, snap)
from vm_analyzer.decoder import decode_record  # noqa: E402
from vm_analyzer.storage.workspace import Workspace  # noqa: E402


class Dash(unittest.TestCase):
    def setUp(self):
        self.cfg, _ = build()

    def test_ensure_cards_and_positions(self):
        lay = DashboardLayout(893)
        lay.ensure_cards(self.cfg)
        self.assertEqual(len(lay.cards), 5)
        self.assertEqual((lay.cards[0].x, lay.cards[0].y), default_position(0))
        self.assertNotEqual((lay.cards[1].x, lay.cards[1].y), (lay.cards[0].x, lay.cards[0].y))

    def test_ensure_keeps_user_changes_and_drops_removed(self):
        lay = DashboardLayout(893); lay.ensure_cards(self.cfg)
        k = param_key(self.cfg.parameters[1])
        lay.by_key()[k].x = 500
        lay.cards.append(lay.cards[0].__class__("9:1-0", 0, 0))   # параметра больше нет
        lay.ensure_cards(self.cfg)
        self.assertEqual(len(lay.cards), 5)
        self.assertEqual(lay.by_key()[k].x, 500)

    def test_color_rules(self):
        lay = DashboardLayout(893); lay.ensure_cards(self.cfg)
        card_a = lay.by_key()[param_key(self.cfg.parameters[1])]   # Параметр А (коды)
        card_a.rules = [ColorRule("text", "#00ff00", text="Включен"),
                        ColorRule("text", "#ff0000", text="Отключен")]
        vals = {v.parameter.name: v for v in decode_record(self.cfg, [0x0A80, 0, 0, 0, 0xC8C8])}
        self.assertEqual(card_a.color_for(vals["Параметр А"]), "#00ff00")
        vals = {v.parameter.name: v for v in decode_record(self.cfg, [0x0200, 0, 0, 0, 0])}
        self.assertEqual(card_a.color_for(vals["Параметр А"]), "#ff0000")
        vals = {v.parameter.name: v for v in decode_record(self.cfg, [0x0530, 0, 0, 0, 0])}
        self.assertIsNone(card_a.color_for(vals["Параметр А"]))     # «ошибка» — правила нет

    def test_range_rules_first_match_wins(self):
        lay = DashboardLayout(893); lay.ensure_cards(self.cfg)
        card = lay.by_key()[param_key(self.cfg.parameters[3])]      # Температура Ф1
        card.rules = [ColorRule("range", "#f00", min=0.4), ColorRule("range", "#0f0", max=1)]
        v = decode_record(self.cfg, [0, 0, 0, 0, 0xC800])[3]        # 200 * 0.0025 = 0.5
        self.assertEqual(card.color_for(v), "#f00")
        v = decode_record(self.cfg, [0, 0, 0, 0, 0x0100])[3]        # 0.0025
        self.assertEqual(card.color_for(v), "#0f0")

    def test_range_does_not_match_text(self):
        self.assertFalse(ColorRule("range", "#fff", min=0).matches(
            decode_record(self.cfg, [0x0A80, 0, 0, 0, 0])[1]))

    def test_snap(self):
        self.assertEqual((snap(29), snap(31), snap(0)), (20, 40, 0))

    def test_layout_roundtrip_and_workspace(self):
        lay = DashboardLayout(893); lay.ensure_cards(self.cfg)
        lay.cards[1].rules = [ColorRule("text", "#0f0", text="Включен")]
        lay.cards[1].title = "Реле"; lay.cards[2].visible = False
        with tempfile.TemporaryDirectory() as d:
            ws = Workspace(d)
            ws.save_config(self.cfg); ws.save_layout(lay)
            cfgs, problems = ws.load_configs()
            self.assertEqual((list(cfgs), problems), ([893], []))
            self.assertEqual(ws.load_layout(893), lay)
            self.assertIsNone(ws.load_layout(1))

    def test_corrupt_layout_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Workspace(d)
            ws.layout_path(5).write_text("{oops", encoding="utf-8")
            self.assertIsNone(ws.load_layout(5))
            self.assertTrue((ws.layouts_dir / "array_5.bad.json").exists())


if __name__ == "__main__":
    unittest.main()

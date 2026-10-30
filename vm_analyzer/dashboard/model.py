"""Раскладка карточек параметров и правила цветов (без зависимостей от Qt)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from ..config.model import ArrayConfig, Parameter
from ..decoder import DecodedValue

LAYOUT_SCHEMA = 1
GRID = 20
CARD_W, CARD_H = 200, 120
MIN_W, MIN_H = 100, 60
GAP = 20
COLUMNS = 4


def param_key(p: Parameter) -> str:
    return f"{p.word_index}:{p.bit_high}-{p.bit_low}"


def snap(v: float, grid: int = GRID) -> int:
    return int(round(v / grid)) * grid


@dataclass
class ColorRule:
    kind: str                       # "text" — совпадение с текстом состояния; "range" — число в [min, max]
    color: str                      # "#RRGGBB"
    text: str | None = None
    min: float | None = None        # None = без нижней границы
    max: float | None = None

    def matches(self, v: DecodedValue) -> bool:
        if self.kind == "text":
            return self.text is not None and v.text == self.text
        if self.kind == "range":
            if v.value is None or isinstance(v.value, str):
                return False
            return ((self.min is None or v.value >= self.min) and
                    (self.max is None or v.value <= self.max))
        return False


@dataclass
class CardLayout:
    key: str
    x: int
    y: int
    w: int = CARD_W
    h: int = CARD_H
    title: str | None = None        # переопределение заголовка
    visible: bool = True
    rules: list[ColorRule] = field(default_factory=list)

    def color_for(self, v: DecodedValue | None) -> str | None:
        """Цвет первого сработавшего правила (порядок правил важен)."""
        if v is None:
            return None
        for r in self.rules:
            if r.matches(v):
                return r.color
        return None


def default_position(index: int) -> tuple[int, int]:
    row, col = divmod(index, COLUMNS)
    return GAP + col * (CARD_W + GAP), GAP + row * (CARD_H + GAP)


@dataclass
class DashboardLayout:
    array_id: int
    cards: list[CardLayout] = field(default_factory=list)
    schema_version: int = LAYOUT_SCHEMA

    def by_key(self) -> dict[str, CardLayout]:
        return {c.key: c for c in self.cards}

    def ensure_cards(self, cfg: ArrayConfig) -> None:
        """Синхронизация с конфигурацией: новые параметры добавляются, исчезнувшие удаляются."""
        keys = [param_key(p) for p in cfg.parameters]
        known = self.by_key()
        self.cards = [known[k] for k in keys if k in known] + []
        n = len(self.cards)
        for k in keys:
            if k not in known:
                x, y = default_position(n)
                self.cards.append(CardLayout(k, x, y)); n += 1

    def reset(self, cfg: ArrayConfig) -> None:
        self.cards = []
        self.ensure_cards(cfg)

    # --- JSON
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DashboardLayout":
        if d.get("schema_version") != LAYOUT_SCHEMA:
            raise ValueError(f"Неподдерживаемая версия раскладки: {d.get('schema_version')}")
        cards = []
        for c in d["cards"]:
            c = dict(c)
            c["rules"] = [ColorRule(**r) for r in c.get("rules", [])]
            cards.append(CardLayout(**c))
        return cls(array_id=d["array_id"], cards=cards)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "DashboardLayout":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

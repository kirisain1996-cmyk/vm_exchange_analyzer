"""Детерминированное декодирование 16-битных слов по ArrayConfig."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..config.model import ArrayConfig, Parameter

# Статусы результата
PLAIN, SCALED, ENUM, ENUM_DEFAULT, UNDECODED = "plain", "scaled", "enum", "enum_default", "undecoded"


@dataclass
class DecodedValue:
    parameter: Parameter
    word: int                 # исходное 16-битное слово
    raw: int                  # значение поля до коэффициента
    value: float | int | None # числовой результат (None для текстовых состояний)
    text: str                 # то, что показываем пользователю
    status: str


def extract_bits(word: int, high: int, low: int) -> int:
    return (word >> low) & ((1 << (high - low + 1)) - 1)


def format_decimal(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return "0" if s in ("-0", "") else s


def decode_parameter(p: Parameter, word: int) -> DecodedValue:
    raw = extract_bits(word, p.bit_high, p.bit_low)
    if p.enum or p.enum_default is not None:
        if str(raw) in p.enum:
            return DecodedValue(p, word, raw, None, p.enum[str(raw)], ENUM)
        if p.enum_default is not None:
            return DecodedValue(p, word, raw, None, p.enum_default, ENUM_DEFAULT)
        return DecodedValue(p, word, raw, raw, str(raw), UNDECODED)
    if p.coefficient is not None:
        d = Decimal(str(p.coefficient)) * raw
        return DecodedValue(p, word, raw, float(d), format_decimal(d), SCALED)
    return DecodedValue(p, word, raw, raw, str(raw), PLAIN)


def decode_record(cfg: ArrayConfig, words: list[int]) -> list[DecodedValue]:
    if len(words) != cfg.word_count:
        raise ValueError(
            f"массив {cfg.array_id}: ожидается слов {cfg.word_count}, получено {len(words)}")
    return [decode_parameter(p, words[p.word_index]) for p in cfg.parameters]

"""Модель конфигурации массива и (де)сериализация в JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass
class Issue:
    """Замечание валидации: ошибка или предупреждение."""
    level: str            # "error" | "warning"
    table: str
    row: int | None       # номер строки в таблице DOCX (1 = заголовок)
    column: str | None
    message: str

    def __str__(self) -> str:
        pos = f"строка {self.row}" if self.row else "таблица"
        col = f", колонка «{self.column}»" if self.column else ""
        return f"[{self.level}] {self.table}: {pos}{col}: {self.message}"


@dataclass
class Parameter:
    name: str
    word_index: int
    bit_high: int
    bit_low: int
    coefficient: float | None = None
    enum: dict[str, str] = field(default_factory=dict)   # ключ: целое значение (строкой)
    enum_default: str | None = None                      # правило «Остальное»
    source_note: str = ""
    source_row: int | None = None

    @property
    def width(self) -> int:
        return self.bit_high - self.bit_low + 1


@dataclass
class ArrayConfig:
    array_id: int
    array_name: str
    word_count: int
    parameters: list[Parameter]
    word_size: int = 16
    source_file: str = ""
    source_table: str = ""
    warnings: list[str] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION
    parser_version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "ArrayConfig":
        if d.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Неподдерживаемая версия схемы: {d.get('schema_version')}")
        params = [Parameter(**p) for p in d["parameters"]]
        rest = {k: v for k, v in d.items() if k != "parameters"}
        return cls(parameters=params, **rest)

    @classmethod
    def load(cls, path: str | Path) -> "ArrayConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

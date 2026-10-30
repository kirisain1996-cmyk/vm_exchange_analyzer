"""Рабочая папка: конфигурации массивов и раскладки карточек."""
from __future__ import annotations

from pathlib import Path

from ..config.model import ArrayConfig
from ..dashboard.model import DashboardLayout


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.configs_dir = self.root / "configs"
        self.layouts_dir = self.root / "layouts"
        self.configs_dir.mkdir(parents=True, exist_ok=True)
        self.layouts_dir.mkdir(parents=True, exist_ok=True)

    def load_configs(self) -> tuple[dict[int, ArrayConfig], list[str]]:
        configs, problems = {}, []
        for p in sorted(self.configs_dir.glob("*.json")):
            try:
                c = ArrayConfig.load(p)
                configs[c.array_id] = c
            except (ValueError, KeyError, TypeError, OSError) as e:
                problems.append(f"{p.name}: {e}")
        return configs, problems

    def save_config(self, cfg: ArrayConfig) -> Path:
        p = self.configs_dir / f"array_{cfg.array_id}.json"
        cfg.save(p)
        return p

    def layout_path(self, array_id: int) -> Path:
        return self.layouts_dir / f"array_{array_id}.json"

    def load_layout(self, array_id: int) -> DashboardLayout | None:
        p = self.layout_path(array_id)
        if not p.exists():
            return None
        try:
            return DashboardLayout.load(p)
        except (ValueError, KeyError, TypeError, OSError):
            p.replace(p.with_suffix(".bad.json"))   # не теряем испорченный файл
            return None

    def save_layout(self, layout: DashboardLayout) -> Path:
        p = self.layout_path(layout.array_id)
        layout.save(p)
        return p

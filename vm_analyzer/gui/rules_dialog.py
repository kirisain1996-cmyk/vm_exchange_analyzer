"""Диалог настройки цветов параметра: по состояниям и по диапазонам значений."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from ..config.model import Parameter
from ..dashboard.model import CardLayout, ColorRule


class ColorButton(QPushButton):
    def __init__(self, color: str | None = None):
        super().__init__()
        self.setFixedWidth(90)
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, color: str | None) -> None:
        self.color = color
        if color:
            self.setText(color.upper())
            fg = "#000" if QColor(color).lightness() > 140 else "#fff"
            self.setStyleSheet(f"background:{color}; color:{fg}; border:1px solid #888;")
        else:
            self.setText("нет цвета"); self.setStyleSheet("")

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self.color or "#2ecc71"), self, "Выбор цвета")
        if c.isValid():
            self.set_color(c.name())


def _float(text: str) -> float | None:
    t = text.strip().replace(",", ".")
    return float(t) if t else None


class RulesDialog(QDialog):
    def __init__(self, card: CardLayout, param: Parameter, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Цвета: {card.title or param.name}")
        self.setMinimumWidth(480)
        root = QVBoxLayout(self)
        self.state_rows: list[tuple[str, ColorButton]] = []
        self.range_rows: list[tuple[QLineEdit, QLineEdit, ColorButton, QWidget]] = []

        existing_text = {r.text: r.color for r in card.rules if r.kind == "text"}
        states = list(param.enum.values())
        if param.enum_default is not None and param.enum_default not in states:
            states.append(param.enum_default)
        if states:
            root.addWidget(QLabel("Цвет по состоянию:"))
            grid = QGridLayout()
            for i, s in enumerate(states):
                btn = ColorButton(existing_text.get(s))
                clear = QPushButton("✕"); clear.setFixedWidth(32)
                clear.clicked.connect(lambda _=False, b=btn: b.set_color(None))
                grid.addWidget(QLabel(s), i, 0); grid.addWidget(btn, i, 1); grid.addWidget(clear, i, 2)
                self.state_rows.append((s, btn))
            grid.setColumnStretch(0, 1)
            root.addLayout(grid)

        self.range_box = QVBoxLayout()
        root.addWidget(QLabel("Цвет по диапазону числового значения (первое совпадение):"))
        root.addLayout(self.range_box)
        add = QPushButton("+ Добавить диапазон"); add.clicked.connect(lambda: self._add_range())
        root.addWidget(add)
        for r in card.rules:
            if r.kind == "range":
                self._add_range(r)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _add_range(self, rule: ColorRule | None = None) -> None:
        row = QWidget(); h = QHBoxLayout(row); h.setContentsMargins(0, 0, 0, 0)
        lo, hi = QLineEdit(), QLineEdit()
        lo.setPlaceholderText("от"); hi.setPlaceholderText("до")
        if rule:
            lo.setText("" if rule.min is None else str(rule.min))
            hi.setText("" if rule.max is None else str(rule.max))
        btn = ColorButton(rule.color if rule else "#ef4444")
        rm = QPushButton("✕"); rm.setFixedWidth(32)
        for w in (lo, hi, btn, rm):
            h.addWidget(w)
        entry = (lo, hi, btn, row)
        rm.clicked.connect(lambda: self._remove_range(entry))
        self.range_rows.append(entry)
        self.range_box.addWidget(row)

    def _remove_range(self, entry) -> None:
        self.range_rows.remove(entry)
        entry[3].setParent(None); entry[3].deleteLater()

    def rules(self) -> list[ColorRule]:
        out = [ColorRule("text", b.color, text=s) for s, b in self.state_rows if b.color]
        for lo, hi, btn, _ in self.range_rows:
            try:
                out.append(ColorRule("range", btn.color, min=_float(lo.text()), max=_float(hi.text())))
            except ValueError:
                continue    # нечисловая граница — правило пропускается
        return out

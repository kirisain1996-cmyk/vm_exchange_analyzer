"""Панель плеера сеанса: линия времени, воспроизведение, скорость, шаги."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QPushButton, QSlider, QStyle,
                               QVBoxLayout, QWidget)


class JumpSlider(QSlider):
    """Слайдер, который прыгает в точку клика и плавно тянется мышью."""
    userSeek = Signal(int)

    def __init__(self):
        super().__init__(Qt.Orientation.Horizontal)
        self._drag = False

    def _value_at(self, x: float) -> int:
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(x), max(1, self.width()))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._drag = True
            v = self._value_at(e.position().x()); self.setValue(v); self.userSeek.emit(v)

    def mouseMoveEvent(self, e):
        if self._drag:
            v = self._value_at(e.position().x()); self.setValue(v); self.userSeek.emit(v)

    def mouseReleaseEvent(self, e):
        self._drag = False


class PlayerBar(QWidget):
    playToggled = Signal()
    seekRequested = Signal(int)       # мс от начала сеанса
    stepped = Signal(int)             # -1 / +1 запись
    toBegin = Signal()
    toEnd = Signal()
    speedUp = Signal()
    speedDown = Signal()
    loopChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setObjectName("playerBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.slider = JumpSlider(); self.slider.setRange(0, 1); self.slider.userSeek.connect(self.seekRequested)
        self.elapsed = QLabel("00:00.000 / 00:00.000"); self.elapsed.setObjectName("elapsedLabel")
        self.clock = QLabel("--:--:--.---"); self.clock.setObjectName("clockLabel")

        def btn(text, tip, sig):
            b = QPushButton(text); b.setToolTip(tip); b.clicked.connect(sig)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return b

        self.b_begin = btn("|◀", "В начало (Home)", lambda: self.toBegin.emit())
        self.b_prev = btn("◀", "Предыдущая запись (←)", lambda: self.stepped.emit(-1))
        self.b_play = btn("▶", "Воспроизведение / пауза (Пробел)", lambda: self.playToggled.emit())
        self.b_next = btn("▶", "Следующая запись (→)", lambda: self.stepped.emit(1))
        self.b_end = btn("▶|", "В конец (End)", lambda: self.toEnd.emit())
        self.b_slow = btn("«", "Медленнее ([)", lambda: self.speedDown.emit())
        self.b_fast = btn("»", "Быстрее (])", lambda: self.speedUp.emit())
        self.b_play.setMinimumWidth(56)
        self.speed = QLabel("×1"); self.speed.setObjectName("speedLabel")
        self.speed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loop = QCheckBox("Повтор"); self.loop.toggled.connect(self.loopChanged)
        self.loop.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        row1 = QHBoxLayout(); row1.setSpacing(12)
        row1.addWidget(self.slider, 1); row1.addWidget(self.clock)
        row2 = QHBoxLayout(); row2.setSpacing(6)
        row2.addWidget(self.elapsed); row2.addStretch(1)
        for w in (self.b_begin, self.b_prev, self.b_play, self.b_next, self.b_end):
            row2.addWidget(w)
        row2.addSpacing(18)
        for w in (self.b_slow, self.speed, self.b_fast):
            row2.addWidget(w)
        row2.addSpacing(18); row2.addWidget(self.loop); row2.addStretch(1)
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 8, 14, 8); lay.setSpacing(6)
        lay.addLayout(row1); lay.addLayout(row2)
        self.set_enabled(False)

    def set_enabled(self, on: bool) -> None:
        for w in (self.slider, self.b_begin, self.b_prev, self.b_play, self.b_next, self.b_end,
                  self.b_slow, self.b_fast, self.loop):
            w.setEnabled(on)

    def set_duration(self, ms: int) -> None:
        self.slider.setRange(0, max(1, ms))

    def set_time(self, t_ms: float, clock_text: str, elapsed_text: str) -> None:
        if not self.slider._drag:
            self.slider.setValue(int(t_ms))
        self.clock.setText(clock_text); self.elapsed.setText(elapsed_text)

    def set_playing(self, playing: bool) -> None:
        self.b_play.setText("❚❚" if playing else "▶")

    def set_speed_text(self, text: str) -> None:
        self.speed.setText(text)

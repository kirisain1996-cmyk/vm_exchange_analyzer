"""Окно «Параметры»: свободное поле с перетаскиваемыми карточками."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

from ..config.model import ArrayConfig, Parameter
from ..dashboard.model import (GRID, MIN_H, MIN_W, CardLayout, DashboardLayout, param_key, snap)
from ..decoder import DecodedValue, decode_record
from ..player.session import Session
from ..storage.workspace import Workspace
from .rules_dialog import RulesDialog
from .theme import Theme


class Canvas(QWidget):
    """Поле с точечной сеткой; растёт вслед за карточками."""
    def __init__(self, theme: Theme):
        super().__init__()
        self.theme = theme

    def update_extent(self) -> None:
        r = b = 0
        for c in self.findChildren(CardWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if c.isVisible():
                r = max(r, c.x() + c.width()); b = max(b, c.y() + c.height())
        self.setMinimumSize(r + 60, b + 60)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.theme.bg))
        p.setPen(QColor(self.theme.grid))
        for x in range(0, self.width(), GRID):
            for y in range(0, self.height(), GRID):
                p.drawPoint(x, y)


class Led(QWidget):
    """Круглый индикатор (как на мнемосхеме): погашен или горит цветом правила."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(16, 16)
        self.color: str | None = None
        self.off = "#39444f"

    def set_state(self, color: str | None, off: str) -> None:
        self.color, self.off = color, off
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.color:
            glow = QColor(self.color); glow.setAlpha(70)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(glow); p.drawEllipse(0, 0, 16, 16)
            p.setBrush(QColor(self.color)); p.drawEllipse(3, 3, 10, 10)
        else:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(self.off)); p.drawEllipse(3, 3, 10, 10)


class CardWidget(QFrame):
    changed = Signal()
    GRIP = 18
    HEADER_H = 28

    def __init__(self, card: CardLayout, param: Parameter, theme: Theme, canvas: Canvas):
        super().__init__(canvas)
        self.card, self.param, self.theme, self.canvas = card, param, theme, canvas
        self.value: DecodedValue | None = None
        self._mode: str | None = None
        self.setObjectName("card")
        self.setMouseTracking(True)

        # шапка: идентификатор · название · индикатор
        self.header = QWidget(); self.header.setObjectName("cardHeader"); self.header.setFixedHeight(self.HEADER_H)
        self.ident = QLabel(); self.title = QLabel(); self.led = Led()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        hl = QHBoxLayout(self.header); hl.setContentsMargins(8, 0, 8, 0); hl.setSpacing(8)
        hl.addWidget(self.ident); hl.addWidget(self.title, 1); hl.addWidget(self.led)

        self.val = QLabel("—"); self.meta = QLabel()
        self.val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        for w in (self.header, self.ident, self.title, self.led, self.val, self.meta):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        lay = QVBoxLayout(self); lay.setContentsMargins(1, 1, 1, 1); lay.setSpacing(0)
        lay.addWidget(self.header)
        body = QVBoxLayout(); body.setContentsMargins(8, 4, 8, 6); body.setSpacing(0)
        body.addWidget(self.val, 1); body.addWidget(self.meta)
        lay.addLayout(body, 1)

        self.setGeometry(card.x, card.y, card.w, card.h)
        self.refresh_text(); self.refresh_style()

    # --- отображение
    def _meta_idle(self) -> str:
        return f"слово {self.param.word_index} · биты {self.param.bit_high}–{self.param.bit_low}"

    def refresh_text(self) -> None:
        p = self.param
        self.ident.setText(f"{p.word_index}.{p.bit_high}–{p.bit_low}")
        self.title.setText(self.card.title or p.name)
        self.title.setToolTip(self.card.title or p.name)
        if self.value is None:
            self.meta.setText(self._meta_idle())
        self._fit_value_font()

    def set_value(self, v: DecodedValue | None) -> None:
        self.value = v
        if v is None:
            self.val.setText("—"); self.meta.setText(self._meta_idle())
        else:
            self.val.setText(v.text)
            self.meta.setText(f"слово {self.param.word_index} = {v.word:04X} · поле = {v.raw}"
                              + (" · не расшифровано" if v.status == "undecoded" else ""))
        self.refresh_style()
        self._fit_value_font()

    def refresh_style(self) -> None:
        t = self.theme
        color = self.card.color_for(self.value)
        body_bg, vcol = t.card, (t.text if self.value is not None else t.muted)
        if color:
            q = QColor(color)
            body_bg = f"rgba({q.red()},{q.green()},{q.blue()},34)"; vcol = color
        self.setStyleSheet(
            f"#card{{background:{body_bg};border:1px solid {t.border};border-radius:3px;}}"
            f"#cardHeader{{background:{t.header};border-bottom:1px solid {t.border};}}")
        self.ident.setStyleSheet(f"color:{t.accent};font-weight:700;font-size:14px;background:transparent;")
        self.title.setStyleSheet(f"color:{t.text};font-weight:700;background:transparent;")
        self.val.setStyleSheet(f"color:{vcol};background:transparent;")
        self.meta.setStyleSheet(f"color:{t.muted};font-size:11px;background:transparent;")
        self.led.setVisible(bool(self.card.rules))
        self.led.set_state(color, t.led_off)

    def _fit_value_font(self) -> None:
        """Крупное жирное значение: масштабируется от высоты и сужается, чтобы текст влезал по ширине."""
        body_h = max(16, self.height() - self.HEADER_H - 26)
        size = max(11, int(body_h * 0.6))
        avail = max(20, self.width() - 24)
        f = QFont(self.val.font()); f.setBold(True)
        text = self.val.text()
        while size > 11:
            f.setPixelSize(size)
            if QFontMetrics(f).horizontalAdvance(text) <= avail:
                break
            size -= 1
        f.setPixelSize(size)
        self.val.setFont(f)

    def resizeEvent(self, e):
        self._fit_value_font(); super().resizeEvent(e)

    # --- перетаскивание и изменение размера
    def _in_grip(self, pos: QPoint) -> bool:
        return QRect(self.width() - self.GRIP, self.height() - self.GRIP, self.GRIP, self.GRIP).contains(pos)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._mode = "resize" if self._in_grip(e.position().toPoint()) else "move"
        self._press = e.globalPosition().toPoint()
        self._geo = self.geometry()
        self.raise_()

    def mouseMoveEvent(self, e):
        if self._mode is None:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor if self._in_grip(e.position().toPoint())
                           else Qt.CursorShape.OpenHandCursor)
            return
        d = e.globalPosition().toPoint() - self._press
        g = self._geo
        if self._mode == "move":
            self.move(max(0, snap(g.x() + d.x())), max(0, snap(g.y() + d.y())))
        else:
            self.resize(max(MIN_W, snap(g.width() + d.x())), max(MIN_H, snap(g.height() + d.y())))
        self.canvas.update_extent()

    def mouseReleaseEvent(self, e):
        if self._mode is None:
            return
        self._mode = None
        g = self.geometry()
        self.card.x, self.card.y, self.card.w, self.card.h = g.x(), g.y(), g.width(), g.height()
        self.changed.emit()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        a_col = m.addAction("Цвета и правила…")
        a_ren = m.addAction("Переименовать…")
        a_hide = m.addAction("Скрыть")
        act = m.exec(e.globalPos())
        if act == a_col:
            dlg = RulesDialog(self.card, self.param, self)
            if dlg.exec():
                self.card.rules = dlg.rules(); self.refresh_style(); self.changed.emit()
        elif act == a_ren:
            text, ok = QInputDialog.getText(self, "Заголовок", "Название карточки (пусто — как в таблице):",
                                            text=self.card.title or self.param.name)
            if ok:
                self.card.title = text.strip() or None
                self.refresh_text(); self.changed.emit()
        elif act == a_hide:
            self.card.visible = False; self.hide(); self.canvas.update_extent(); self.changed.emit()


class ParamsView(QWidget):
    decodeError = Signal(str)

    def __init__(self, ws: Workspace, theme: Theme):
        super().__init__()
        self.ws, self.theme = ws, theme
        self.session: Session | None = None
        self._idx = -1                    # текущая позиция плеера (индекс записи)
        self._shown = object()            # какая запись массива сейчас показана
        self.configs: dict[int, ArrayConfig] = {}
        self.cfg: ArrayConfig | None = None
        self.layout_model: DashboardLayout | None = None
        self.cards: dict[str, CardWidget] = {}
        self.record_values: dict[str, DecodedValue] = {}

        self.combo = QComboBox(); self.combo.setMinimumWidth(260)
        self.combo.currentIndexChanged.connect(self._on_combo)
        self.follow = QCheckBox("Переключаться на массив текущей записи"); self.follow.setChecked(False)
        self.follow.toggled.connect(lambda _on: self.set_position(self._idx, force=True))
        self.upd = QLabel("")
        self.hidden_btn = QPushButton("Скрытые: 0"); self.hidden_btn.clicked.connect(self._show_hidden_menu)
        b_reset = QPushButton("Сбросить раскладку"); b_reset.clicked.connect(self.reset_layout)
        b_save = QPushButton("Сохранить раскладку…"); b_save.clicked.connect(self.export_layout)
        b_load = QPushButton("Загрузить раскладку…"); b_load.clicked.connect(self.import_layout)
        top = QHBoxLayout()
        top.addWidget(QLabel("Массив:")); top.addWidget(self.combo); top.addWidget(self.follow)
        top.addSpacing(12); top.addWidget(self.upd)
        top.addStretch(1)
        for b in (self.hidden_btn, b_reset, b_load, b_save):
            top.addWidget(b)

        self.canvas = Canvas(theme)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setWidget(self.canvas)
        self.hint = QLabel("Выберите массив. Карточки можно перетаскивать, тянуть за правый нижний угол; "
                           "правый клик — цвета, переименование, скрытие.")
        self.hint.setStyleSheet(f"color:{theme.muted};")
        self.upd.setStyleSheet(f"color:{theme.accent};font-weight:700;")
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 10, 10, 10)
        lay.addLayout(top); lay.addWidget(self.scroll, 1); lay.addWidget(self.hint)

        self._save_timer = QTimer(self); self._save_timer.setSingleShot(True); self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self.save_now)

    # --- массивы
    def set_configs(self, configs: dict[int, ArrayConfig]) -> None:
        keep = self.cfg.array_id if self.cfg else None
        self.configs = configs
        self.combo.blockSignals(True); self.combo.clear()
        for aid in sorted(configs):
            self.combo.addItem(f"{aid} — {configs[aid].array_name}", aid)
        self.combo.blockSignals(False)
        if configs:
            self.show_array(keep if keep in configs else sorted(configs)[0])
        else:
            self._clear(); self.cfg = None

    def show_array(self, array_id: int) -> None:
        i = self.combo.findData(array_id)
        if i >= 0 and self.combo.currentIndex() != i:
            self.combo.blockSignals(True); self.combo.setCurrentIndex(i); self.combo.blockSignals(False)
        self.save_now()
        self.cfg = self.configs.get(array_id)
        if self.cfg is None:
            return
        lay = self.ws.load_layout(array_id) or DashboardLayout(array_id)
        lay.ensure_cards(self.cfg)
        self.layout_model = lay
        self.record_values = {}
        self._shown = object()
        self.rebuild()
        self.set_position(self._idx, force=True)

    def _on_combo(self, _i) -> None:
        aid = self.combo.currentData()
        if aid is not None:
            self.show_array(aid)

    # --- карточки
    def _clear(self) -> None:
        for c in self.cards.values():
            c.setParent(None); c.deleteLater()
        self.cards = {}
        self.canvas.update_extent(); self._update_hidden_btn()

    def rebuild(self) -> None:
        self._clear()
        params = {param_key(p): p for p in self.cfg.parameters}
        for cl in self.layout_model.cards:
            w = CardWidget(cl, params[cl.key], self.theme, self.canvas)
            w.changed.connect(self._schedule_save)
            w.setVisible(cl.visible)
            self.cards[cl.key] = w
        self.canvas.update_extent(); self._update_hidden_btn()
        self._apply_values()

    def set_session(self, session: Session | None) -> None:
        self.session = session
        self._idx = -1
        self.set_position(-1, force=True)

    def set_position(self, idx: int, force: bool = False) -> None:
        """Позиция плеера изменилась. Карточки показывают ПОСЛЕДНЮЮ запись выбранного массива
        на этот момент: значения меняются только когда приходит новая запись этого массива."""
        self._idx = idx
        if self.session is None or self.cfg is None:
            if self.session is None:
                self._show(None)
            return
        if self.follow.isChecked() and 0 <= idx < len(self.session):
            aid = self.session.records[idx].array_id
            if aid in self.configs and aid != self.cfg.array_id:
                self.show_array(aid); return
        ri = self.session.last_of_array(self.cfg.array_id, idx)
        if ri == self._shown and not force:
            return
        self._shown = ri
        self._show(ri)

    def _show(self, ri: int | None) -> None:
        self.record_values = {}
        if ri is None:
            self.upd.setText("Записей этого массива ещё нет" if self.session else "")
        else:
            rec = self.session.records[ri]
            self.upd.setText(f"Обновлено: {rec.time_text} · строка {rec.line_no}")
            try:
                for v in decode_record(self.cfg, rec.words):
                    self.record_values[param_key(v.parameter)] = v
            except ValueError as e:
                self.decodeError.emit(f"строка {rec.line_no}: {e}")
        self._apply_values()

    def _apply_values(self) -> None:
        for k, w in self.cards.items():
            w.set_value(self.record_values.get(k))

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme; self.canvas.theme = theme
        self.hint.setStyleSheet(f"color:{theme.muted};")
        self.upd.setStyleSheet(f"color:{theme.accent};font-weight:700;")
        for w in self.cards.values():
            w.theme = theme; w.refresh_style()
        self.canvas.update()

    # --- скрытые, сброс
    def _update_hidden_btn(self) -> None:
        n = sum(1 for c in (self.layout_model.cards if self.layout_model else []) if not c.visible)
        self.hidden_btn.setText(f"Скрытые: {n}")

    def _show_hidden_menu(self) -> None:
        if not self.layout_model:
            return
        m = QMenu(self)
        names = {param_key(p): p.name for p in self.cfg.parameters}
        for cl in self.layout_model.cards:
            if not cl.visible:
                m.addAction(cl.title or names[cl.key], lambda cl=cl: self._unhide(cl))
        if m.isEmpty():
            m.addAction("Нет скрытых карточек").setEnabled(False)
        m.exec(self.hidden_btn.mapToGlobal(QPoint(0, self.hidden_btn.height())))

    def _unhide(self, cl: CardLayout) -> None:
        cl.visible = True
        self.cards[cl.key].show(); self.canvas.update_extent(); self._schedule_save()

    def reset_layout(self) -> None:
        if not self.cfg:
            return
        if QMessageBox.question(self, "Сброс", "Вернуть карточки к расположению по умолчанию? "
                                "Цвета и названия будут потеряны.") != QMessageBox.StandardButton.Yes:
            return
        self.layout_model.reset(self.cfg); self.rebuild(); self._schedule_save()

    # --- сохранение
    def _schedule_save(self) -> None:
        self._update_hidden_btn(); self._save_timer.start()

    def save_now(self) -> None:
        self._save_timer.stop()
        if self.layout_model is not None:
            self.ws.save_layout(self.layout_model)

    def export_layout(self) -> None:
        if not self.layout_model:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить раскладку",
                                              f"layout_{self.layout_model.array_id}.json", "JSON (*.json)")
        if path:
            self.layout_model.save(path)

    def import_layout(self) -> None:
        if not self.cfg:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить раскладку", "", "JSON (*.json)")
        if not path:
            return
        try:
            lay = DashboardLayout.load(path)
        except (ValueError, KeyError, TypeError, OSError) as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить раскладку:\n{e}"); return
        if lay.array_id != self.cfg.array_id and QMessageBox.question(
                self, "Другой массив",
                f"Раскладка создана для массива {lay.array_id}, выбран {self.cfg.array_id}. "
                "Применить по совпадению параметров?") != QMessageBox.StandardButton.Yes:
            return
        lay.array_id = self.cfg.array_id
        lay.ensure_cards(self.cfg)
        self.layout_model = lay; self.rebuild(); self._schedule_save()

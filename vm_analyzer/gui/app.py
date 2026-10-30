"""Главное окно: «Обмены» и «Параметры» (стыкуемые панели) + плеер сеанса внизу."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog, QMainWindow, QMessageBox,
                               QToolBar, QWidget)

from ..docx_import import read_tables
from ..exchange_import import read_exchange
from ..player.session import Player, Session, format_elapsed, format_speed
from ..storage.workspace import Workspace
from ..table_parser.parser import parse_table
from .exchange_view import ExchangeView
from .params_view import ParamsView
from .player_bar import PlayerBar
from .theme import DARK, LIGHT, stylesheet

FRAME_MS = 33          # ~30 кадров/с для обновления экрана; часы плеера считаются по реальному времени


class MainWindow(QMainWindow):
    def __init__(self, ws: Workspace):
        super().__init__()
        self.ws = ws
        self.settings = QSettings("VMExchangeAnalyzer", "VMExchangeAnalyzer")
        self.theme = LIGHT if self.settings.value("theme", "dark") == "light" else DARK
        self.setWindowTitle("VM Exchange Analyzer")
        self.resize(1600, 900)

        self.session: Session | None = None
        self.player = Player()
        self.cur_idx = -1
        self._last_tick = 0.0

        self.exchange = ExchangeView()
        self.params = ParamsView(ws, self.theme)
        self.bar = PlayerBar()
        self.dock_ex = self._dock("Обмены", self.exchange, "dock_ex")
        self.dock_pa = self._dock("Параметры", self.params, "dock_pa")
        self.dock_pl = QDockWidget("Плеер", self); self.dock_pl.setObjectName("dock_pl")
        self.dock_pl.setWidget(self.bar); self.dock_pl.setTitleBarWidget(QWidget())   # без заголовка
        self.dock_pl.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)

        central = QWidget(); central.setMaximumSize(0, 0)      # всё место отдаём докам
        self.setCentralWidget(central)
        self.setDockNestingEnabled(True)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_ex)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_pa)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_pl)
        self.resizeDocks([self.dock_ex, self.dock_pa], [520, 1080], Qt.Orientation.Horizontal)

        tb = QToolBar("Главная"); tb.setMovable(False); self.addToolBar(tb)
        for text, fn in (("Импорт DOCX…", self.import_docx), ("Открыть обмен…", self.open_exchange)):
            a = QAction(text, self); a.triggered.connect(fn); tb.addAction(a)
        tb.addSeparator()
        a_theme = QAction("Тема: светлая/тёмная", self); a_theme.triggered.connect(self.toggle_theme)
        tb.addAction(a_theme)
        view = self.menuBar().addMenu("Вид")
        view.addAction(self.dock_ex.toggleViewAction()); view.addAction(self.dock_pa.toggleViewAction())
        self._add_shortcuts()

        self.timer = QTimer(self); self.timer.setInterval(FRAME_MS)
        self.timer.timeout.connect(self._on_tick)

        self.exchange.rowChosen.connect(self.go_to_index)
        self.params.decodeError.connect(self.statusBar().showMessage)
        b = self.bar
        b.playToggled.connect(self.toggle_play)
        b.seekRequested.connect(self.seek_ms)
        b.stepped.connect(lambda d: self.go_to_index(self.cur_idx + d))
        b.toBegin.connect(lambda: self.go_to_index(0))
        b.toEnd.connect(lambda: self.go_to_index(len(self.session) - 1 if self.session else -1))
        b.speedUp.connect(lambda: self._change_speed(1))
        b.speedDown.connect(lambda: self._change_speed(-1))
        b.loopChanged.connect(lambda on: setattr(self.player, "loop", on))
        b.set_speed_text(format_speed(self.player.speed))

        self.apply_theme()
        self.reload_configs()
        geo, st = self.settings.value("geometry"), self.settings.value("state")
        if geo: self.restoreGeometry(geo)
        if st: self.restoreState(st)

    # --- общее
    def _dock(self, title: str, widget: QWidget, name: str) -> QDockWidget:
        d = QDockWidget(title, self); d.setObjectName(name); d.setWidget(widget)
        d.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                      QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        return d

    def _add_shortcuts(self) -> None:
        def sc(keys, fn):
            a = QAction(self); a.setShortcut(QKeySequence(keys)); a.triggered.connect(fn)
            self.addAction(a)
        sc("Space", self.toggle_play)
        sc("Left", lambda: self.go_to_index(self.cur_idx - 1))
        sc("Right", lambda: self.go_to_index(self.cur_idx + 1))
        sc("Home", lambda: self.go_to_index(0))
        sc("End", lambda: self.go_to_index(len(self.session) - 1 if self.session else -1))
        sc("[", lambda: self._change_speed(-1))
        sc("]", lambda: self._change_speed(1))

    def apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(stylesheet(self.theme))
        self.params.set_theme(self.theme)

    def toggle_theme(self) -> None:
        self.theme = LIGHT if self.theme is DARK else DARK
        self.settings.setValue("theme", self.theme.name)
        self.apply_theme()

    # --- конфигурации
    def reload_configs(self) -> None:
        configs, problems = self.ws.load_configs()
        self.params.set_configs(configs)
        self.exchange.set_known_ids(set(configs))
        if problems:
            QMessageBox.warning(self, "Конфигурации", "Не удалось прочитать:\n" + "\n".join(problems))
        self.statusBar().showMessage(f"Рабочая папка: {self.ws.root} · массивов: {len(configs)}")

    def import_docx(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Документ с таблицами массивов", "", "Word (*.docx)")
        if not path:
            return
        try:
            tables = read_tables(path)
        except Exception as e:                       # повреждённый/не-DOCX файл
            QMessageBox.critical(self, "Импорт DOCX", f"Не удалось прочитать файл:\n{e}"); return
        lines, ok, bad = [], 0, 0
        for t in tables:
            cfg, issues = parse_table(t, path)
            lines += [str(i) for i in issues]
            if cfg is None:
                bad += 1; lines.append(f"→ таблица #{t.index} отклонена")
            else:
                self.ws.save_config(cfg); ok += 1
                lines.append(f"→ массив {cfg.array_id} «{cfg.array_name}» сохранён "
                             f"(слов: {cfg.word_count}, параметров: {len(cfg.parameters)})")
        self.reload_configs()
        box = QMessageBox(QMessageBox.Icon.Warning if bad else QMessageBox.Icon.Information,
                          "Импорт DOCX", f"Загружено: {ok}, отклонено: {bad}", parent=self)
        if lines:
            box.setDetailedText("\n".join(lines))
        box.exec()

    # --- обмен и воспроизведение
    def open_exchange(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Файл обмена", "", "Текст (*.txt);;Все файлы (*)")
        if path:
            self.load_exchange(path)

    def load_exchange(self, path: str) -> None:
        try:
            records, issues = read_exchange(path)
        except (OSError, UnicodeDecodeError) as e:
            QMessageBox.critical(self, "Файл обмена", f"Не удалось прочитать файл:\n{e}"); return
        self._stop()
        self.session = Session(records)
        self.player.set_duration(self.session.duration_ms)
        self.exchange.set_records(records, f"{Path(path).name} · записей: {len(records)}"
                                  + (f" · ошибок формата: {len(issues)}" if issues else ""))
        self.params.set_session(self.session)
        self.bar.set_enabled(bool(records)); self.bar.set_duration(self.session.duration_ms)
        self.cur_idx = -1
        if records:
            self.go_to_index(0)
        if issues:
            box = QMessageBox(QMessageBox.Icon.Warning, "Файл обмена",
                              f"Пропущено строк с ошибками формата: {len(issues)}", parent=self)
            box.setDetailedText("\n".join(str(i) for i in issues[:500])); box.exec()

    def go_to_index(self, i: int) -> None:
        """Перейти к записи i (шаг, клик по строке, начало/конец)."""
        if not self.session or not len(self.session):
            return
        i = min(max(i, 0), len(self.session) - 1)
        self.player.seek(self.session.t_ms[i])
        self._set_position(i)

    def seek_ms(self, ms: int) -> None:
        if not self.session or not len(self.session):
            return
        self.player.seek(ms)
        self._set_position(max(0, self.session.index_at(self.player.t)))

    def _set_position(self, idx: int) -> None:
        if idx != self.cur_idx:
            self.cur_idx = idx
            self.exchange.select_row(idx)
            self.params.set_position(idx)
            rec = self.session.records[idx]
            self.statusBar().showMessage(f"Запись {rec.line_no} из файла · массив {rec.array_id}")
        self._update_bar()

    def _update_bar(self) -> None:
        s, p = self.session, self.player
        self.bar.set_time(p.t, s.clock_text(p.t),
                          f"{format_elapsed(p.t)} / {format_elapsed(p.duration_ms)}")

    def toggle_play(self) -> None:
        if not self.session or not len(self.session):
            return
        self.player.toggle()
        if self.player.playing:
            self._last_tick = time.perf_counter(); self.timer.start()
        else:
            self.timer.stop()
        self.bar.set_playing(self.player.playing)

    def _stop(self) -> None:
        self.player.playing = False; self.timer.stop(); self.bar.set_playing(False)

    def _change_speed(self, d: int) -> None:
        (self.player.faster if d > 0 else self.player.slower)()
        self.bar.set_speed_text(format_speed(self.player.speed))

    def _on_tick(self) -> None:
        now = time.perf_counter()
        dt = min((now - self._last_tick) * 1000.0, 500.0)   # защита от «скачка» после зависания окна
        self._last_tick = now
        if self.player.tick(dt):
            self._set_position(max(0, self.session.index_at(self.player.t)))
        if not self.player.playing:
            self.timer.stop(); self.bar.set_playing(False)

    def closeEvent(self, e):
        self.params.save_now()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("state", self.saveState())
        super().closeEvent(e)


def main(argv=None) -> int:
    import argparse
    from ..cli import _block_network
    ap = argparse.ArgumentParser(prog="vm_analyzer.gui")
    ap.add_argument("--workspace", default="workspace", help="рабочая папка (конфигурации и раскладки)")
    args = ap.parse_args(argv)
    _block_network()
    app = QApplication(sys.argv[:1])
    win = MainWindow(Workspace(args.workspace)); win.show()
    return app.exec()

"""Окно «Обмены»: построчная копия файла обмена. Воспроизведением управляет плеер."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLabel, QTableView, QVBoxLayout, QWidget)

from ..exchange_import import Record

HEADERS = ["№", "Время", "Массив", "Слова данных"]


class RecordsModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.records: list[Record] = []
        self.known_ids: set[int] = set()

    def set_records(self, records: list[Record]) -> None:
        self.beginResetModel(); self.records = records; self.endResetModel()

    def set_known_ids(self, ids: set[int]) -> None:
        self.known_ids = ids
        if self.records:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.records) - 1, 3))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):
        return len(HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = self.records[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (r.line_no, r.time_text, r.array_id, r.words_text)[index.column()]
        if role == Qt.ItemDataRole.ForegroundRole and r.array_id not in self.known_ids:
            return QBrush(QColor("#e5a03a"))     # нет конфигурации для массива
        if role == Qt.ItemDataRole.ToolTipRole and r.array_id not in self.known_ids:
            return f"Нет конфигурации для массива {r.array_id}"
        return None


class ExchangeView(QWidget):
    rowChosen = Signal(int)      # пользователь выбрал строку (клик/стрелки)

    def __init__(self):
        super().__init__()
        self._silent = False
        self.model = RecordsModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setShowGrid(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for c in (0, 1, 2):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.selectionModel().currentRowChanged.connect(self._on_row)

        self.info = QLabel("Файл не загружен")
        self.info.setStyleSheet("color:#93a4b5;")
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)
        lay.addWidget(self.info); lay.addWidget(self.table)

    def set_records(self, records: list[Record], info: str) -> None:
        self.model.set_records(records)
        self.info.setText(info)

    def set_known_ids(self, ids: set[int]) -> None:
        self.model.set_known_ids(ids)

    def select_row(self, row: int) -> None:
        """Подсветить строку программно (сигнал rowChosen не посылается)."""
        if not 0 <= row < self.model.rowCount():
            return
        self._silent = True
        try:
            self.table.selectRow(row)
            self.table.scrollTo(self.model.index(row, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        finally:
            self._silent = False

    def _on_row(self, current: QModelIndex, _prev) -> None:
        if not self._silent and current.isValid():
            self.rowChosen.emit(current.row())

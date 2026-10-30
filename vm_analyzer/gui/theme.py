"""Темы оформления в стиле промышленной SCADA-мнемосхемы (тёмная — основная) и общий stylesheet."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str          # фон рабочего поля
    panel: str       # панели, доки, тулбары
    card: str        # тело карточки
    header: str      # шапка карточки / заголовки доков
    border: str
    text: str
    muted: str
    accent: str      # синий акцент (как стрелки на схеме)
    grid: str
    row_alt: str
    sel: str         # выделенная строка
    led_off: str     # погашенный индикатор


DARK = Theme("dark", bg="#171c22", panel="#1f2730", card="#212932", header="#2b3540", border="#3a4756",
             text="#e4ebf2", muted="#93a4b5", accent="#2a9fd6", grid="#232c35", row_alt="#1c232b",
             sel="#1f5878", led_off="#39444f")
LIGHT = Theme("light", bg="#e8ecf1", panel="#f6f8fa", card="#ffffff", header="#dbe3ea", border="#bfc9d4",
              text="#1b2530", muted="#5d6e7f", accent="#1b82b9", grid="#d5dce4", row_alt="#f0f3f7",
              sel="#bde0f3", led_off="#c3ccd6")

MONO = '"Consolas", "Cascadia Mono", "Courier New", monospace'


def stylesheet(t: Theme) -> str:
    return f"""
    * {{ font-family: "Segoe UI", "Roboto", "Inter", sans-serif; font-size: 13px; }}
    QMainWindow, QDialog {{ background: {t.bg}; color: {t.text}; }}
    QWidget {{ color: {t.text}; }}
    QMainWindow::separator {{ background: {t.border}; width: 2px; height: 2px; }}
    QDockWidget {{ font-weight: 700; }}
    QDockWidget::title {{ background: {t.header}; padding: 7px 12px; border-bottom: 1px solid {t.border};
                         text-align: left; }}
    QToolBar {{ background: {t.panel}; border: none; border-bottom: 1px solid {t.border}; padding: 5px; spacing: 6px; }}
    QToolBar QToolButton {{ background: {t.header}; border: 1px solid {t.border}; border-radius: 3px; padding: 6px 12px; }}
    QToolBar QToolButton:hover {{ border-color: {t.accent}; }}
    QStatusBar {{ background: {t.panel}; color: {t.muted}; border-top: 1px solid {t.border}; }}
    QMenuBar {{ background: {t.panel}; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {t.accent}; color: white; }}
    QMenu {{ background: {t.panel}; border: 1px solid {t.border}; padding: 4px; }}
    QMenu::item {{ padding: 6px 18px; }}
    QPushButton, QToolButton {{ background: {t.header}; border: 1px solid {t.border}; border-radius: 3px; padding: 5px 12px; }}
    QPushButton:hover, QToolButton:hover {{ border-color: {t.accent}; }}
    QPushButton:pressed {{ background: {t.accent}; color: white; }}
    QPushButton:checked {{ background: {t.accent}; color: white; border-color: {t.accent}; }}
    QPushButton:disabled {{ color: {t.muted}; }}
    QComboBox, QLineEdit, QDoubleSpinBox {{ background: {t.card}; border: 1px solid {t.border}; border-radius: 3px;
                                           padding: 4px 8px; min-height: 20px; }}
    QComboBox:hover, QLineEdit:focus {{ border-color: {t.accent}; }}
    QComboBox QAbstractItemView {{ background: {t.panel}; selection-background-color: {t.sel}; }}
    QTableView {{ background: {t.panel}; alternate-background-color: {t.row_alt}; border: none; gridline-color: transparent;
                 selection-background-color: {t.sel}; selection-color: {t.text}; font-family: {MONO}; }}
    QTableView QTableCornerButton::section {{ background: {t.header}; }}
    QHeaderView::section {{ background: {t.header}; color: {t.muted}; border: none; border-bottom: 1px solid {t.border};
                           border-right: 1px solid {t.border}; padding: 6px 8px; font-weight: 700; font-family: "Segoe UI"; }}
    QScrollArea {{ border: none; background: {t.bg}; }}
    QScrollBar:vertical {{ background: {t.bg}; width: 12px; }}
    QScrollBar:horizontal {{ background: {t.bg}; height: 12px; }}
    QScrollBar::handle {{ background: {t.border}; border-radius: 3px; min-height: 30px; min-width: 30px; margin: 2px; }}
    QScrollBar::handle:hover {{ background: {t.accent}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QCheckBox {{ spacing: 6px; }}
    QToolTip {{ background: {t.panel}; color: {t.text}; border: 1px solid {t.border}; padding: 4px; }}

    #playerBar {{ background: {t.panel}; border-top: 1px solid {t.border}; }}
    #playerBar QPushButton {{ min-width: 34px; padding: 6px 10px; font-weight: 700; }}
    #clockLabel {{ font-family: {MONO}; font-size: 22px; font-weight: 700; color: {t.text}; }}
    #elapsedLabel {{ font-family: {MONO}; color: {t.muted}; }}
    #speedLabel {{ font-weight: 700; color: {t.accent}; min-width: 56px; qproperty-alignment: AlignCenter; }}
    QSlider::groove:horizontal {{ height: 4px; background: {t.border}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {t.text}; border: 2px solid {t.accent}; width: 10px; height: 10px;
                                 margin: -6px 0; border-radius: 7px; }}
    """

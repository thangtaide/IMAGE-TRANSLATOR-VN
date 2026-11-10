"""Application-level palette, including Windows popup/menu surfaces."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


DARK_QSS = '''
QWidget { color: #e5e7eb; }
QMainWindow, QDialog, QScrollArea, QScrollArea > QWidget > QWidget { background: #111827; }
QGroupBox { border: 1px solid #374151; border-radius: 8px; margin-top: 14px; padding: 12px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; color: #cbd5e1; }
QLabel#title { font-size: 20px; font-weight: 700; color: #60a5fa; }
QLabel#muted { color: #b8c4d4; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
 background: #1f2937; color: #f1f5f9; border: 1px solid #475569; border-radius: 5px; padding: 7px; }
QPushButton, QToolButton { background: #273449; color: #f1f5f9; border: 1px solid #475569; border-radius: 5px; padding: 9px 12px; }
QPushButton:hover, QToolButton:hover { background: #334155; border-color: #94a3b8; }
QPushButton:focus, QToolButton:focus, QComboBox:focus { border: 2px solid #60a5fa; }
QPushButton#primary { background: #2563eb; color: white; font-weight: 600; }
QPushButton#restart { background: #155e75; color: white; border-color: #22d3ee; font-weight: 600; }
QPushButton:disabled, QToolButton:disabled { color: #a1adbf; background: #1b2535; border-color: #334155; }
QMenuBar { background: #111827; color: #e5e7eb; }
QMenuBar::item:selected { background: #334155; }
QMenu { background-color: #1f2937; color: #f1f5f9; border: 1px solid #64748b; padding: 5px; }
QMenu::item { padding: 9px 24px; background: transparent; color: #f1f5f9; }
QMenu::item:selected { background-color: #2563eb; color: white; }
QMenu::item:disabled { color: #a1adbf; background: #1f2937; }
QMenu::separator { height: 1px; background: #475569; margin: 5px; }
QComboBox QAbstractItemView { background-color: #1f2937; color: #f1f5f9; border: 1px solid #64748b;
 selection-background-color: #2563eb; selection-color: white; outline: 0; }
QComboBox QAbstractItemView::item { min-height: 28px; padding: 5px; color: #f1f5f9; }
QComboBox QAbstractItemView::item:disabled { color: #a1adbf; }
QTabWidget::pane { border: 1px solid #374151; border-radius: 7px; padding: 8px; }
QTabBar::tab { background: #1f2937; padding: 9px 16px; margin-right: 4px; }
QTabBar::tab:selected { background: #2563eb; color: white; }
QTableWidget { background: #172033; alternate-background-color: #1f2937; gridline-color: #374151;
 selection-background-color: #1d4ed8; selection-color: white; }
QHeaderView::section, QTableCornerButton::section { background: #273449; color: #e5e7eb; padding: 8px; border: 0; }
QScrollBar:vertical { background: #111827; width: 12px; }
QScrollBar::handle:vertical { background: #475569; min-height: 24px; border-radius: 4px; }
QProgressBar { background: #1f2937; border: 1px solid #374151; text-align: center; min-height: 24px; border-radius: 4px; }
QProgressBar::chunk { background: #2563eb; }
QToolTip { background: #1f2937; color: #f1f5f9; border: 1px solid #64748b; padding: 5px; }
'''


def apply_dark_theme(app=None):
    app = app or QApplication.instance()
    if app is None:
        return
    if app.property('translatorDarkTheme'):
        return
    # Fusion honors palette/QSS for popups instead of the Windows light menu surface.
    app.setStyle('Fusion')
    palette = QPalette()
    for role, color in [(QPalette.Window,'#111827'),(QPalette.WindowText,'#e5e7eb'),
            (QPalette.Base,'#1f2937'),(QPalette.AlternateBase,'#273449'),(QPalette.Text,'#f1f5f9'),
            (QPalette.Button,'#273449'),(QPalette.ButtonText,'#f1f5f9'),(QPalette.Highlight,'#2563eb'),
            (QPalette.HighlightedText,'#ffffff'),(QPalette.ToolTipBase,'#1f2937'),(QPalette.ToolTipText,'#f1f5f9')]:
        palette.setColor(role,QColor(color))
    for role in (QPalette.Text,QPalette.WindowText,QPalette.ButtonText):
        palette.setColor(QPalette.Disabled,role,QColor('#a1adbf'))
    app.setPalette(palette); app.setStyleSheet(DARK_QSS)
    app.setProperty('translatorDarkTheme',True)

"""
Chess Karma – global UI theme.

Colour palette and application-wide Qt stylesheet inspired by the
dark forest-green aesthetic of Chess.com.
"""

# ── Palette ────────────────────────────────────────────────────────────────────

BG           = "#354530"   # main window / dialog background — medium olive green
BG_PANEL     = "#3a4a34"   # panels / lighter dialog surfaces
BG_CARD      = "#455238"   # cards, group boxes, section backgrounds
BG_INPUT     = "#2e3a26"   # text inputs, table cell background
BORDER       = "#5a7048"   # subtle borders
BORDER_FOCUS = "#81b64c"   # active / focused border
TEXT         = "#dde8cc"   # primary text — off-white green
TEXT_DIM     = "#8fa882"   # secondary / hint text
TEXT_HEADER  = "#ffffff"   # bright headings
ACCENT       = "#81b64c"   # Chess.com brand green (accent)
TEAL         = "#7dd6e8"   # chart lines / teal highlights
GOLD         = "#f5c542"   # medals / golden highlights
RED          = "#e05252"   # errors / failed indicators
RED_DARK     = "#9e2020"   # destructive action buttons
ORANGE       = "#e07b22"   # warning / hint indicators
GREEN_BTN    = "#4a7c2f"   # primary action buttons
GREEN_HOVER  = "#5a9438"   # button hover state


def get_global_qss() -> str:
    """Return the application-wide Qt Style Sheet."""
    return """

/* ── Base ────────────────────────────────────────────────────────── */
QWidget {
    background-color: #354530;
    color: #dde8cc;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 12px;
}

QMainWindow {
    background-color: #354530;
}

/* ── Dialogs ─────────────────────────────────────────────────────── */
QDialog {
    background-color: #354530;
}

QMessageBox {
    background-color: #354530;
}

QMessageBox QLabel {
    color: #dde8cc;
    background-color: transparent;
}

QInputDialog {
    background-color: #354530;
}

/* ── Menu bar ────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #2e3a26;
    color: #dde8cc;
    border-bottom: 1px solid #5a7048;
    padding: 2px;
    spacing: 4px;
}

QMenuBar::item:selected {
    background-color: #455238;
    border-radius: 4px;
}

QMenu {
    background-color: #3a4a34;
    border: 1px solid #5a7048;
    color: #dde8cc;
    padding: 4px 2px;
}

QMenu::item {
    padding: 4px 20px;
    border-radius: 3px;
}

QMenu::item:selected {
    background-color: #4a7c2f;
    color: white;
}

QMenu::separator {
    height: 1px;
    background-color: #5a7048;
    margin: 4px 8px;
}

/* ── Status bar ──────────────────────────────────────────────────── */
QStatusBar {
    background-color: #2e3a26;
    color: #8fa882;
    border-top: 1px solid #5a7048;
}

/* ── Labels ──────────────────────────────────────────────────────── */
QLabel {
    color: #dde8cc;
    background-color: transparent;
}

/* ── Group boxes ─────────────────────────────────────────────────── */
QGroupBox {
    background-color: #455238;
    border: 1px solid #5a7048;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 6px;
    color: #dde8cc;
    font-weight: bold;
    font-size: 11px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #81b64c;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {
    background-color: #455238;
    color: #dde8cc;
    border: 1px solid #5a7048;
    border-radius: 5px;
    padding: 6px 12px;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #4e5f40;
    border-color: #81b64c;
}

QPushButton:pressed {
    background-color: #3a4a34;
}

QPushButton:disabled {
    background-color: #354530;
    color: #6a8058;
    border-color: #455238;
}

/* ── Text inputs ─────────────────────────────────────────────────── */
QLineEdit,
QTextEdit,
QPlainTextEdit {
    background-color: #2e3a26;
    color: #dde8cc;
    border: 1px solid #5a7048;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #81b64c;
    selection-color: #000000;
}

QLineEdit:focus,
QTextEdit:focus {
    border-color: #81b64c;
}

/* ── Combo box ───────────────────────────────────────────────────── */
QComboBox {
    background-color: #2e3a26;
    color: #dde8cc;
    border: 1px solid #5a7048;
    border-radius: 4px;
    padding: 4px 8px;
}

QComboBox:hover {
    border-color: #81b64c;
}

QComboBox QAbstractItemView {
    background-color: #3a4a34;
    color: #dde8cc;
    selection-background-color: #4a7c2f;
    border: 1px solid #5a7048;
}

/* ── Tables ──────────────────────────────────────────────────────── */
QTableWidget,
QTableView {
    background-color: #2e3a26;
    alternate-background-color: #333f28;
    color: #dde8cc;
    gridline-color: #455238;
    border: 1px solid #5a7048;
    selection-background-color: #4a6535;
    selection-color: white;
}

QTableWidget::item,
QTableView::item {
    padding: 3px 6px;
    border: none;
}

QHeaderView {
    background-color: #2e3a26;
    border: none;
}

QHeaderView::section {
    background-color: #3a4a34;
    color: #81b64c;
    border: none;
    border-right: 1px solid #5a7048;
    border-bottom: 1px solid #5a7048;
    padding: 4px 8px;
    font-weight: bold;
    font-size: 11px;
}

QHeaderView::section:last {
    border-right: none;
}

/* ── Progress bar ────────────────────────────────────────────────── */
QProgressBar {
    background-color: #2e3a26;
    border: 1px solid #5a7048;
    border-radius: 4px;
    text-align: center;
    color: #dde8cc;
    height: 12px;
}

QProgressBar::chunk {
    background-color: #81b64c;
    border-radius: 3px;
}

/* ── Check box ───────────────────────────────────────────────────── */
QCheckBox {
    color: #dde8cc;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    background-color: #2e3a26;
    border: 1px solid #5a7048;
    border-radius: 3px;
}

QCheckBox::indicator:checked {
    background-color: #81b64c;
    border-color: #81b64c;
}

QCheckBox::indicator:hover {
    border-color: #81b64c;
}


/* ── Scroll bars ─────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #2e3a26;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #5a7048;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #81b64c;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #2e3a26;
    height: 8px;
    margin: 0;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #5a7048;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #81b64c;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Splitter ────────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #5a7048;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* ── Tooltip ─────────────────────────────────────────────────────── */
QToolTip {
    background-color: #3a4a34;
    color: #dde8cc;
    border: 1px solid #5a7048;
    padding: 4px 6px;
    font-size: 11px;
}

/* ── Dialog button box ───────────────────────────────────────────── */
QDialogButtonBox QPushButton {
    min-width: 80px;
}

/* ── Frame lines (HLine / VLine separators) ──────────────────────── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #5a7048;
}

"""

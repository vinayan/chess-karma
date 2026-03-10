"""
Chess Karma – main entry point.

Run with:
    python main.py
or (after installing as a package):
    chess-karma
"""

import pathlib
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from chess_karma.ui.main_window import MainWindow
from chess_karma.ui.theme import get_global_qss

_ICON_PATH = pathlib.Path(__file__).parent / "chess_karma" / "assets" / "icon.ico"


def main() -> None:
    # High-DPI support (PyQt6 enables this by default, but be explicit)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Chess Karma")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("Chess Karma")

    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    # Apply Chess.com-style dark forest-green theme
    app.setStyle("Fusion")
    app.setStyleSheet(get_global_qss())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

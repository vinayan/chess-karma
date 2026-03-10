"""
RushPanel – side panel shown during a Puzzle Rush session.

Displays
────────
  • Mode title
  • Large countdown / stopwatch timer
  • Lives (hearts)
  • Solved counter
  • Current puzzle status
  • Abort button
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import pyqtSignal

from chess_karma.core.rush_manager import MAX_FAILURES, RushMode


_MODE_LABELS = {
    RushMode.THREE_MIN: "⚡  3-Minute Rush",
    RushMode.FIVE_MIN:  "⚡  5-Minute Rush",
    RushMode.SURVIVAL:  "♾  Survival Rush",
}

_TIMER_COLOUR_NORMAL  = "color: #dde8cc;"
_TIMER_COLOUR_WARNING = "color: #e07b22;"   # < 30 s remaining
_TIMER_COLOUR_DANGER  = "color: #e05252;"   # < 10 s remaining

_HEART_FILLED = "♥"
_HEART_EMPTY  = "♡"


class _Separator(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)


class RushPanel(QWidget):
    """
    Compact sidebar panel displayed while a Puzzle Rush session is active.

    Signals
    ───────
    abort_requested()   – user clicked the Abort button
    """

    abort_requested = pyqtSignal()

    def __init__(self, mode: RushMode, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._is_survival = (mode == RushMode.SURVIVAL)
        self.setMinimumWidth(240)
        self.setMaximumWidth(300)
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Dark forest-green background to differentiate from train mode
        self.setStyleSheet("background-color: #3a4a34; border-radius: 6px;")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Mode title
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)

        self._lbl_mode = QLabel(_MODE_LABELS.get(self._mode, "Puzzle Rush"))
        self._lbl_mode.setFont(title_font)
        self._lbl_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_mode.setStyleSheet("color: #dde8cc;")
        root.addWidget(self._lbl_mode)

        root.addWidget(_Separator())

        # Timer
        timer_font = QFont("Monospace")
        timer_font.setPointSize(40)
        timer_font.setBold(True)

        self._lbl_timer = QLabel("0:00")
        self._lbl_timer.setFont(timer_font)
        self._lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_timer.setStyleSheet(_TIMER_COLOUR_NORMAL)
        root.addWidget(self._lbl_timer)

        timer_hint = QLabel("countdown" if not self._is_survival else "elapsed")
        timer_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_hint.setStyleSheet("color: #8fa882; font-size: 10px;")
        root.addWidget(timer_hint)

        root.addWidget(_Separator())

        # Lives
        lives_title = QLabel("Lives")
        lives_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lives_title.setStyleSheet("color: #8fa882; font-size: 10px; font-weight: bold;")
        root.addWidget(lives_title)

        hearts_font = QFont()
        hearts_font.setPointSize(24)

        self._lbl_lives = QLabel(_HEART_FILLED * MAX_FAILURES)
        self._lbl_lives.setFont(hearts_font)
        self._lbl_lives.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_lives.setStyleSheet("color: #e05252; letter-spacing: 8px;")
        root.addWidget(self._lbl_lives)

        root.addWidget(_Separator())

        # Score
        score_title = QLabel("Puzzles Solved")
        score_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_title.setStyleSheet("color: #8fa882; font-size: 10px; font-weight: bold;")
        root.addWidget(score_title)

        score_font = QFont()
        score_font.setPointSize(32)
        score_font.setBold(True)

        self._lbl_score = QLabel("0")
        self._lbl_score.setFont(score_font)
        self._lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_score.setStyleSheet("color: #81b64c;")
        root.addWidget(self._lbl_score)

        root.addWidget(_Separator())

        # Status
        self._lbl_status = QLabel("Solve the puzzle!")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_status.setStyleSheet(
            "color: #dde8cc; font-size: 13px; font-weight: bold;"
        )
        root.addWidget(self._lbl_status)

        root.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # Abort button
        self._btn_abort = QPushButton("✕  Abort Rush")
        self._btn_abort.setStyleSheet(
            """
            QPushButton {
                background-color: #9e2020;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 7px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c62828;
            }
            """
        )
        self._btn_abort.clicked.connect(self.abort_requested)
        root.addWidget(self._btn_abort)

    # ── Public update API ──────────────────────────────────────────────────────

    def update_timer(self, formatted: str, remaining_s: float | None = None) -> None:
        """Update the timer label and change colour when time is running low."""
        self._lbl_timer.setText(formatted)

        if remaining_s is None:
            # Survival stopwatch – stay neutral
            self._lbl_timer.setStyleSheet(_TIMER_COLOUR_NORMAL)
        elif remaining_s <= 10:
            self._lbl_timer.setStyleSheet(_TIMER_COLOUR_DANGER)
        elif remaining_s <= 30:
            self._lbl_timer.setStyleSheet(_TIMER_COLOUR_WARNING)
        else:
            self._lbl_timer.setStyleSheet(_TIMER_COLOUR_NORMAL)

    def update_lives(self, lives_left: int) -> None:
        """Redraw the hearts to reflect remaining lives."""
        hearts = "".join(
            _HEART_FILLED if i < lives_left else _HEART_EMPTY
            for i in range(MAX_FAILURES)
        )
        self._lbl_lives.setText(hearts)

    def update_score(self, score: int) -> None:
        self._lbl_score.setText(str(score))

    def set_status(self, text: str, style: str = "") -> None:
        colours = {
            "success": "color: #81b64c; font-size: 13px; font-weight: bold;",
            "error":   "color: #e05252; font-size: 13px; font-weight: bold;",
            "info":    "color: #dde8cc; font-size: 13px; font-weight: bold;",
            "":        "color: #dde8cc; font-size: 13px; font-weight: bold;",
        }
        self._lbl_status.setStyleSheet(colours.get(style, colours[""]))
        self._lbl_status.setText(text)

    def set_abort_enabled(self, enabled: bool) -> None:
        self._btn_abort.setEnabled(enabled)

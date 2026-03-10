"""
RushStartDialog – mode selection dialog shown before a Puzzle Rush session.

Displays the three available modes with descriptions, shows the current
top-3 scores for each mode, and lets the user pick or cancel.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from chess_karma.core.leaderboard import Leaderboard, ScoreEntry
from chess_karma.core.rush_manager import MAX_FAILURES, RushMode


class RushStartDialog(QDialog):
    """
    Modal dialog for selecting a Puzzle Rush mode.

    After exec_() returns Accepted, read .selected_mode for the choice.
    """

    def __init__(
        self,
        leaderboard: Leaderboard,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Puzzle Rush")
        self.setMinimumWidth(560)
        self.setModal(True)

        self._leaderboard = leaderboard
        self.selected_mode: RushMode | None = None

        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # Header
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)

        header = QLabel("⚡  Puzzle Rush")
        header.setFont(title_font)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(header)

        sub = QLabel(
            f"Solve as many puzzles as you can before time runs out or "
            f"you make {MAX_FAILURES} mistakes."
        )
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #8fa882; font-size: 12px;")
        root.addWidget(sub)

        # Mode cards
        modes_layout = QHBoxLayout()
        modes_layout.setSpacing(10)

        modes = [
            (RushMode.THREE_MIN, "3 Minutes",  "⏱",
             "Race the clock for 3 minutes.\nHow many can you solve?",
             "#8a6000"),
            (RushMode.FIVE_MIN,  "5 Minutes",  "⏱",
             "A longer sprint \u2013 5 minutes\nof full concentration.",
             "#2a5f80"),
            (RushMode.SURVIVAL,  "Survival",   "♾",
             "No time limit. Survive as\nlong as possible.",
             "#4a7c2f"),
        ]

        for mode, label, icon, desc, colour in modes:
            card = self._make_mode_card(mode, label, icon, desc, colour)
            modes_layout.addWidget(card)

        root.addLayout(modes_layout)

        # Cancel button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _make_mode_card(
        self,
        mode: RushMode,
        label: str,
        icon: str,
        desc: str,
        colour: str,
    ) -> QGroupBox:
        box = QGroupBox()
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        # Icon + title
        icon_font = QFont()
        icon_font.setPointSize(22)
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(icon_font)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_lbl = QLabel(label)
        title_lbl.setFont(title_font)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet("color: #8fa882; font-size: 11px;")

        layout.addWidget(icon_lbl)
        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Leaderboard top-3
        lb_title = QLabel("Top Scores")
        lb_title_font = QFont()
        lb_title_font.setBold(True)
        lb_title_font.setPointSize(9)
        lb_title.setFont(lb_title_font)
        lb_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lb_title)

        entries = self._leaderboard.get_top(mode)
        medals = ["🥇", "🥈", "🥉"]
        if entries:
            for i, entry in enumerate(entries):
                medal = medals[i] if i < len(medals) else f"{i+1}."
                t = entry.display_time(mode)
                if mode == RushMode.SURVIVAL:
                    row_text = f"{medal}  {entry.score} solved  ·  {t}"
                else:
                    row_text = f"{medal}  {entry.score} solved  ·  {t}"
                row = QLabel(row_text)
                row.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row.setStyleSheet("font-size: 11px; color: #dde8cc;")
                layout.addWidget(row)
        else:
            empty = QLabel("No scores yet")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #8fa882; font-size: 11px; font-style: italic;")
            layout.addWidget(empty)

        # Start button
        btn = QPushButton(f"Start  {label}")
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {colour};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colour}cc;
            }}
            """
        )
        btn.clicked.connect(lambda _checked, m=mode: self._select(m))
        layout.addWidget(btn)

        return box

    def _select(self, mode: RushMode) -> None:
        self.selected_mode = mode
        self.accept()

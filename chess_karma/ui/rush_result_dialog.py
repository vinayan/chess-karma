"""
RushResultDialog – shown when a Puzzle Rush session ends.

Displays
────────
  • Session summary (score, time used, failures)
  • "New personal best!" banner if applicable
  • Updated top-3 leaderboard for that mode
  • Buttons: Play Again  /  Back to Training
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from chess_karma.core.leaderboard import Leaderboard
from chess_karma.core.rush_manager import MAX_FAILURES, RushManager, RushMode


_MODE_LABELS = {
    RushMode.THREE_MIN: "3-Minute Rush",
    RushMode.FIVE_MIN:  "5-Minute Rush",
    RushMode.SURVIVAL:  "Survival Rush",
}

_END_REASONS = {
    "failures": f"You used all {MAX_FAILURES} lives!",
    "timeout":  "Time's up!",
    "aborted":  "Rush aborted.",
}


class RushResultDialog(QDialog):
    """
    Modal result dialog displayed at the end of a Puzzle Rush session.

    After exec_() inspect .play_again (bool) to decide what to do next.
    """

    def __init__(
        self,
        rush: RushManager,
        leaderboard: Leaderboard,
        rank: int,                   # 1-3 = placed, 0 = didn't place
        end_reason: str,             # "failures" | "timeout" | "aborted"
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Puzzle Rush – Results")
        self.setMinimumWidth(420)
        self.setModal(True)

        self._rush = rush
        self._leaderboard = leaderboard
        self._rank = rank
        self._end_reason = end_reason
        self.play_again: bool = False

        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)

        mode = self._rush.mode

        # ── Header ──────────────────────────────────────────────────────────────
        title_font = QFont()
        title_font.setPointSize(17)
        title_font.setBold(True)
        title = QLabel(_MODE_LABELS.get(mode, "Puzzle Rush"))
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        reason_lbl = QLabel(_END_REASONS.get(self._end_reason, "Session ended."))
        reason_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reason_lbl.setStyleSheet("color: #8fa882; font-size: 12px;")
        root.addWidget(reason_lbl)

        root.addWidget(_hsep())

        # ── Score summary ────────────────────────────────────────────────────────
        score_font = QFont()
        score_font.setPointSize(48)
        score_font.setBold(True)
        score_lbl = QLabel(str(self._rush.score))
        score_lbl.setFont(score_font)
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_lbl.setStyleSheet("color: #81b64c;")
        root.addWidget(score_lbl)

        solved_hint = QLabel("puzzles solved")
        solved_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        solved_hint.setStyleSheet("color: #8fa882; font-size: 11px;")
        root.addWidget(solved_hint)

        # Details grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(4)

        elapsed_m, elapsed_s = divmod(int(self._rush.elapsed_s()), 60)
        elapsed_str = f"{elapsed_m}:{elapsed_s:02d}"

        detail_items = [
            ("Time used",   elapsed_str),
            ("Mistakes",    f"{self._rush.failures} / {MAX_FAILURES}"),
        ]
        for row, (k, v) in enumerate(detail_items):
            key_lbl = QLabel(k)
            key_lbl.setStyleSheet("color: #8fa882; font-size: 12px;")
            val_lbl = QLabel(v)
            val_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #dde8cc;")
            grid.addWidget(key_lbl, row, 0, Qt.AlignmentFlag.AlignRight)
            grid.addWidget(val_lbl, row, 1, Qt.AlignmentFlag.AlignLeft)

        root.addLayout(grid)

        # Personal best banner
        if self._rank in (1, 2, 3) and self._end_reason != "aborted":
            medals = {1: "🥇 New Best!", 2: "🥈 Top 3!", 3: "🥉 Top 3!"}
            pb_lbl = QLabel(medals[self._rank])
            pb_font = QFont()
            pb_font.setPointSize(14)
            pb_font.setBold(True)
            pb_lbl.setFont(pb_font)
            pb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pb_lbl.setStyleSheet("color: #f5c542;")
            root.addWidget(pb_lbl)

        root.addWidget(_hsep())

        # ── Leaderboard ──────────────────────────────────────────────────────────
        lb_title = QLabel("Top Scores")
        lb_font = QFont()
        lb_font.setBold(True)
        lb_title.setFont(lb_font)
        lb_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(lb_title)

        entries = self._leaderboard.get_top(mode)
        medals_list = ["🥇", "🥈", "🥉"]
        if entries:
            for i, entry in enumerate(entries):
                medal = medals_list[i] if i < len(medals_list) else f"{i+1}."
                t = entry.display_time(mode)
                row_txt = f"{medal}  {entry.score} solved  ·  {t}  ·  {entry.date}"
                row_lbl = QLabel(row_txt)
                row_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row_lbl.setStyleSheet("font-size: 12px; color: #dde8cc;")
                root.addWidget(row_lbl)
        else:
            none_lbl = QLabel("No scores yet")
            none_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            none_lbl.setStyleSheet("color: #8fa882; font-style: italic;")
            root.addWidget(none_lbl)

        root.addWidget(_hsep())

        # ── Buttons ──────────────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_again = _make_button("⚡  Play Again", "#8a6000")
        btn_train = _make_button("📖  Back to Training", "#2a5f80")

        btn_again.clicked.connect(self._on_play_again)
        btn_train.clicked.connect(self._on_back_to_train)

        btn_layout.addWidget(btn_again)
        btn_layout.addWidget(btn_train)
        root.addLayout(btn_layout)

    # ── Handlers ───────────────────────────────────────────────────────────────

    def _on_play_again(self) -> None:
        self.play_again = True
        self.accept()

    def _on_back_to_train(self) -> None:
        self.play_again = False
        self.accept()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _hsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFrameShadow(QFrame.Shadow.Sunken)
    return f


def _make_button(text: str, colour: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {colour};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 14px;
            font-size: 13px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {colour}cc;
        }}
        """
    )
    return btn

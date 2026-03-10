"""
PuzzlePanel – right-hand side panel containing puzzle metadata, status,
controls (hint / solution / reset) and navigation (prev / next).
"""

from __future__ import annotations

import chess
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class _Separator(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)


class PuzzlePanel(QWidget):
    """
    Sidebar panel that shows puzzle information and provides controls.

    Signals
    ───────
    hint_requested()
    solution_requested()
    reset_requested()
    next_requested()
    prev_requested()
    """

    hint_requested = pyqtSignal()
    solution_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    next_requested = pyqtSignal()
    prev_requested = pyqtSignal()
    auto_next_changed = pyqtSignal(bool)   # emitted when the toggle changes

    # ── Setup ──────────────────────────────────────────────────────────────────

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(240)
        self.setMaximumWidth(300)
        self._build_ui()
        self._set_no_puzzle()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        # ── Title ──────────────────────────────────────────────────────────────
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)

        self._app_title = QLabel("Chess Karma")
        self._app_title.setFont(title_font)
        self._app_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._app_title)

        root.addWidget(_Separator())

        # ── Puzzle index (always visible) ──────────────────────────────────────
        index_row = QHBoxLayout()
        bold = QFont()
        bold.setBold(True)
        self._lbl_index = QLabel("—")
        self._lbl_index.setFont(bold)
        index_row.addWidget(self._lbl_index)
        index_row.addStretch()

        # Toggle button to reveal/hide spoiler info
        self._btn_show_info = QPushButton("🔍  Show Info")
        self._btn_show_info.setCheckable(True)
        self._btn_show_info.setChecked(False)
        self._btn_show_info.setFixedHeight(22)
        self._btn_show_info.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 2px 6px;"
            " border: 1px solid #5a7048; border-radius: 3px; background: #455238; color: #dde8cc; }"
            "QPushButton:checked { background: #4a6535; border-color: #81b64c; }"
        )
        self._btn_show_info.toggled.connect(self._on_info_toggle)
        index_row.addWidget(self._btn_show_info)
        root.addLayout(index_row)

        # ── Puzzle info (hidden until revealed) ────────────────────────────────
        info_box = QGroupBox("Puzzle Info")
        info_layout = QVBoxLayout(info_box)
        info_layout.setSpacing(4)

        self._lbl_title = QLabel("—")
        self._lbl_title.setWordWrap(True)
        self._lbl_white = QLabel("White: —")
        self._lbl_black = QLabel("Black: —")
        self._lbl_side = QLabel("Side to move: —")
        bold2 = QFont()
        bold2.setBold(True)

        for w in (
            self._lbl_title,
            self._lbl_white,
            self._lbl_black,
            self._lbl_side,
        ):
            info_layout.addWidget(w)

        self._lbl_prev_result = QLabel("")
        self._lbl_prev_result.setWordWrap(True)
        info_layout.addWidget(self._lbl_prev_result)

        self._info_box = info_box
        self._info_box.setVisible(False)   # hidden by default
        root.addWidget(info_box)

        # ── Status ─────────────────────────────────────────────────────────────
        status_box = QGroupBox("Status")
        status_layout = QVBoxLayout(status_box)

        self._lbl_status = QLabel("Load a PGN to start.")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(11)
        self._lbl_status.setFont(status_font)
        status_layout.addWidget(self._lbl_status)

        root.addWidget(status_box)

        # ── Controls ───────────────────────────────────────────────────────────
        ctrl_box = QGroupBox("Controls")
        ctrl_layout = QVBoxLayout(ctrl_box)
        ctrl_layout.setSpacing(6)

        self._btn_hint = _make_button("💡  Hint", "#e07b22")
        self._btn_solution = _make_button("🔍  Show Solution", "#3a6a88")
        self._btn_reset = _make_button("↺  Reset Puzzle", "#5a7048")

        for btn in (self._btn_hint, self._btn_solution, self._btn_reset):
            ctrl_layout.addWidget(btn)

        root.addWidget(ctrl_box)

        self._btn_hint.clicked.connect(self.hint_requested)
        self._btn_solution.clicked.connect(self.solution_requested)
        self._btn_reset.clicked.connect(self.reset_requested)

        # ── Navigation ─────────────────────────────────────────────────────────
        nav_box = QGroupBox("Navigation")
        nav_layout = QHBoxLayout(nav_box)
        nav_layout.setSpacing(6)

        self._btn_prev = _make_button("◀  Prev", "#4a7c2f")
        self._btn_next = _make_button("Next  ▶", "#4a7c2f")

        nav_layout.addWidget(self._btn_prev)
        nav_layout.addWidget(self._btn_next)

        root.addWidget(nav_box)
        # Auto-advance toggle (below nav box)
        self._chk_auto_next = QCheckBox("Auto-advance after solve")
        self._chk_auto_next.setChecked(True)
        self._chk_auto_next.setToolTip(
            "Automatically move to the next puzzle after solving one.\n"
            "Disabled when the puzzle is failed or the solution is shown."
        )
        self._chk_auto_next.toggled.connect(self.auto_next_changed)
        root.addWidget(self._chk_auto_next)
        self._btn_prev.clicked.connect(self.prev_requested)
        self._btn_next.clicked.connect(self.next_requested)

        # ── Progress ───────────────────────────────────────────────────────────
        progress_box = QGroupBox("Session Progress")
        prog_layout = QVBoxLayout(progress_box)
        prog_layout.setSpacing(4)

        self._lbl_progress = QLabel("0 / 0 puzzles")
        self._lbl_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prog_layout.addWidget(self._lbl_progress)

        self._bar_solved = _make_progress_bar("#81b64c", "Solved")
        self._bar_failed = _make_progress_bar("#e74c3c", "Failed")
        prog_layout.addWidget(self._bar_solved)
        prog_layout.addWidget(self._bar_failed)

        root.addWidget(progress_box)

        root.addSpacerItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

    # ── Public update API ──────────────────────────────────────────────────────

    @property
    def is_auto_next(self) -> bool:
        """True when the auto-advance-after-solve toggle is checked."""
        return self._chk_auto_next.isChecked()

    def update_puzzle_info(
        self,
        index: int,
        total: int,
        title: str,
        white: str,
        black: str,
        player_color: chess.Color,
        previous_result: str | None = None,
    ) -> None:
        self._lbl_index.setText(f"Puzzle {index + 1} of {total}")
        self._lbl_title.setText(title)
        self._lbl_white.setText(f"White: {white}")
        self._lbl_black.setText(f"Black: {black}")
        side = "White \u2654" if player_color == chess.WHITE else "Black \u265a"
        self._lbl_side.setText(f"Side to move: {side}")

        # Previous result badge (only shown for DB-backed sets)
        if previous_result == "solved":
            self._lbl_prev_result.setText("Previous: ✓ Solved")
            self._lbl_prev_result.setStyleSheet("color: #81b64c; font-size: 11px; font-weight: bold;")
        elif previous_result == "failed":
            self._lbl_prev_result.setText("Previous: ✗ Failed")
            self._lbl_prev_result.setStyleSheet("color: #e74c3c; font-size: 11px; font-weight: bold;")
        else:
            self._lbl_prev_result.setText("")
            self._lbl_prev_result.setStyleSheet("")

        self._btn_prev.setEnabled(index > 0)
        self._btn_next.setEnabled(index < total - 1)
        self._set_controls_enabled(True)

    def set_status(self, text: str, style: str = "") -> None:
        """
        Update the status label.

        style: "success" | "error" | "info" | "" (default neutral)
        """
        colours = {
            "success": "color: #81b64c; font-weight: bold;",
            "error": "color: #e05252; font-weight: bold;",
            "info": "color: #7dd6e8; font-weight: bold;",
            "": "",
        }
        self._lbl_status.setStyleSheet(colours.get(style, ""))
        self._lbl_status.setText(text)

    def update_progress(self, total: int, solved: int, failed: int) -> None:
        self._lbl_progress.setText(
            f"{solved} solved · {failed} failed · {total} total"
        )
        if total > 0:
            self._bar_solved.setMaximum(total)
            self._bar_solved.setValue(solved)
            self._bar_failed.setMaximum(total)
            self._bar_failed.setValue(failed)

    def set_controls_enabled_for_state(
        self, *, complete: bool, is_player_turn: bool
    ) -> None:
        self._btn_hint.setEnabled(is_player_turn and not complete)
        self._btn_solution.setEnabled(not complete)
        self._btn_reset.setEnabled(True)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _on_info_toggle(self, checked: bool) -> None:
        self._info_box.setVisible(checked)
        self._btn_show_info.setText("🔎  Hide Info" if checked else "🔍  Show Info")

    def _set_no_puzzle(self) -> None:
        self._lbl_index.setText("No puzzle loaded")
        self._lbl_title.setText("—")
        self._lbl_white.setText("White: —")
        self._lbl_black.setText("Black: —")
        self._lbl_side.setText("Side to move: —")
        self.set_status("Select a puzzle set (File → Puzzle Sets) to begin.", "info")
        self._set_controls_enabled(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for btn in (
            self._btn_hint,
            self._btn_solution,
            self._btn_reset,
            self._btn_prev,
            self._btn_next,
        ):
            btn.setEnabled(enabled)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_button(text: str, colour: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {colour};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            opacity: 0.85;
            filter: brightness(110%);
        }}
        QPushButton:disabled {{
            background-color: #354530;
            color: #6a8058;
        }}
        """
    )
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return btn


def _make_progress_bar(colour: str, label: str) -> QProgressBar:
    bar = QProgressBar()
    bar.setMinimum(0)
    bar.setMaximum(1)
    bar.setValue(0)
    bar.setFormat(f"{label}: %v / %m")
    bar.setTextVisible(True)
    bar.setStyleSheet(
        f"""
        QProgressBar {{
            border: 1px solid #5a7048;
            border-radius: 4px;
            text-align: center;
            background-color: #2e3a26;
            color: #dde8cc;
        }}
        QProgressBar::chunk {{
            background-color: {colour};
            border-radius: 4px;
        }}
        """
    )
    return bar

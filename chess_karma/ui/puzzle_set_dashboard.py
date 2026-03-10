from __future__ import annotations

from enum import Enum, auto

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush,
    QLinearGradient, QPainterPath,
)
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from chess_karma.core.database import Database, PuzzleSetRow
from chess_karma.core.leaderboard import Leaderboard
from chess_karma.core.rush_manager import RushMode

# ── Palette ────────────────────────────────────────────────────────────────────
_BG          = "#354530"   # window background
_CARD_BG     = "#455238"   # stat card / section backgrounds
_BORDER      = "#5a7048"   # subtle borders
_TEXT_DIM    = "#8fa882"   # secondary text
_TEXT_BRIGHT = "#dde8cc"   # primary text

_C_TOTAL    = "#7dd6e8"    # teal  – total
_C_SOLVED   = "#81b64c"    # chess.com green – solved
_C_FAILED   = "#e05252"    # red   – failed
_C_UNTRIED  = "#f5c542"    # gold  – untried

_RUSH_ACCENT = "#7dd6e8"   # teal – rush accent

_BTN_TRAIN_ALL    = "#4a7c2f"   # chess.com green
_BTN_TRAIN_FAILED = "#9e2020"   # dark red
_BTN_RUSH_COL     = "#8a6000"   # dark gold
_BTN_CLOSE        = "#455238"   # neutral button


class DashboardAction(Enum):
    TRAIN_ALL    = auto()
    TRAIN_FAILED = auto()
    RUSH         = auto()
    CANCEL       = auto()


# ── Small helpers ──────────────────────────────────────────────────────────────

def _sep() -> QFrame:
    """1-px horizontal rule."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {_BORDER};")
    return line


def _lbl(text: str, size: int = 11, bold: bool = False,
         colour: str = _TEXT_BRIGHT, align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
    lb = QLabel(text)
    lb.setAlignment(align)
    ss = f"color: {colour}; font-size: {size}px;"
    if bold:
        ss += " font-weight: bold;"
    lb.setStyleSheet(ss)
    return lb


def _action_btn(text: str, bg: str, hover: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    btn.setMinimumHeight(40)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg};
            color: {_TEXT_BRIGHT};
            border: 1px solid {hover};
            border-radius: 6px;
            font-size: 13px;
            font-weight: bold;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
        QPushButton:pressed {{
            background-color: {bg};
            border-color: white;
        }}
        QPushButton:disabled {{
            background-color: #21262d;
            color: {_TEXT_DIM};
            border-color: {_BORDER};
        }}
    """)
    return btn


class _StatCard(QFrame):
    """A small card showing a coloured number + label."""

    def __init__(self, colour: str, value: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(88)
        self.setMinimumWidth(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {_CARD_BG};
                border: 1px solid {colour}44;
                border-left: 3px solid {colour};
                border-radius: 6px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)

        self._val_lbl = QLabel(value)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._val_lbl.setStyleSheet(
            f"color: {colour}; font-size: 28px; font-weight: bold; border: none;"
        )
        lay.addWidget(self._val_lbl)

        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 10px; letter-spacing: 1px; border: none;"
        )
        lay.addWidget(title_lbl)

    def set_value(self, v: str) -> None:
        self._val_lbl.setText(v)


class _LineChart(QWidget):
    """Custom QPainter line chart for rush session history.

    X-axis: attempt index (most recent on right, date label below).
    Y-axis: number of puzzles solved in that session.
    """

    _LINE_CLR   = QColor(_RUSH_ACCENT)
    _DOT_CLR    = QColor(_RUSH_ACCENT)
    _BEST_CLR   = QColor("#f5c542")   # gold dashed best-score line
    _GRID_CLR   = QColor(_BORDER)
    _AXIS_CLR   = QColor(_TEXT_DIM)
    _BG_CLR     = QColor(_CARD_BG)
    _FILL_START = QColor(_RUSH_ACCENT)
    _FILL_END   = QColor(_CARD_BG)

    _PAD_L = 42
    _PAD_R = 12
    _PAD_T = 28
    _PAD_B = 36

    def __init__(self, mode_label: str, best_score: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self._mode_label = mode_label
        self._best       = best_score
        self._data: list[tuple[str, int]] = []   # (date_str, score)
        self.setMinimumSize(180, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data: list[tuple[str, int]], best_score: int | None) -> None:
        self._data  = data
        self._best  = best_score
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(self._BG_CLR))
        p.drawRoundedRect(0, 0, w, h, 6, 6)

        # ── title
        title_font = QFont()
        title_font.setPixelSize(11)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QPen(QColor(_TEXT_DIM)))
        p.drawText(QRectF(self._PAD_L, 6, w - self._PAD_L - self._PAD_R, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"⚡  {self._mode_label}")

        # chart area
        cx = self._PAD_L
        cy = self._PAD_T
        cw = w - self._PAD_L - self._PAD_R
        ch = h - self._PAD_T - self._PAD_B
        if cw < 10 or ch < 10:
            p.end()
            return

        if not self._data:
            # no-data placeholder
            msg_font = QFont()
            msg_font.setPixelSize(10)
            p.setFont(msg_font)
            p.setPen(QPen(QColor(_TEXT_DIM)))
            p.drawText(QRectF(cx, cy, cw, ch),
                       Qt.AlignmentFlag.AlignCenter, "No attempts yet")
            p.end()
            return

        scores   = [s for _, s in self._data]
        y_max    = max(max(scores), self._best or 0, 1)
        y_min    = 0
        n        = len(scores)
        x_step   = cw / max(n - 1, 1)

        def _px(i: int, score: int) -> QPointF:
            x = cx + i * x_step
            y = cy + ch - ch * (score - y_min) / (y_max - y_min)
            return QPointF(x, y)

        # ── grid lines (y axis)
        small_font = QFont()
        small_font.setPixelSize(9)
        p.setFont(small_font)
        grid_pen = QPen(self._GRID_CLR, 1, Qt.PenStyle.DotLine)
        axis_pen  = QPen(QColor(_TEXT_DIM))
        n_grid = 4
        for i in range(n_grid + 1):
            yv    = y_min + (y_max - y_min) * i / n_grid
            yp    = cy + ch - ch * i / n_grid
            p.setPen(grid_pen)
            p.drawLine(QPointF(cx, yp), QPointF(cx + cw, yp))
            p.setPen(axis_pen)
            p.drawText(QRectF(0, yp - 7, self._PAD_L - 4, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       str(int(yv)))

        # ── best-score dashed line
        if self._best is not None and y_max > 0:
            by = cy + ch - ch * self._best / y_max
            best_pen = QPen(self._BEST_CLR, 1, Qt.PenStyle.DashLine)
            p.setPen(best_pen)
            p.drawLine(QPointF(cx, by), QPointF(cx + cw, by))
            p.setFont(small_font)
            p.setPen(QPen(self._BEST_CLR))
            p.drawText(QRectF(cx + 2, by - 12, 40, 12),
                       Qt.AlignmentFlag.AlignLeft, f"best {self._best}")

        # ── gradient fill under the line
        if n > 1:
            path = QPainterPath()
            path.moveTo(_px(0, scores[0]))
            for i in range(1, n):
                path.lineTo(_px(i, scores[i]))
            path.lineTo(QPointF(cx + (n - 1) * x_step, cy + ch))
            path.lineTo(QPointF(cx, cy + ch))
            path.closeSubpath()

            grad = QLinearGradient(0, cy, 0, cy + ch)
            start_c = QColor(self._FILL_START)
            start_c.setAlpha(80)
            end_c = QColor(self._FILL_END)
            end_c.setAlpha(0)
            grad.setColorAt(0.0, start_c)
            grad.setColorAt(1.0, end_c)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawPath(path)

        # ── line
        line_pen = QPen(self._LINE_CLR, 2)
        p.setPen(line_pen)
        for i in range(n - 1):
            p.drawLine(_px(i, scores[i]), _px(i + 1, scores[i + 1]))

        # ── dots + x-axis date labels
        p.setFont(small_font)
        max_date_labels = 6
        step = max(1, n // max_date_labels)
        for i, (date_str, score) in enumerate(self._data):
            pt = _px(i, score)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(self._DOT_CLR))
            p.drawEllipse(pt, 3.5, 3.5)

            if i % step == 0 or i == n - 1:
                short_date = date_str[5:]   # "MM-DD HH:MM" → trim year
                p.setPen(QPen(QColor(_TEXT_DIM)))
                p.drawText(
                    QRectF(pt.x() - 22, cy + ch + 4, 44, 14),
                    Qt.AlignmentFlag.AlignCenter, short_date[:5],  # "MM-DD" only
                )

        p.end()


class _ProgressBar(QWidget):
    """Custom segmented progress bar: green | red | amber."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._solved = 0
        self._failed = 0
        self._total  = 1
        self.setFixedHeight(10)
        self.setMinimumWidth(1)

    def set_values(self, total: int, solved: int, failed: int) -> None:
        self._total  = max(total, 1)
        self._solved = solved
        self._failed = failed
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        radius = h / 2

        # background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(_BORDER)))
        p.drawRoundedRect(0, 0, w, h, radius, radius)

        # solved segment
        sw = int(w * self._solved / self._total)
        if sw > 0:
            p.setBrush(QBrush(QColor(_C_SOLVED)))
            p.drawRoundedRect(0, 0, sw, h, radius, radius)

        # failed segment
        fw = int(w * self._failed / self._total)
        if fw > 0:
            p.setBrush(QBrush(QColor(_C_FAILED)))
            x = sw
            p.drawRect(x, 0, fw, h)

        p.end()


# ── Main dialog ────────────────────────────────────────────────────────────────

class PuzzleSetDashboard(QDialog):
    """Stylised dashboard dialog for a puzzle set.

    After exec() returns, read ``dlg.selected_action`` (a DashboardAction).
    """

    def __init__(self, db: Database, set_id: int, leaderboard: Leaderboard,
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Puzzle Set Dashboard")
        self.setModal(True)
        self.setMinimumSize(680, 520)
        self.resize(760, 560)
        self.setStyleSheet(f"QDialog {{ background-color: {_BG}; }}")

        self._db          = db
        self._leaderboard = leaderboard
        self._set_id      = set_id
        self.selected_action = DashboardAction.CANCEL

        self._build_ui()
        self._load_stats()

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Header ──────────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {_CARD_BG};
                border-radius: 8px;
                border: 1px solid {_BORDER};
            }}
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(18, 14, 18, 14)
        h_lay.setSpacing(4)

        self._name_label = QLabel("—")
        self._name_label.setStyleSheet(
            f"color: {_TEXT_BRIGHT}; font-size: 22px; font-weight: bold; border: none;"
        )
        h_lay.addWidget(self._name_label)

        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 11px; border: none;"
        )
        h_lay.addWidget(self._meta_label)

        root.addWidget(header)

        # ── Stat cards row ───────────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)

        self._card_total   = _StatCard(_C_TOTAL,   "0", "Total Puzzles")
        self._card_solved  = _StatCard(_C_SOLVED,  "0", "Solved")
        self._card_failed  = _StatCard(_C_FAILED,  "0", "Failed")
        self._card_untried = _StatCard(_C_UNTRIED, "0", "Untried")

        for card in (self._card_total, self._card_solved,
                     self._card_failed, self._card_untried):
            cards_row.addWidget(card)

        root.addLayout(cards_row)

        # ── Progress bar section ─────────────────────────────────────────────────
        prog_section = QWidget()
        prog_section.setStyleSheet(f"""
            QWidget {{
                background-color: {_CARD_BG};
                border-radius: 8px;
                border: 1px solid {_BORDER};
            }}
        """)
        prog_lay = QVBoxLayout(prog_section)
        prog_lay.setContentsMargins(16, 12, 16, 12)
        prog_lay.setSpacing(6)

        prog_header = QHBoxLayout()
        prog_lbl = _lbl("TRAINING PROGRESS", 10, bold=True, colour=_TEXT_DIM)
        prog_header.addWidget(prog_lbl)
        prog_header.addStretch()
        self._pct_label = _lbl("0%", 13, bold=True, colour=_TEXT_BRIGHT,
                                align=Qt.AlignmentFlag.AlignRight)
        prog_header.addWidget(self._pct_label)
        prog_lay.addLayout(prog_header)

        self._progress_bar = _ProgressBar()
        prog_lay.addWidget(self._progress_bar)

        legend = QHBoxLayout()
        legend.setSpacing(16)
        for colour, label in ((_C_SOLVED, "● Solved"), (_C_FAILED, "● Failed"),
                               (_BORDER, "● Untried")):
            lb = _lbl(label, 10, colour=colour)
            legend.addWidget(lb)
        legend.addStretch()
        prog_lay.addLayout(legend)

        root.addWidget(prog_section)

        # ── Rush performance charts ────────────────────────────────────────────
        charts_section = QWidget()
        charts_section.setStyleSheet(f"""
            QWidget {{
                background-color: {_CARD_BG};
                border-radius: 8px;
                border: 1px solid {_BORDER};
            }}
        """)
        charts_lay = QVBoxLayout(charts_section)
        charts_lay.setContentsMargins(14, 10, 14, 10)
        charts_lay.setSpacing(8)

        charts_hdr = QHBoxLayout()
        charts_hdr.addWidget(_lbl("⚡  PUZZLE RUSH HISTORY", 10, bold=True, colour=_TEXT_DIM))
        charts_hdr.addStretch()
        charts_hdr.addWidget(_lbl("-- best score", 9, colour="#f5c542"))
        charts_lay.addLayout(charts_hdr)

        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)
        self._chart_3min     = _LineChart("3 Minutes")
        self._chart_5min     = _LineChart("5 Minutes")
        self._chart_survival = _LineChart("Survival")
        for c in (self._chart_3min, self._chart_5min, self._chart_survival):
            charts_row.addWidget(c)
        charts_lay.addLayout(charts_row, stretch=1)

        root.addWidget(charts_section, stretch=1)

        # ── Action buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_train_all    = _action_btn("📚  Train All Puzzles",       _BTN_TRAIN_ALL,    "#2ea043")
        self._btn_train_failed = _action_btn("🔴  Train Failed Puzzles",    _BTN_TRAIN_FAILED, "#da3633")
        self._btn_rush         = _action_btn("⚡  Start Puzzle Rush",        _BTN_RUSH_COL,     "#d29922")
        self._btn_close        = _action_btn("✕  Close",                    _BTN_CLOSE,        "#5a7048")
        self._btn_close.setMinimumWidth(90)
        self._btn_close.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        btn_row.addWidget(self._btn_train_all)
        btn_row.addWidget(self._btn_train_failed)
        btn_row.addWidget(self._btn_rush)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_close)

        root.addLayout(btn_row)

        # connections
        self._btn_train_all.clicked.connect(self._on_train_all)
        self._btn_train_failed.clicked.connect(self._on_train_failed)
        self._btn_rush.clicked.connect(self._on_rush)
        self._btn_close.clicked.connect(self.reject)

    # ── Data loading ────────────────────────────────────────────────────────────

    def _load_stats(self) -> None:
        s: PuzzleSetRow | None = self._db.get_set(self._set_id)
        if s is None:
            return

        # Header
        self._name_label.setText(f"♟  {s.name}")
        parts = []
        if s.created_at:
            parts.append(f"Created {s.created_at}")
        if s.last_played_at:
            parts.append(f"Last played {s.last_played_at}")
        self._meta_label.setText("  ·  ".join(parts) if parts else "Never played")

        # Stat cards
        self._card_total.set_value(str(s.total_puzzles))
        self._card_solved.set_value(str(s.solved))
        self._card_failed.set_value(str(s.failed))
        self._card_untried.set_value(str(s.untried))

        # Progress bar
        self._progress_bar.set_values(s.total_puzzles, s.solved, s.failed)
        self._pct_label.setText(f"{s.pct_done:.0f}% attempted")

        # Enable / disable train-failed button
        if s.failed == 0:
            self._btn_train_failed.setEnabled(False)
            self._btn_train_failed.setToolTip("No failed puzzles yet")
        else:
            self._btn_train_failed.setText(
                f"🔴  Train Failed Puzzles ({s.failed})"
            )

        # Rush performance charts
        _chart_map = {
            RushMode.THREE_MIN: self._chart_3min,
            RushMode.FIVE_MIN:  self._chart_5min,
            RushMode.SURVIVAL:  self._chart_survival,
        }
        for mode, chart in _chart_map.items():
            history = self._db.get_rush_history(mode.value, set_id=self._set_id)  # [(date, score), ...]
            tops    = self._leaderboard.get_top(mode)
            best    = tops[0].score if tops else None
            chart.set_data(history, best)

    # ── Button handlers ─────────────────────────────────────────────────────────

    def _on_train_all(self) -> None:
        self.selected_action = DashboardAction.TRAIN_ALL
        self.accept()

    def _on_train_failed(self) -> None:
        self.selected_action = DashboardAction.TRAIN_FAILED
        self.accept()

    def _on_rush(self) -> None:
        self.selected_action = DashboardAction.RUSH
        self.accept()

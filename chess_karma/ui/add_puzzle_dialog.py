"""
AddPuzzleDialog – add a single puzzle to a named puzzle set.

Specify the board position by typing a FEN string (or keeping the starting position).

After confirming the FEN the user types the solution moves in SAN notation
(e.g. "1. Qxf7+ Ke7 2. Nd5#").  Title / White / Black are optional metadata.
The finished PGN is inserted into the DB via database.add_puzzle().
"""

from __future__ import annotations

import io
from typing import Optional

import chess
import chess.pgn
import chess.svg
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chess_karma.core.database import Database

_STARTING_FEN = chess.STARTING_FEN


# ── Helpers ───────────────────────────────────────────────────────────────────

def _render_fen_to_pixmap(fen: str, size: int = 240) -> QPixmap | None:
    """Render a FEN position to a QPixmap using chess.svg."""
    try:
        board = chess.Board(fen)
    except Exception:
        return None
    svg_text = chess.svg.board(board, size=size)
    renderer = QSvgRenderer(QByteArray(svg_text.encode()))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def _parse_moves(fen: str, moves_text: str) -> tuple[bool, str, str]:
    """
    Try to parse SAN/UCI moves from moves_text against the given FEN.
    Returns (ok, pgn_text, error_message).
    """
    moves_text = moves_text.strip()
    if not moves_text:
        # No moves supplied is valid; store as a position-only annotation
        try:
            board = chess.Board(fen)
        except Exception as exc:
            return False, "", f"Invalid FEN: {exc}"
        game = chess.pgn.Game()
        game.setup(board)
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return True, game.accept(exporter), ""

    # Wrap in a minimal PGN so python-chess can parse it
    pgn_src = f'[FEN "{fen}"]\n\n{moves_text}\n'
    try:
        reader = io.StringIO(pgn_src)
        game = chess.pgn.read_game(reader)
        if game is None:
            return False, "", "Could not parse moves."
        # Verify the game has at least one move
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        pgn_text = game.accept(exporter)
        return True, pgn_text, ""
    except Exception as exc:
        return False, "", str(exc)


# ── Main dialog ───────────────────────────────────────────────────────────────

class AddPuzzleDialog(QDialog):
    """
    Modal dialog for adding a single puzzle to a set.

    Usage:
        dlg = AddPuzzleDialog(db, set_id, parent=self)
        dlg.exec()        # puzzle is written to DB on Accept
    """

    def __init__(
        self,
        db: Database,
        set_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Puzzle")
        self.setMinimumSize(700, 580)
        self.setModal(True)

        self._db = db
        self._set_id = set_id
        self._current_fen: str = _STARTING_FEN

        self._build_ui()
        self._update_preview(_STARTING_FEN)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        body = QHBoxLayout()
        body.setSpacing(14)

        # ── Left: tabs for FEN input ─────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setMinimumWidth(320)

        tabs.addTab(self._build_manual_tab(), "✏  Manual")

        body.addWidget(tabs, stretch=1)

        # ── Right: board preview + moves + metadata ──────────────────────────
        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        # Board preview
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(260, 260)
        self._preview_label.setStyleSheet(
            "border: 1px solid #5a7048; border-radius: 4px; background: #2e3a26;"
        )
        right_panel.addWidget(self._preview_label)

        # Side to move
        side_row = QHBoxLayout()
        side_row.addWidget(QLabel("Side to move:"))
        self._side_combo = QComboBox()
        self._side_combo.addItems(["White (w)", "Black (b)"])
        self._side_combo.currentIndexChanged.connect(self._on_side_changed)
        side_row.addWidget(self._side_combo)
        side_row.addStretch()
        right_panel.addLayout(side_row)

        # Metadata
        meta_form = QFormLayout()
        meta_form.setSpacing(6)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("e.g. Mate in 2, Exercise 513 …")
        meta_form.addRow("Title:", self._title_edit)

        players = QHBoxLayout()
        self._white_edit = QLineEdit()
        self._white_edit.setPlaceholderText("White")
        self._black_edit = QLineEdit()
        self._black_edit.setPlaceholderText("Black")
        players.addWidget(self._white_edit)
        players.addWidget(QLabel("vs"))
        players.addWidget(self._black_edit)
        meta_form.addRow("Players:", players)

        right_panel.addLayout(meta_form)

        # Moves
        right_panel.addWidget(QLabel("Solution moves (SAN):"))
        self._moves_edit = QTextEdit()
        self._moves_edit.setPlaceholderText(
            "e.g.  1. Qxf7+ Ke7  2. Nd5#\n(Leave blank for position-only)"
        )
        self._moves_edit.setMaximumHeight(90)
        right_panel.addWidget(self._moves_edit)

        right_panel.addStretch()
        body.addLayout(right_panel, stretch=1)
        root.addLayout(body, stretch=1)

        # ── Dialog buttons ───────────────────────────────────────────────────
        btn_box = QDialogButtonBox()
        self._add_btn = QPushButton("➕  Add Puzzle")
        self._add_btn.setDefault(True)
        self._add_btn.setStyleSheet(
            "QPushButton { background: #4a7c2f; color: white; border: none;"
            " border-radius: 4px; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #5a9438; }"
        )
        cancel_btn = QPushButton("Cancel")
        btn_box.addButton(cancel_btn,   QDialogButtonBox.ButtonRole.RejectRole)
        btn_box.addButton(self._add_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btn_box.rejected.connect(self.reject)
        self._add_btn.clicked.connect(self._on_add)
        root.addWidget(btn_box)

    # ── Manual tab ────────────────────────────────────────────────────────────

    def _build_manual_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(QLabel("FEN string:"))
        fen_row = QHBoxLayout()
        self._manual_fen_edit = QLineEdit(_STARTING_FEN)
        self._manual_fen_edit.setPlaceholderText("Paste FEN here …")
        self._manual_fen_edit.textChanged.connect(self._on_manual_fen_changed)
        fen_row.addWidget(self._manual_fen_edit)
        validate_btn = QPushButton("✔ Validate")
        validate_btn.clicked.connect(lambda: self._validate_and_apply_fen(
            self._manual_fen_edit.text().strip()
        ))
        fen_row.addWidget(validate_btn)
        layout.addLayout(fen_row)

        self._manual_fen_status = QLabel("")
        self._manual_fen_status.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._manual_fen_status)

        layout.addWidget(QLabel(
            "Enter the position FEN, or leave as the starting position.\n"
            "Use the board preview (right) to verify the position."
        ))
        layout.addStretch()
        return w

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _on_manual_fen_changed(self, text: str) -> None:
        ok, _ = _try_parse_fen(text.strip())
        if ok:
            self._current_fen = text.strip()
            self._update_preview(self._current_fen)
            self._manual_fen_status.setText("✔ Valid FEN")
            self._manual_fen_status.setStyleSheet("font-size: 11px; color: #81b64c;")
        else:
            self._manual_fen_status.setText("⚠ Invalid FEN")
            self._manual_fen_status.setStyleSheet("font-size: 11px; color: #e74c3c;")

    def _on_side_changed(self, _index: int) -> None:
        self._update_fen_side()
        self._update_preview(self._current_fen)

    def _on_add(self) -> None:
        fen = self._current_fen.strip()
        ok, err = _try_parse_fen(fen)
        if not ok:
            QMessageBox.warning(self, "Invalid FEN", f"The FEN is not valid:\n{err}")
            return

        moves_text = self._moves_edit.toPlainText().strip()
        ok, pgn_text, err = _parse_moves(fen, moves_text)
        if not ok:
            QMessageBox.warning(
                self,
                "Invalid Moves",
                f"Could not parse the solution moves:\n{err}\n\n"
                "Please use SAN notation (e.g. 1. e4 e5 2. Nf3).",
            )
            return

        # Inject metadata headers into pgn_text
        pgn_text = self._inject_headers(pgn_text, fen)

        title = self._title_edit.text().strip() or "Puzzle"
        white = self._white_edit.text().strip() or "?"
        black = self._black_edit.text().strip() or "?"

        try:
            self._db.add_puzzle(
                set_id=self._set_id,
                pgn_text=pgn_text,
                title=title,
                white=white,
                black=black,
                event=title,
                fen=fen,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", str(exc))
            return

        self.accept()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _validate_and_apply_fen(self, fen: str) -> None:
        ok, err = _try_parse_fen(fen)
        if ok:
            self._current_fen = fen
            self._update_preview(fen)
            # Sync side-to-move combo from FEN
            parts = fen.split()
            if len(parts) >= 2:
                self._side_combo.setCurrentIndex(0 if parts[1] == "w" else 1)
        else:
            QMessageBox.warning(self, "Invalid FEN", f"Not a valid FEN:\n{err}")

    def _update_preview(self, fen: str) -> None:
        pix = _render_fen_to_pixmap(fen, size=240)
        if pix:
            self._preview_label.setPixmap(pix)
        else:
            self._preview_label.setText("(Invalid FEN)")

    def _update_fen_side(self) -> None:
        """Swap side-to-move in the current FEN to match the combo box."""
        side = "b" if self._side_combo.currentIndex() == 1 else "w"
        parts = self._current_fen.split()
        if len(parts) >= 2:
            parts[1] = side
            new_fen = " ".join(parts)
            ok, _ = _try_parse_fen(new_fen)
            if ok:
                self._current_fen = new_fen
                # Propagate back to visible FEN fields
                self._manual_fen_edit.blockSignals(True)
                self._manual_fen_edit.setText(self._current_fen)
                self._manual_fen_edit.blockSignals(False)

    def _inject_headers(self, pgn_text: str, fen: str) -> str:
        """Re-parse the PGN and inject Title/White/Black/FEN headers."""
        reader = io.StringIO(pgn_text)
        game = chess.pgn.read_game(reader)
        if game is None:
            return pgn_text
        title = self._title_edit.text().strip() or "Puzzle"
        white = self._white_edit.text().strip() or "?"
        black = self._black_edit.text().strip() or "?"
        game.headers["Event"] = title
        game.headers["White"] = white
        game.headers["Black"] = black
        game.headers["FEN"]   = fen
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return game.accept(exporter)


# ── Module-level helpers ──────────────────────────────────────────────────────

def _try_parse_fen(fen: str) -> tuple[bool, str]:
    if not fen:
        return False, "Empty FEN."
    try:
        chess.Board(fen)
        return True, ""
    except Exception as exc:
        return False, str(exc)

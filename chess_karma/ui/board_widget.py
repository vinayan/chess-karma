"""
BoardWidget – an interactive chess board rendered from SVG (python-chess).

Rendering pipeline
──────────────────
  chess.svg.board()  →  QSvgRenderer  →  QPainter  →  QWidget

Coordinate mapping
──────────────────
The chess.svg module uses a fixed viewBox:

    SIZE   = 8 * SQUARE_SIZE + 2 * MARGIN  =  8*45 + 2*15  =  390 px
    MARGIN = 15 px  (border reserved for coordinate labels)
    SQUARE_SIZE = 45 px

When the widget is rendered at an arbitrary pixel size *w* the scale factor is:

    scale = w / 390

A mouse click at widget pixel (px, py) maps to chess square:

    file = floor( (px − x_off − MARGIN*scale) / (SQUARE_SIZE*scale) )
    rank = 7 − floor( (py − y_off − MARGIN*scale) / (SQUARE_SIZE*scale) )

With the board flipped both file and rank are mirrored.

Interaction modes
──────────────────
  Click-to-move: press on a piece to select it, press on a target to move.
  Drag-to-move:  press and drag a piece to its target square, release to drop.
  Both modes can be used interchangeably.
"""

from __future__ import annotations

import chess
import chess.svg
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QSizePolicy, QWidget

# ── Constants (must match chess.svg internals) ─────────────────────────────────
_SVG_MARGIN: float = 15.0
_SVG_SQUARE: float = 45.0
_SVG_SIZE: float = 8 * _SVG_SQUARE + 2 * _SVG_MARGIN  # 390.0

# Pixels the mouse must travel before a press becomes a drag
_DRAG_THRESHOLD: float = 6.0

# Size of the ghost piece rendered under the cursor while dragging (widget px)
_GHOST_SIZE: int = 72

# ── Chess.com default board theme ─────────────────────────────────────────────
# Board square / margin colours
_BOARD_COLORS = {
    "square light": "#EEEED2",   # cream
    "square dark":  "#769656",   # green
    "margin":       "#769656",   # border band – same as dark square
    "coord":        "#EEEED2",   # rank/file label text
}

# Per-square highlight fills (8-digit hex = RRGGBBAA)
_HL_LAST_FROM  = "#F6F66966"   # last-move origin  – muted yellow (40 % opacity)
_HL_LAST_TO    = "#BACA44CC"   # last-move target  – yellow-green  (80 % opacity)
_HL_SELECTED   = "#14551E99"   # selected piece    – chess.com dark-green (60 %)
_HL_LEGAL      = "#14551E3D"   # legal-move target – very subtle green dot (24 %)

# Arrow colours
_ARROW_HINT     = "#15781499"   # hint arrow   – chess.com green
_ARROW_SOLUTION = "#1B5FA699"   # solution arrows – chess.com blue


class _PromotionDialog(QDialog):
    """
    Modal dialog that lets the player pick a promotion piece.
    Shows four piece buttons (Q / R / B / N) for the given colour.
    """

    _PIECES = [
        (chess.QUEEN,  "Q"),
        (chess.ROOK,   "R"),
        (chess.BISHOP, "B"),
        (chess.KNIGHT, "N"),
    ]
    _BTN_SIZE = 72

    def __init__(self, color: chess.Color, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Promote pawn")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.chosen: chess.PieceType | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        for piece_type, label in self._PIECES:
            btn = QPushButton()
            btn.setFixedSize(self._BTN_SIZE, self._BTN_SIZE)
            btn.setToolTip(label)
            btn.setStyleSheet(
                "QPushButton { border: 2px solid #5a7048; border-radius: 4px; background: #2e3a26; }"
                "QPushButton:hover { border-color: #81b64c; background: #3a4a34; }"
            )
            # Render piece SVG as button icon
            piece = chess.Piece(piece_type, color)
            svg_str = chess.svg.piece(piece, size=self._BTN_SIZE)
            renderer = QSvgRenderer(svg_str.encode("utf-8"))
            pixmap = QPixmap(self._BTN_SIZE, self._BTN_SIZE)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter, QRectF(0, 0, self._BTN_SIZE, self._BTN_SIZE))
            painter.end()
            from PyQt6.QtGui import QIcon
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(pixmap.size())

            btn.clicked.connect(lambda _checked, pt=piece_type: self._pick(pt))
            layout.addWidget(btn)

        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    def _pick(self, piece_type: chess.PieceType) -> None:
        self.chosen = piece_type
        self.accept()


class BoardWidget(QWidget):
    """
    Interactive chess board widget.

    Signals
    ───────
    move_made(chess.Move)  – emitted when the player clicks a legal move.
    """

    move_made = pyqtSignal(object)  # carries chess.Move

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._board: chess.Board = chess.Board()
        self._flipped: bool = False
        self._player_color: chess.Color = chess.WHITE
        self._interactive: bool = True

        self._selected_sq: int | None = None
        self._legal_targets: list[int] = []
        self._last_move: chess.Move | None = None
        self._hint_move: chess.Move | None = None
        self._arrow_moves: list[chess.Move] = []   # solution arrows (show solution)

        # ── Drag state ──────────────────────────────────────────────────────────
        self._drag_active: bool = False          # True once threshold crossed
        self._drag_from_sq: int | None = None    # origin square
        self._press_pos: QPointF | None = None   # where the mouse was pressed
        self._drag_pos: QPointF | None = None    # current cursor position
        self._drag_pixmap: QPixmap | None = None # rendered ghost piece

        self._renderer = QSvgRenderer()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 320)
        self.setMouseTracking(False)  # only track when button held
        self._rebuild_svg()

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_board(
        self,
        board: chess.Board,
        player_color: chess.Color = chess.WHITE,
        flipped: bool | None = None,
    ) -> None:
        """Replace the displayed position.  Clears selection and arrows."""
        self._board = board
        self._player_color = player_color
        self._flipped = (player_color == chess.BLACK) if flipped is None else flipped
        self._selected_sq = None
        self._legal_targets = []
        self._hint_move = None
        self._arrow_moves = []
        self._rebuild_svg()

    def update_board(self, board: chess.Board, last_move: chess.Move | None = None) -> None:
        """Refresh after a move without resetting the full state."""
        self._board = board
        if last_move is not None:
            self._last_move = last_move
        self._selected_sq = None
        self._legal_targets = []
        self._hint_move = None
        self._rebuild_svg()

    def set_hint(self, move: chess.Move | None) -> None:
        """Display a green arrow for the move hint."""
        self._hint_move = move
        self._arrow_moves = []
        self._rebuild_svg()

    def set_solution_arrows(self, moves: list[chess.Move]) -> None:
        """Display solution arrows (multiple half-transparent arrows)."""
        self._arrow_moves = moves
        self._hint_move = None
        self._rebuild_svg()

    def set_interactive(self, enabled: bool) -> None:
        """Enable or disable mouse interaction."""
        self._interactive = enabled
        if not enabled:
            self._cancel_drag()
            self._selected_sq = None
            self._legal_targets = []
            self._rebuild_svg()

    def clear_decorations(self) -> None:
        """Remove all arrows and highlights (except last-move highlight)."""
        self._hint_move = None
        self._arrow_moves = []
        self._selected_sq = None
        self._legal_targets = []
        self._rebuild_svg()

    # ── SVG generation ─────────────────────────────────────────────────────────

    def _rebuild_svg(self) -> None:
        arrows: list[chess.svg.Arrow] = []

        if self._hint_move:
            arrows.append(
                chess.svg.Arrow(
                    self._hint_move.from_square,
                    self._hint_move.to_square,
                    color=_ARROW_HINT,
                )
            )

        for mv in self._arrow_moves:
            arrows.append(
                chess.svg.Arrow(mv.from_square, mv.to_square, color=_ARROW_SOLUTION)
            )

        fill: dict[int, str] = {}

        # Last-move highlight – chess.com yellow tones
        if self._last_move:
            fill[self._last_move.from_square] = _HL_LAST_FROM
            fill[self._last_move.to_square]   = _HL_LAST_TO

        # Selected piece / drag-origin highlight – chess.com dark green
        src_sq = self._drag_from_sq if self._drag_active else self._selected_sq
        if src_sq is not None:
            fill[src_sq] = _HL_SELECTED

        # Legal-move target squares – subtle green overlay
        for sq in self._legal_targets:
            fill[sq] = _HL_LEGAL

        # While dragging, temporarily remove the piece from its origin square
        # so it appears to "lift off" the board.
        render_board = self._board
        if self._drag_active and self._drag_from_sq is not None:
            render_board = self._board.copy()
            render_board.remove_piece_at(self._drag_from_sq)

        svg_text = chess.svg.board(
            render_board,
            flipped=self._flipped,
            arrows=arrows,
            fill=fill,
            colors=_BOARD_COLORS,
            size=int(_SVG_SIZE),
        )
        self._renderer.load(svg_text.encode("utf-8"))
        self.update()

    def _make_drag_pixmap(self, piece: chess.Piece) -> QPixmap:
        """Render a piece SVG into a QPixmap for use as the drag ghost."""
        svg_str = chess.svg.piece(piece, size=_GHOST_SIZE)
        renderer = QSvgRenderer(svg_str.encode("utf-8"))
        pixmap = QPixmap(_GHOST_SIZE, _GHOST_SIZE)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, _GHOST_SIZE, _GHOST_SIZE))
        painter.end()
        return pixmap

    # ── Qt overrides ───────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        sz = float(min(self.width(), self.height()))
        x_off = (self.width() - sz) / 2.0
        y_off = (self.height() - sz) / 2.0
        self._renderer.render(painter, QRectF(x_off, y_off, sz, sz))

        # Draw ghost piece centred on the cursor during a drag
        if self._drag_active and self._drag_pos is not None and self._drag_pixmap:
            half = _GHOST_SIZE / 2.0
            painter.setOpacity(0.85)
            painter.drawPixmap(
                int(self._drag_pos.x() - half),
                int(self._drag_pos.y() - half),
                self._drag_pixmap,
            )
            painter.setOpacity(1.0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # No re-render needed; paintEvent always recomputes the target rect.

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._interactive:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.position()
        sq = self._pixel_to_square(pos.x(), pos.y())
        if sq is None:
            return

        piece = self._board.piece_at(sq)
        if (
            piece
            and piece.color == self._player_color
            and piece.color == self._board.turn
        ):
            # Could become either a drag or a click; record the press and wait.
            self._press_pos = pos
            self._drag_from_sq = sq
            self._drag_pixmap = self._make_drag_pixmap(piece)
            # Pre-select for click-to-move feedback
            self._try_select(sq)
        else:
            # Clicking on a non-own square: handle as a click-to-move target.
            self._press_pos = None
            self._drag_from_sq = None
            self._handle_click(sq)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._interactive or self._press_pos is None:
            return

        pos = event.position()
        delta_x = pos.x() - self._press_pos.x()
        delta_y = pos.y() - self._press_pos.y()
        dist = (delta_x ** 2 + delta_y ** 2) ** 0.5

        if not self._drag_active and dist >= _DRAG_THRESHOLD:
            # Cross the threshold → switch from potential-click to drag
            self._drag_active = True
            # Clear the click-selection visuals; the SVG will hide the lifted piece
            self._selected_sq = None
            self._legal_targets = [
                m.to_square
                for m in self._board.legal_moves
                if m.from_square == self._drag_from_sq
            ]
            self._rebuild_svg()

        if self._drag_active:
            self._drag_pos = pos
            self.update()  # repaint to move the ghost piece

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if not self._interactive:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.position()

        if self._drag_active:
            # ── Complete the drag ──────────────────────────────────────────────
            to_sq = self._pixel_to_square(pos.x(), pos.y())
            from_sq = self._drag_from_sq
            self._cancel_drag()

            if to_sq is not None and from_sq is not None and to_sq != from_sq:
                self._selected_sq = from_sq
                self._try_move(to_sq)
            else:
                # Dropped back on origin or off-board → cancel
                self._selected_sq = None
                self._legal_targets = []
                self._rebuild_svg()
        else:
            # ── Short press – treat as a click ─────────────────────────────────
            # The piece was already selected in mousePressEvent; nothing more to do.
            # Pressing _this_ release means the user just clicked (didn't drag).
            # The selection is already shown; next click on a target will move.
            self._press_pos = None
            self._drag_from_sq = None

    # ── Move interaction ───────────────────────────────────────────────────────

    def _handle_click(self, sq: int) -> None:
        if self._selected_sq is None:
            self._try_select(sq)
        else:
            if sq == self._selected_sq:
                # Deselect
                self._selected_sq = None
                self._legal_targets = []
                self._rebuild_svg()
                return

            piece = self._board.piece_at(sq)
            if (
                piece
                and piece.color == self._player_color
                and piece.color == self._board.turn
            ):
                # Re-select another own piece
                self._try_select(sq)
                return

            # Attempt move
            self._try_move(sq)

    def _try_select(self, sq: int) -> None:
        piece = self._board.piece_at(sq)
        if (
            piece
            and piece.color == self._player_color
            and piece.color == self._board.turn
        ):
            self._selected_sq = sq
            self._legal_targets = [
                m.to_square for m in self._board.legal_moves if m.from_square == sq
            ]
        else:
            self._selected_sq = None
            self._legal_targets = []
        self._rebuild_svg()

    def _try_move(self, to_sq: int) -> None:
        from_sq = self._selected_sq
        if from_sq is None:
            return

        # Check whether this is a pawn promotion move
        piece = self._board.piece_at(from_sq)
        is_promotion = (
            piece is not None
            and piece.piece_type == chess.PAWN
            and chess.square_rank(to_sq) in (0, 7)
        )

        # Verify the target square is actually a legal destination before
        # opening the dialog (avoids a dialog for an illegal pawn push).
        promotion_check = chess.QUEEN if is_promotion else None
        if chess.Move(from_sq, to_sq, promotion=promotion_check) not in self._board.legal_moves:
            self._selected_sq = None
            self._legal_targets = []
            self._rebuild_svg()
            return

        if is_promotion:
            dlg = _PromotionDialog(self._board.turn, parent=self)
            # Centre dialog over the board widget
            dlg.move(
                self.mapToGlobal(self.rect().center())
                - dlg.rect().center()
            )
            if dlg.exec() != QDialog.DialogCode.Accepted or dlg.chosen is None:
                # User cancelled – keep selection so they can try again
                self._rebuild_svg()
                return
            promotion = dlg.chosen
        else:
            promotion = None

        move = chess.Move(from_sq, to_sq, promotion=promotion)

        self._selected_sq = None
        self._legal_targets = []

        if move in self._board.legal_moves:
            self._last_move = move
            self._hint_move = None
            self._rebuild_svg()
            self.move_made.emit(move)
        else:
            self._rebuild_svg()

    def _cancel_drag(self) -> None:
        """Reset all drag state."""
        self._drag_active = False
        self._drag_from_sq = None
        self._press_pos = None
        self._drag_pos = None
        self._drag_pixmap = None

    # ── Coordinate mapping ─────────────────────────────────────────────────────

    def _pixel_to_square(self, px: float, py: float) -> int | None:
        """Map widget pixel (px, py) to a chess square index, or None."""
        sz = float(min(self.width(), self.height()))
        x_off = (self.width() - sz) / 2.0
        y_off = (self.height() - sz) / 2.0

        scale = sz / _SVG_SIZE
        margin = _SVG_MARGIN * scale
        sq_px = _SVG_SQUARE * scale

        bx = (px - x_off - margin) / sq_px
        by = (py - y_off - margin) / sq_px

        if not (0.0 <= bx < 8.0 and 0.0 <= by < 8.0):
            return None

        file_ = int(bx)
        rank_ = 7 - int(by)

        if self._flipped:
            file_ = 7 - file_
            rank_ = 7 - rank_

        return chess.square(file_, rank_)

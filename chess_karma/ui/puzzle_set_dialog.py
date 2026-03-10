"""
PuzzleSetDialog – manage named puzzle sets stored in the local database.

Layout
──────
┌────────────────────────────────────────────────────────────────┐
│  📚 Puzzle Sets                                               │
│  ┌─ Name ──┬ Total ┬ ✓ ┬ ✗ ┬ Untried ┬ % ┬ Last Played ─┐  │
│  │  …      │       │   │   │         │   │               │  │
│  └─────────┴───────┴───┴───┴─────────┴───┴───────────────┘  │
│  [Import]  [New]  [Rename]  [Delete]  [Reset]  [+Puzzle]  [▶]│
└────────────────────────────────────────────────────────────────┘

The dialog returns Accepted when the user clicks Open Set.
Read .selected_set_id after exec().
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chess_karma.core.database import Database, PuzzleSetRow


# Column indices for the Sets table
_SC_NAME    = 0
_SC_TOTAL   = 1
_SC_SOLVED  = 2
_SC_FAILED  = 3
_SC_UNTRIED = 4
_SC_PCT     = 5
_SC_PLAYED  = 6


class PuzzleSetDialog(QDialog):
    """
    Modal dialog for browsing, importing, and managing puzzle sets.

    After exec_() returns Accepted, read .selected_set_id (int) for the
    id of the set to load.  Returns Rejected on Close without opening.
    """

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Puzzle Sets")
        self.setMinimumSize(620, 360)
        self.setModal(True)

        self._db = db
        self.selected_set_id: int | None = None

        self._build_ui()
        self._refresh_sets()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 10, 12, 10)

        # Header
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        hdr = QLabel("📚  Puzzle Sets")
        hdr.setFont(title_font)
        root.addWidget(hdr)

        # ── Sets table ─────────────────────────────────────────────────────────
        self._sets_table = QTableWidget()
        self._sets_table.setColumnCount(7)
        self._sets_table.setHorizontalHeaderLabels(
            ["Name", "Total", "✓ Solved", "✗ Failed", "Untried", "%", "Last Played"]
        )
        self._sets_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._sets_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._sets_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sets_table.setAlternatingRowColors(True)
        self._sets_table.verticalHeader().setVisible(False)
        self._sets_table.setShowGrid(False)
        hh = self._sets_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 7):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._sets_table.doubleClicked.connect(self._on_open)
        self._sets_table.selectionModel().selectionChanged.connect(self._on_set_selected)
        root.addWidget(self._sets_table, stretch=1)

        # ── Button bar ─────────────────────────────────────────────────────────
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(6)

        self._btn_import  = _make_btn("📂  Import",      "#4a7c2f")
        self._btn_rename  = _make_btn("✏  Rename",      "#2a5f80")
        self._btn_delete  = _make_btn("🗑  Delete",      "#9e2020")
        self._btn_reset   = _make_btn("↺  Reset Stats", "#5a7048")
        self._btn_open    = _make_btn("▶  Open Set",    "#8a6000")

        self._btn_open.setEnabled(False)

        for b in (self._btn_import, self._btn_rename, self._btn_delete, self._btn_reset):
            btn_bar.addWidget(b)

        btn_bar.addStretch()
        btn_bar.addWidget(self._btn_open)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_bar.addWidget(close_btn)

        root.addLayout(btn_bar)

        # Connections
        self._btn_import.clicked.connect(self._on_import)
        self._btn_rename.clicked.connect(self._on_rename)
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_reset.clicked.connect(self._on_reset_stats)
        self._btn_open.clicked.connect(self._on_open)

        self._update_buttons()

    # ── Data loading ───────────────────────────────────────────────────────────

    def _refresh_sets(self, select_id: int | None = None) -> None:
        """Reload the sets table from DB.

        If ``select_id`` is provided we try to select that set after
        populating.  When ``select_id`` is ``None`` and there are any
        rows we select the first one (which due to the ordering is the most
        recently played set).
        """
        self._sets: list[PuzzleSetRow] = self._db.list_sets()
        self._sets_table.setRowCount(len(self._sets))

        for row, s in enumerate(self._sets):
            pct_str = f"{s.pct_done:.0f}%"
            items = [
                s.name,
                str(s.total_puzzles),
                str(s.solved),
                str(s.failed),
                str(s.untried),
                pct_str,
                s.last_played_at or "—",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter
                    | (Qt.AlignmentFlag.AlignLeft if col == 0
                       else Qt.AlignmentFlag.AlignCenter)
                )
                if col == 2:   # solved green
                    item.setForeground(QColor("#81b64c"))
                elif col == 3: # failed red
                    item.setForeground(QColor("#e74c3c"))
                self._sets_table.setItem(row, col, item)

            # Restore selection
            if select_id is not None and s.id == select_id:
                self._sets_table.selectRow(row)

        # if nothing was selected and we have at least one row, pick the first
        if select_id is None and self._sets_table.rowCount() > 0:
            self._sets_table.selectRow(0)

        self._update_buttons()

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _on_set_selected(self) -> None:
        self._update_buttons()

    def _on_import(self) -> None:
        path, selected_filter = QFileDialog.getOpenFileName(
            self, "Import Puzzle Set", "",
            "Puzzle Files (*.pgn *.json);;PGN Files (*.pgn);;Lichess JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return

        import pathlib
        default_name = pathlib.Path(path).stem.replace("_", " ").replace("-", " ").title()
        name, ok = QInputDialog.getText(
            self, "Name this Puzzle Set",
            "Puzzle set name:",
            text=default_name,
        )
        if not ok or not name.strip():
            return

        ext = pathlib.Path(path).suffix.lower()
        try:
            if ext == ".json":
                new_id = self._db.import_san(name.strip(), path)
            else:
                new_id = self._db.import_pgn(name.strip(), path)
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return

        self._refresh_sets(select_id=new_id)

    def _on_rename(self) -> None:
        s = self._selected_set()
        if s is None:
            return
        name, ok = QInputDialog.getText(
            self, "Rename Puzzle Set", "New name:", text=s.name
        )
        if not ok or not name.strip():
            return
        self._db.rename_set(s.id, name.strip())
        self._refresh_sets(select_id=s.id)

    def _on_delete(self) -> None:
        s = self._selected_set()
        if s is None:
            return
        reply = QMessageBox.question(
            self,
            "Delete Puzzle Set",
            f'Delete "{s.name}" and all its stats?\n\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._db.delete_set(s.id)
        self._refresh_sets()

    def _on_reset_stats(self) -> None:
        s = self._selected_set()
        if s is None:
            return
        reply = QMessageBox.question(
            self,
            "Reset Stats",
            f'Reset all puzzle stats for "{s.name}"?\n\nSolve/fail counts will be cleared.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._db.reset_stats(s.id)
        self._refresh_sets(select_id=s.id)

    def _on_open(self) -> None:
        s = self._selected_set()
        if s is None:
            return
        self.selected_set_id = s.id
        self.accept()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _selected_set(self) -> PuzzleSetRow | None:
        rows = self._sets_table.selectedItems()
        if not rows:
            return None
        row = self._sets_table.currentRow()
        if 0 <= row < len(self._sets):
            return self._sets[row]
        return None

    def _update_buttons(self) -> None:
        has = self._selected_set() is not None
        self._btn_rename.setEnabled(has)
        self._btn_delete.setEnabled(has)
        self._btn_reset.setEnabled(has)
        self._btn_open.setEnabled(has)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_btn(text: str, colour: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {colour};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {colour}cc;
        }}
        QPushButton:disabled {{
            background-color: #354530;
            color: #6a8058;
        }}
        """
    )
    return btn

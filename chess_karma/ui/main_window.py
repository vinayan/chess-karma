"""
MainWindow – the top-level application window.

Layout
──────
┌──────────────────────────────┬──────────────────┐
│         BoardWidget          │ Panel (stacked)  │
│      (takes all space)       │ Train / Rush     │
└──────────────────────────────┴──────────────────┘

Modes
─────
  Train  – classic puzzle-by-puzzle practice (PuzzlePanel)
  Rush   – timed puzzle sprint with lives (RushPanel)

Flow (Train)
────────────
1. User selects a set from the landing page (File → Puzzle Sets).
2. PuzzleManager loads the games from the database; the first puzzle is displayed.
3. Player clicks to move; MainWindow validates via PuzzleManager.
4. Correct move  → auto-play opponent → next player turn.
5. Wrong move    → board NOT updated; status "Incorrect, try again."
6. Puzzle solved → celebrate; player can navigate to the next puzzle.

Flow (Rush)
───────────
1. PGN must be loaded first.  User picks mode via Puzzle Rush dialog.
2. RushManager shuffles puzzle order, starts timer.
3. Wrong move → lose 1 life; keep trying the same puzzle.
4. 3 lives lost OR time expires → session ends → result dialog.
5. Correct puzzle → score++, advance to next puzzle.
"""

from __future__ import annotations

import chess
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from chess_karma.core.engine import EngineManager
from chess_karma.core.database import Database
from chess_karma.core.leaderboard import Leaderboard
from chess_karma.core.puzzle_manager import PuzzleManager
from chess_karma.core.rush_manager import RushManager, RushMode
from chess_karma.core.sound import SoundManager
from chess_karma.ui.board_widget import BoardWidget
from chess_karma.ui.puzzle_panel import PuzzlePanel
from chess_karma.ui.puzzle_set_dialog import PuzzleSetDialog
from chess_karma.ui.rush_panel import RushPanel
from chess_karma.ui.rush_result_dialog import RushResultDialog
from chess_karma.ui.rush_start_dialog import RushStartDialog

# Delay (ms) before auto-playing the opponent move
_OPPONENT_DELAY = 600

# Delay (ms) before auto-advancing to the next puzzle after solving (train mode)
_AUTO_NEXT_DELAY = 1200

# Delay (ms) to show wrong move feedback before advancing (rush mode)
_RUSH_WRONG_DELAY  = 1200
# Delay (ms) before loading the next rush puzzle after current is solved
_RUSH_NEXT_DELAY   = 700

# Stacked-panel indices
_PANEL_TRAIN = 0
_PANEL_RUSH  = 1


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chess Karma – Puzzle Trainer")
        self.setMinimumSize(820, 580)
        self.resize(1060, 700)

        self._manager     = PuzzleManager()
        self._engine      = EngineManager()
        self._sound       = SoundManager()
        self._leaderboard = Leaderboard()
        self._db          = Database()

        # Rush session state (None when not in rush mode)
        self._rush: RushManager | None = None

        self._engine.start()

        self._build_ui()
        self._build_menu()
        self._build_status_bar()

        # show landing page on first run
        QTimer.singleShot(0, lambda: self._on_open_puzzle_sets(initial=True))

        # Timer for opponent auto-play (train and rush share this)
        self._opponent_timer = QTimer(self)
        self._opponent_timer.setSingleShot(True)
        self._opponent_timer.timeout.connect(self._auto_play_opponent)

        # Timer for advancing to the next rush puzzle after solve
        self._rush_next_timer = QTimer(self)
        self._rush_next_timer.setSingleShot(True)
        self._rush_next_timer.timeout.connect(self._rush_load_next)

        # Timer for advancing past a wrong rush move
        self._rush_wrong_timer = QTimer(self)
        self._rush_wrong_timer.setSingleShot(True)
        self._rush_wrong_timer.timeout.connect(self._rush_after_wrong)

        # 100 ms tick to refresh the rush timer display
        self._rush_tick_timer = QTimer(self)
        self._rush_tick_timer.setInterval(100)
        self._rush_tick_timer.timeout.connect(self._rush_tick)

        # Timer for auto-advancing to the next puzzle after solve (train mode)
        self._auto_next_timer = QTimer(self)
        self._auto_next_timer.setSingleShot(True)
        self._auto_next_timer.timeout.connect(self._on_next)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._board = BoardWidget()
        self._board.move_made.connect(self._on_player_move)
        layout.addWidget(self._board, stretch=1)

        # Stacked panel: index 0 = Train, index 1 = Rush
        self._panel_stack = QStackedWidget()
        self._panel_stack.setMaximumWidth(300)
        self._panel_stack.setMinimumWidth(240)
        layout.addWidget(self._panel_stack, stretch=0)

        # Train panel (always present at index 0)
        self._panel = PuzzlePanel()
        self._panel.hint_requested.connect(self._on_hint)
        self._panel.solution_requested.connect(self._on_show_solution)
        self._panel.reset_requested.connect(self._on_reset)
        self._panel.next_requested.connect(self._on_next)
        self._panel.prev_requested.connect(self._on_prev)
        self._panel.auto_next_changed.connect(self._on_auto_next_toggled)
        self._panel_stack.addWidget(self._panel)   # index 0

        # Rush panel placeholder – real widget inserted when rush starts
        self._rush_panel: RushPanel | None = None

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        # ── Train ─────────────────────────────────────────────────────────────
        puzzle_menu = menu_bar.addMenu("&Train")

        sets_action = QAction("📚  &Puzzles…", self)
        sets_action.setShortcut("Ctrl+Shift+O")
        sets_action.triggered.connect(self._on_open_puzzle_sets)
        puzzle_menu.addAction(sets_action)

        # ── View ─────────────────────────────────────────────────────────────
        view_menu = menu_bar.addMenu("&View")

        flip_action = QAction("&Flip Board", self)
        flip_action.setShortcut("F")
        flip_action.triggered.connect(self._flip_board)
        view_menu.addAction(flip_action)

        view_menu.addSeparator()

        self._mute_action = QAction("&Mute Sounds", self)
        self._mute_action.setCheckable(True)
        self._mute_action.setShortcut("M")
        self._mute_action.triggered.connect(self._toggle_mute)
        view_menu.addAction(self._mute_action)

        # ── Help ──────────────────────────────────────────────────────────────
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About Chess Karma", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        self._status_lbl = QLabel("Ready – select a puzzle set to begin.")
        bar.addWidget(self._status_lbl)
        engine_text = (
            "  ·  Engine: Stockfish ✓" if self._engine.available else "  ·  Engine: not found"
        )
        self._engine_lbl = QLabel(engine_text)
        bar.addPermanentWidget(self._engine_lbl)

    # ── PGN loading ────────────────────────────────────────────────────────────

    # the old PGN-loading mechanism has been retired; puzzle sets are now
    # used exclusively.  The method is kept here in case someone still
    # binds it (unlikely) but it does nothing.
    def _open_pgn(self) -> None:
        QMessageBox.information(
            self,
            "Deprecated",
            "Opening raw PGN files is no longer supported. Use Puzzle Sets."
        )

    def _on_open_puzzle_sets(self, initial: bool = False) -> None:
        """Show the puzzle‑sets browser and then the per‑set dashboard.

        When ``initial`` is True the call came from startup; cancelling will
        simply leave the window empty rather than loading anything.
        """
        if self._rush is not None:
            QMessageBox.warning(
                self, "Rush in Progress",
                "Please abort the current Puzzle Rush before switching puzzle sets."
            )
            return

        dlg = PuzzleSetDialog(self._db, parent=self)
        if dlg.exec() != PuzzleSetDialog.DialogCode.Accepted:
            return
        if dlg.selected_set_id is None:
            return

        # once the user has picked a set, show the dashboard for that set
        from chess_karma.ui.puzzle_set_dashboard import PuzzleSetDashboard, DashboardAction

        dash = PuzzleSetDashboard(self._db, dlg.selected_set_id, self._leaderboard, parent=self)
        if dash.exec() != PuzzleSetDashboard.DialogCode.Accepted:
            return
        action = dash.selected_action
        if action == DashboardAction.TRAIN_ALL:
            self._start_training(dlg.selected_set_id)
        elif action == DashboardAction.TRAIN_FAILED:
            self._start_training(dlg.selected_set_id, failed_only=True)
        elif action == DashboardAction.RUSH:
            # load set so manager has puzzles, then hand off to rush dialog
            self._load_set_from_db(dlg.selected_set_id)
            self._on_start_rush()
        # if CANCEL we do nothing

    def _load_set_from_db(self, set_id: int) -> None:
        """Load a DB puzzle set into the PuzzleManager and refresh the board."""
        try:
            count = self._manager.load_from_set(self._db, set_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error loading puzzle set", str(exc))
            return

        if count == 0:
            QMessageBox.warning(self, "Empty Set", "No puzzles found in this set.")
            return

        set_row = self._db.get_set(set_id)
        name = set_row.name if set_row else f"Set #{set_id}"
        self._status_lbl.setText(f"Loaded {count} puzzle(s) from set \u2018{name}\u2019")
        self._load_current_puzzle()

    def _start_training(self, set_id: int, failed_only: bool = False) -> None:
        """High-level helper invoked from the dashboard.

        ``failed_only`` will load only the puzzles whose last_result was
        'failed'; if there are none a message is shown instead.
        """
        if self._rush is not None:
            QMessageBox.warning(
                self, "Rush in Progress",
                "Please abort the current Puzzle Rush before starting training."
            )
            return

        try:
            if failed_only:
                count = self._manager.load_failed_from_set(self._db, set_id)
            else:
                count = self._manager.load_from_set(self._db, set_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error loading puzzle set", str(exc))
            return

        if count == 0:
            if failed_only:
                QMessageBox.information(
                    self, "No Failures",
                    "There are no failed puzzles to train – everything is solved!"
                )
            else:
                QMessageBox.warning(self, "Empty Set", "No puzzles found in this set.")
            return

        set_row = self._db.get_set(set_id)
        name = set_row.name if set_row else f"Set #{set_id}"
        suffix = " (failed only)" if failed_only else ""
        self._status_lbl.setText(f"Loaded {count} puzzle(s) from set \u2018{name}\u2019{suffix}")
        self._load_current_puzzle()

    # ═══════════════════════════════════════════════════════════════════════════
    # TRAIN MODE
    # ═══════════════════════════════════════════════════════════════════════════

    def _load_current_puzzle(self) -> None:
        """Load and display the current puzzle in Train mode."""
        if not self._manager.has_puzzles():
            return

        puzzle      = self._manager.get_current_puzzle()
        player_color = self._manager.get_player_color()

        self._board.set_board(self._manager.board, player_color)
        self._board.set_interactive(self._manager.is_player_turn())

        # Detect previous result from DB-backed set history
        prev_result: str | None = None
        if self._manager.active_set_id is not None and puzzle is not None:
            if self._manager.is_solved():
                prev_result = "solved"
            elif self._manager.is_failed():
                prev_result = "failed"

        self._panel.update_puzzle_info(
            index=self._manager.current_index,
            total=len(self._manager.puzzles),
            title=puzzle.title,
            white=puzzle.white,
            black=puzzle.black,
            player_color=player_color,
            previous_result=prev_result,
        )
        self._panel.set_status("Your turn – find the best move!", "info")
        self._panel.update_progress(
            self._manager.progress.total,
            self._manager.progress.solved,
            self._manager.progress.failed,
        )
        self._panel.set_controls_enabled_for_state(
            complete=self._manager.is_puzzle_complete(),
            is_player_turn=self._manager.is_player_turn(),
        )

    def _on_player_move(self, move: chess.Move) -> None:
        """Route player move to the correct mode handler."""
        if self._rush is not None:
            self._on_player_move_rush(move)
        else:
            self._on_player_move_train(move)

    def _on_player_move_train(self, move: chess.Move) -> None:
        if not self._manager.has_puzzles():
            return
        if not self._manager.is_player_turn():
            return

        board_before = self._manager.board.copy()
        is_correct, is_complete = self._manager.try_move(move)

        if is_correct:
            self._board.update_board(self._manager.board, last_move=move)
            self._play_move_sound(board_before, move, self._manager.board)

            if is_complete:
                self._on_puzzle_solved_train()
            else:
                self._board.set_interactive(False)
                self._panel.set_status("Correct! ✓  Waiting for opponent…", "success")
                self._opponent_timer.start(_OPPONENT_DELAY)
        else:
            self._board.update_board(self._manager.board, last_move=None)
            self._panel.set_status("✗  Incorrect – try again.", "error")
            self._manager._mark_failed()
            self._board.set_interactive(True)
            self._panel.update_progress(
                self._manager.progress.total,
                self._manager.progress.solved,
                self._manager.progress.failed,
            )

    def _auto_play_opponent(self) -> None:
        """Called by the timer after the player's correct move (both modes)."""
        next_idx = self._manager.current_move_index
        if next_idx >= len(self._manager.solution_moves):
            return

        board_before = self._manager.board.copy()
        opp_move     = self._manager.solution_moves[next_idx]

        applied = self._manager.apply_opponent_move()
        if applied is None:
            return

        self._play_move_sound(board_before, opp_move, self._manager.board)
        self._board.update_board(self._manager.board, last_move=applied)

        if self._manager.is_puzzle_complete():
            if self._rush is not None:
                self._on_puzzle_solved_rush()
            else:
                self._on_puzzle_solved_train()
        else:
            self._board.set_interactive(True)
            if self._rush is not None:
                self._rush_panel.set_status("Your turn!", "info")  # type: ignore[union-attr]
            else:
                self._panel.set_status("Your turn – find the best move!", "info")
                self._panel.set_controls_enabled_for_state(
                    complete=False,
                    is_player_turn=True,
                )

    def _on_puzzle_solved_train(self) -> None:
        self._board.set_interactive(False)
        self._panel.set_controls_enabled_for_state(complete=True, is_player_turn=False)
        self._panel.update_progress(
            self._manager.progress.total,
            self._manager.progress.solved,
            self._manager.progress.failed,
        )
        has_next = self._manager.current_index < len(self._manager.puzzles) - 1
        if self._panel.is_auto_next and has_next:
            self._panel.set_status("🎉  Puzzle solved! Next puzzle in 1 s…", "success")
            self._auto_next_timer.start(_AUTO_NEXT_DELAY)
        else:
            self._panel.set_status("🎉  Puzzle solved!", "success")

    def _play_move_sound(
        self,
        board_before: chess.Board,
        move: chess.Move,
        board_after: chess.Board,
    ) -> None:
        if board_after.is_check():
            self._sound.play_check()
        elif board_before.is_castling(move):
            self._sound.play_castle()
        elif board_before.is_capture(move):
            self._sound.play_capture()
        else:
            self._sound.play_move()

    # ── Train control handlers ─────────────────────────────────────────────────

    def _on_hint(self) -> None:
        if self._rush is not None or not self._manager.has_puzzles():
            return
        hint = self._manager.get_hint()
        if hint:
            self._board.set_hint(hint)
            self._panel.set_status("Hint shown – green arrow indicates the move.", "info")

    def _on_show_solution(self) -> None:
        if self._rush is not None or not self._manager.has_puzzles():
            return
        if self._manager.is_puzzle_complete():
            return

        remaining = self._manager.solution_moves[self._manager.current_move_index:]
        self._manager.show_solution()
        self._board.update_board(self._manager.board)
        self._board.set_solution_arrows(remaining)
        self._board.set_interactive(False)
        self._panel.set_status("Solution shown.", "info")
        self._panel.update_progress(
            self._manager.progress.total,
            self._manager.progress.solved,
            self._manager.progress.failed,
        )
        self._panel.set_controls_enabled_for_state(complete=True, is_player_turn=False)

    def _on_reset(self) -> None:
        if self._rush is not None or not self._manager.has_puzzles():
            return
        self._opponent_timer.stop()
        self._auto_next_timer.stop()
        self._manager.reset_puzzle()
        self._load_current_puzzle()

    def _on_auto_next_toggled(self, enabled: bool) -> None:
        """Cancel any pending auto-advance when the user turns the toggle off."""
        if not enabled:
            self._auto_next_timer.stop()

    def _on_next(self) -> None:
        if self._rush is not None:
            return
        self._opponent_timer.stop()
        self._auto_next_timer.stop()
        if self._manager.next_puzzle():
            self._load_current_puzzle()

    def _on_prev(self) -> None:
        if self._rush is not None:
            return
        self._opponent_timer.stop()
        self._auto_next_timer.stop()
        if self._manager.prev_puzzle():
            self._load_current_puzzle()

    # ═══════════════════════════════════════════════════════════════════════════
    # PUZZLE RUSH MODE
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_start_rush(self) -> None:
        """Menu action: open mode-selection dialog and start rush."""
        if not self._manager.has_puzzles():
            QMessageBox.information(
                self,
                "No Puzzles Loaded",
                "Please select a puzzle set before starting Puzzle Rush.",
            )
            return

        dlg = RushStartDialog(self._leaderboard, parent=self)
        if dlg.exec() != RushStartDialog.DialogCode.Accepted:
            return
        if dlg.selected_mode is None:
            return

        self._start_rush(dlg.selected_mode)

    def _start_rush(self, mode: RushMode) -> None:
        """Initialise and begin a Puzzle Rush session."""
        # Stop any in-progress train timers
        self._opponent_timer.stop()

        # Build rush state
        self._rush = RushManager(mode, len(self._manager.puzzles))

        # Build and insert rush panel into the stack at index 1
        if self._panel_stack.count() > 1:
            old = self._panel_stack.widget(1)
            self._panel_stack.removeWidget(old)
            old.deleteLater()

        self._rush_panel = RushPanel(mode, parent=self)
        self._rush_panel.abort_requested.connect(self._on_abort_rush)
        self._panel_stack.insertWidget(_PANEL_RUSH, self._rush_panel)
        self._panel_stack.setCurrentIndex(_PANEL_RUSH)

        # Menu state
        self._rush_action.setEnabled(False)
        self._rush_abort_action.setEnabled(True)

        # Load first puzzle
        self._rush_load_next()

        # Start the session clock AFTER the first puzzle is on screen
        self._rush.start()
        self._rush_tick_timer.start()

        self._status_lbl.setText(f"⚡  Puzzle Rush – {mode.value} – GO!")

    def _rush_load_next(self) -> None:
        """Load the next puzzle in the rush sequence."""
        if self._rush is None:
            return

        idx = self._rush.next_puzzle_index()
        if idx is None:
            # All puzzles exhausted – treat as a win
            self._end_rush("complete")
            return

        self._manager.goto_puzzle(idx)
        puzzle       = self._manager.get_current_puzzle()
        player_color = self._manager.get_player_color()

        self._board.set_board(self._manager.board, player_color)
        self._board.set_interactive(self._manager.is_player_turn())

        self._rush_panel.set_status("Your turn!", "info")  # type: ignore[union-attr]
        self._rush_panel.update_timer(            # type: ignore[union-attr]
            self._rush.format_timer(),
            self._rush.remaining_s(),
        )

    def _on_player_move_rush(self, move: chess.Move) -> None:
        """Handle a player move during a Puzzle Rush session."""
        if self._rush is None or self._rush.is_over():
            return
        if not self._manager.is_player_turn():
            return

        board_before          = self._manager.board.copy()
        is_correct, is_complete = self._manager.try_move(move)

        if is_correct:
            self._board.update_board(self._manager.board, last_move=move)
            self._play_move_sound(board_before, move, self._manager.board)

            if is_complete:
                self._on_puzzle_solved_rush()
            else:
                self._board.set_interactive(False)
                self._rush_panel.set_status("Correct! ✓", "success")  # type: ignore[union-attr]
                self._opponent_timer.start(_OPPONENT_DELAY)
        else:
            # Wrong move – lose a life, show feedback, then move to next puzzle
            self._board.update_board(self._manager.board, last_move=None)
            session_over = self._rush.record_failure()
            self._rush_panel.update_lives(self._rush.lives_left)    # type: ignore[union-attr]
            self._board.set_interactive(False)

            if session_over:
                self._rush_panel.set_status("❌  Three mistakes – game over!", "error")  # type: ignore[union-attr]
            else:
                remaining_lives = self._rush.lives_left
                self._rush_panel.set_status(   # type: ignore[union-attr]
                    f"✗  Wrong!  {remaining_lives} life{'s' if remaining_lives != 1 else ''} left.",
                    "error",
                )
            # Always pause briefly, then either end or advance
            self._rush_wrong_timer.start(_RUSH_WRONG_DELAY)

    def _rush_after_wrong(self) -> None:
        """Called after the brief pause following a wrong move in rush mode."""
        if self._rush is None:
            return
        if self._rush.is_over():
            self._end_rush("failures")
        else:
            self._rush_load_next()

    def _on_puzzle_solved_rush(self) -> None:
        """Puzzle complete in rush mode – increment score, queue next puzzle."""
        if self._rush is None:
            return
        self._rush.record_correct()
        self._rush_panel.update_score(self._rush.score)   # type: ignore[union-attr]
        self._rush_panel.set_status("🎉  Solved!", "success")   # type: ignore[union-attr]
        self._board.set_interactive(False)

        if self._rush.is_time_up():
            self._end_rush("timeout")
        else:
            self._rush_next_timer.start(_RUSH_NEXT_DELAY)

    def _rush_tick(self) -> None:
        """100 ms heartbeat: refresh timer display and detect timeout."""
        if self._rush is None:
            self._rush_tick_timer.stop()
            return

        self._rush_panel.update_timer(   # type: ignore[union-attr]
            self._rush.format_timer(),
            self._rush.remaining_s(),
        )

        if self._rush.is_time_up():
            self._rush_tick_timer.stop()
            self._end_rush("timeout")

    def _on_abort_rush(self) -> None:
        self._end_rush("aborted")

    def _end_rush(self, reason: str) -> None:
        """Finalise the rush session, save score, show result dialog."""
        if self._rush is None:
            return

        self._rush_tick_timer.stop()
        self._opponent_timer.stop()
        self._rush_next_timer.stop()
        self._rush_wrong_timer.stop()
        self._board.set_interactive(False)

        rush = self._rush
        rush.end()
        self._rush = None   # clear before dialog to avoid re-entrancy

        # Save to leaderboard and history (don't save aborted runs with score 0)
        rank = 0
        if reason != "aborted" or rush.score > 0:
            rank = self._leaderboard.submit(
                rush.mode,
                rush.score,
                rush.elapsed_s(),
            )
            self._db.record_rush_session(rush.mode.value, rush.score, rush.elapsed_s(), self._manager.active_set_id)

        # Show result dialog
        dlg = RushResultDialog(rush, self._leaderboard, rank, reason, parent=self)
        dlg.exec()

        # Restore UI
        self._panel_stack.setCurrentIndex(_PANEL_TRAIN)
        self._rush_action.setEnabled(True)
        self._rush_abort_action.setEnabled(False)
        self._status_lbl.setText("Rush ended – back to Training mode.")

        if dlg.play_again:
            self._on_start_rush()
        else:
            # Reload first puzzle so train panel shows something sensible
            if self._manager.has_puzzles():
                self._manager.goto_puzzle(0)
                self._load_current_puzzle()

    # ═══════════════════════════════════════════════════════════════════════════
    # SHARED / VIEW HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _flip_board(self) -> None:
        self._board._flipped = not self._board._flipped
        self._board._rebuild_svg()

    def _toggle_mute(self, checked: bool) -> None:
        self._sound.enabled = not checked
        state = "muted" if checked else "on"
        self._status_lbl.setText(f"Sound {state}.")

    # ── About ──────────────────────────────────────────────────────────────────

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Chess Karma",
            "<h2>Chess Karma</h2>"
            "<p>A chess puzzle trainer built with PyQt6 and python-chess.</p>"
            "<p>Licensed under the <b>GNU GPL v3</b>.</p>"
            "<p>Dependencies: PyQt6 · python-chess · (optional) Stockfish</p>",
        )

    # ── Window close ──────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        self._rush_tick_timer.stop()
        self._engine.stop()
        super().closeEvent(event)

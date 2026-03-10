"""
Puzzle Manager - loads and manages chess puzzles from PGN files.
Tracks solution progress, validates player moves, and handles puzzle navigation.
"""

import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import chess
import chess.pgn

if TYPE_CHECKING:
    from chess_karma.core.database import Database


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class PuzzleProgress:
    total: int = 0
    solved: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass
class Puzzle:
    game: chess.pgn.Game
    title: str
    index: int
    white: str = "?"
    black: str = "?"
    event: str = ""
    fen: str = ""
    db_id: Optional[int] = None      # puzzle.id in puzzle_stats table (None = not DB-backed)


# ── Puzzle Manager ─────────────────────────────────────────────────────────────

class PuzzleManager:
    """
    Loads puzzles from a PGN file and manages the puzzle-solving session.

    A PGN game is treated as a puzzle where:
      - The starting position is given by the FEN header (or standard start).
      - The mainline moves define the full solution.
      - Moves at even indices (0, 2, 4 …) belong to the player.
      - Moves at odd indices (1, 3, 5 …) are opponent auto-play responses.

    Some PGNs prepend "setup" moves before the actual puzzle; this manager
    applies them automatically, then waits for the player's first move.
    """

    def __init__(self):
        self.puzzles: list[Puzzle] = []
        self.current_index: int = 0
        self.progress: PuzzleProgress = PuzzleProgress()

        # Live board and solution for the current puzzle
        self.board: chess.Board = chess.Board()
        self.solution_moves: list[chess.Move] = []
        self.current_move_index: int = 0

        # Track which puzzles have been solved/failed this session
        self._solved_set: set[int] = set()
        self._failed_set: set[int] = set()

        # Optional DB integration – set by load_from_set()
        self._db: Optional["Database"] = None
        self.active_set_id: Optional[int] = None

    # ── Loading ────────────────────────────────────────────────────────────────

    def load_from_set(self, db: "Database", set_id: int) -> int:
        """
        Load puzzles from a DB puzzle set.
        Restores prior solved/failed state from puzzle_stats.
        Returns the number of puzzles loaded.
        """
        self.puzzles.clear()
        self._solved_set.clear()
        self._failed_set.clear()
        self.progress = PuzzleProgress()
        self._db = db
        self.active_set_id = set_id

        rows = db.load_puzzles(set_id)
        if not rows:
            return 0

        for row in rows:
            game = chess.pgn.read_game(io.StringIO(row.pgn_text))
            if game is None:
                continue
            puzzle = Puzzle(
                game=game,
                title=row.title,
                index=row.index_in_set,
                white=row.white,
                black=row.black,
                event=row.event,
                fen=row.fen,
                db_id=row.id,
            )
            self.puzzles.append(puzzle)
            # Restore prior results into in-memory sets
            if row.last_result == "solved":
                self._solved_set.add(row.index_in_set)
            elif row.last_result == "failed":
                self._failed_set.add(row.index_in_set)

        self.progress.total  = len(self.puzzles)
        self.progress.solved = len(self._solved_set)
        self.progress.failed = len(self._failed_set)

        if self.puzzles:
            self.current_index = self._smart_start_index()
            self._setup_current_puzzle()
            db.touch_set(set_id)

        return len(self.puzzles)

    def load_failed_from_set(self, db: "Database", set_id: int) -> int:
        """
        Load only the puzzles that have previously been marked as failed
        for the given set.  Returns the number of puzzles loaded.  If no
        puzzles have been failed yet the result will be 0.
        """
        count = self.load_from_set(db, set_id)
        if count == 0:
            return 0
        # filter the list in-place
        failed_indexes = self._failed_set.copy()
        self.puzzles = [p for p in self.puzzles if p.index in failed_indexes]
        self.progress.total = len(self.puzzles)
        # reset progress since we're starting a new session with the subset
        self.progress.solved = 0
        self.progress.failed = 0
        self._solved_set.clear()
        self._failed_set.clear()
        if self.puzzles:
            self.current_index = 0
            self._setup_current_puzzle()
            db.touch_set(set_id)
        return len(self.puzzles)

    def load_pgn(self, filepath: str) -> int:
        """
        Load all games from a PGN file as puzzles.
        Returns the number of puzzles loaded.
        """
        self.puzzles.clear()
        self._solved_set.clear()
        self._failed_set.clear()
        self.progress = PuzzleProgress()

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        pgn_io = io.StringIO(content)
        index = 0
        while True:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                break
            headers = game.headers
            title = headers.get("Event", f"Puzzle {index + 1}")
            puzzle = Puzzle(
                game=game,
                title=title,
                index=index,
                white=headers.get("White", "?"),
                black=headers.get("Black", "?"),
                event=headers.get("Event", ""),
                fen=headers.get("FEN", ""),
            )
            self.puzzles.append(puzzle)
            index += 1

        self.progress.total = len(self.puzzles)

        if self.puzzles:
            self.current_index = 0
            self._setup_current_puzzle()

        # Raw PGN load is not DB-backed
        self._db = None
        self.active_set_id = None

        return len(self.puzzles)

    # ── Puzzle life-cycle ──────────────────────────────────────────────────────

    def _smart_start_index(self) -> int:
        """
        Return the index to start at when opening a DB-backed set:
          1. First failed puzzle  (should be retried immediately).
          2. First untried puzzle (neither solved nor failed).
          3. Fall back to 0 (all puzzles have been attempted).
        """
        first_untried: int | None = None
        for i, p in enumerate(self.puzzles):
            idx = p.index
            if idx in self._failed_set:
                return i          # highest priority: failed puzzle
            if first_untried is None and idx not in self._solved_set:
                first_untried = i
        return first_untried if first_untried is not None else 0

    def _setup_current_puzzle(self) -> None:
        """Initialise board and solution for the current puzzle index."""
        if not self.puzzles:
            return
        puzzle = self.puzzles[self.current_index]
        self.board = puzzle.game.board()
        self.solution_moves = list(puzzle.game.mainline_moves())
        self.current_move_index = 0

    def reset_puzzle(self) -> None:
        """Reset the current puzzle back to its starting position."""
        self._setup_current_puzzle()

    def next_puzzle(self) -> bool:
        """Advance to the next puzzle. Returns False if already at the last."""
        if self.current_index < len(self.puzzles) - 1:
            self.current_index += 1
            self._setup_current_puzzle()
            return True
        return False

    def prev_puzzle(self) -> bool:
        """Go back to the previous puzzle. Returns False if at the first."""
        if self.current_index > 0:
            self.current_index -= 1
            self._setup_current_puzzle()
            return True
        return False

    def goto_puzzle(self, index: int) -> bool:
        """Jump to an arbitrary puzzle index."""
        if 0 <= index < len(self.puzzles):
            self.current_index = index
            self._setup_current_puzzle()
            return True
        return False

    # ── Move logic ─────────────────────────────────────────────────────────────

    def try_move(self, move: chess.Move) -> tuple[bool, bool]:
        """
        Attempt a player move against the expected solution.

        Returns:
            (is_correct, is_complete)
            is_correct  – True when the move matches the solution.
            is_complete – True when the puzzle is fully solved.
        """
        if self.current_move_index >= len(self.solution_moves):
            return False, True

        expected = self.solution_moves[self.current_move_index]

        if move == expected:
            self.board.push(move)
            self.current_move_index += 1
            complete = self.current_move_index >= len(self.solution_moves)
            if complete:
                self._mark_solved()
            return True, complete
        else:
            self._mark_failed()
            return False, False

    def apply_opponent_move(self) -> Optional[chess.Move]:
        """
        Push the next solution move as the opponent's response.
        Returns the move, or None if there are no more moves.
        """
        if self.current_move_index >= len(self.solution_moves):
            return None
        move = self.solution_moves[self.current_move_index]
        self.board.push(move)
        self.current_move_index += 1
        return move

    def get_hint(self) -> Optional[chess.Move]:
        """Return the next correct player move without applying it."""
        if self.is_player_turn() and self.current_move_index < len(self.solution_moves):
            return self.solution_moves[self.current_move_index]
        return None

    def show_solution(self) -> None:
        """Apply all remaining solution moves to the board."""
        while self.current_move_index < len(self.solution_moves):
            self.board.push(self.solution_moves[self.current_move_index])
            self.current_move_index += 1

    # ── State queries ──────────────────────────────────────────────────────────

    def get_current_puzzle(self) -> Optional[Puzzle]:
        if not self.puzzles:
            return None
        return self.puzzles[self.current_index]

    def get_player_color(self) -> chess.Color:
        """The side the human player controls for the current puzzle."""
        return self.board.turn

    def is_puzzle_complete(self) -> bool:
        return self.current_move_index >= len(self.solution_moves)

    def is_player_turn(self) -> bool:
        """True when it is the player's turn (even move index, puzzle not done)."""
        if not self.solution_moves:
            return False
        return self.current_move_index % 2 == 0 and not self.is_puzzle_complete()

    def is_solved(self) -> bool:
        return self.current_index in self._solved_set

    def is_failed(self) -> bool:
        return self.current_index in self._failed_set

    def has_puzzles(self) -> bool:
        return bool(self.puzzles)

    # ── Progress helpers ───────────────────────────────────────────────────────

    def _mark_solved(self) -> None:
        idx = self.current_index
        if idx not in self._solved_set:
            self._solved_set.add(idx)
            self._failed_set.discard(idx)
            self.progress.solved = len(self._solved_set)
            self.progress.failed = len(self._failed_set)
        # Always record in DB (cumulative solved_count)
        puzzle = self.puzzles[idx] if idx < len(self.puzzles) else None
        if self._db is not None and puzzle is not None and puzzle.db_id is not None:
            try:
                self._db.record_solved(puzzle.db_id)
            except Exception:
                pass

    def _mark_failed(self) -> None:
        idx = self.current_index
        already_solved = idx in self._solved_set
        if not already_solved and idx not in self._failed_set:
            self._failed_set.add(idx)
            self.progress.failed = len(self._failed_set)
        # Always record in DB (cumulative failed_count)
        puzzle = self.puzzles[idx] if idx < len(self.puzzles) else None
        if self._db is not None and puzzle is not None and puzzle.db_id is not None:
            try:
                self._db.record_failed(puzzle.db_id)
            except Exception:
                pass

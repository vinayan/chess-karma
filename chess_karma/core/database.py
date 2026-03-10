"""
Database – SQLite-backed persistence for Chess Karma puzzle sets and stats.

Uses the Python standard-library ``sqlite3`` module only – no extra deps.

Schema
──────
  puzzle_sets   – one row per named collection imported from a PGN file
  puzzles       – one row per puzzle within a set (stores the PGN text)
  puzzle_stats  – per-puzzle result history (solved/failed counts)

The database file is stored at  ~/chess_karma.db  (next to the scores file).
"""

from __future__ import annotations

import io
import json
import pathlib
import shutil
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

import chess
import chess.pgn

_DB_PATH = pathlib.Path.home() / "chess_karma.db"


def _bundled_blank_db() -> Optional[pathlib.Path]:
    """Return the blank-schema DB bundled with the installer, or None."""
    # PyInstaller extracts data files to sys._MEIPASS at runtime
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = pathlib.Path(base) / "chess_karma_blank.db"
        if p.exists():
            return p
    return None

_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS puzzle_sets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    pgn_path        TEXT,
    total_puzzles   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL,
    last_played_at  TEXT
);

CREATE TABLE IF NOT EXISTS puzzles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id          INTEGER NOT NULL REFERENCES puzzle_sets(id) ON DELETE CASCADE,
    index_in_set    INTEGER NOT NULL,
    title           TEXT,
    white           TEXT,
    black           TEXT,
    event           TEXT,
    fen             TEXT,
    pgn_text        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS puzzle_stats (
    puzzle_id       INTEGER PRIMARY KEY REFERENCES puzzles(id) ON DELETE CASCADE,
    solved_count    INTEGER NOT NULL DEFAULT 0,
    failed_count    INTEGER NOT NULL DEFAULT 0,
    last_result     TEXT,
    last_played_at  TEXT
);

CREATE TABLE IF NOT EXISTS rush_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mode        TEXT    NOT NULL,
    score       INTEGER NOT NULL,
    elapsed_s   REAL    NOT NULL,
    played_at   TEXT    NOT NULL,
    set_id      INTEGER REFERENCES puzzle_sets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_puzzles_set    ON puzzles(set_id, index_in_set);
CREATE INDEX IF NOT EXISTS idx_stats_puzzle   ON puzzle_stats(puzzle_id);
CREATE INDEX IF NOT EXISTS idx_rush_mode_date ON rush_sessions(mode, played_at);
"""


# ── Data-transfer objects ──────────────────────────────────────────────────────

@dataclass
class PuzzleSetRow:
    id: int
    name: str
    pgn_path: Optional[str]
    total_puzzles: int
    created_at: str
    last_played_at: Optional[str]
    # Aggregated from puzzle_stats:
    solved: int = 0
    failed: int = 0

    @property
    def untried(self) -> int:
        return max(0, self.total_puzzles - self.solved - self.failed)

    @property
    def pct_done(self) -> float:
        if self.total_puzzles == 0:
            return 0.0
        return round(100.0 * (self.solved + self.failed) / self.total_puzzles, 1)


@dataclass
class PuzzleRow:
    id: int
    set_id: int
    index_in_set: int
    title: str
    white: str
    black: str
    event: str
    fen: str
    pgn_text: str
    # From puzzle_stats (None means never played):
    solved_count: int = 0
    failed_count: int = 0
    last_result: Optional[str] = None
    last_played_at: Optional[str] = None


# ── Database class ─────────────────────────────────────────────────────────────

class Database:
    """
    Thin wrapper around sqlite3.  All public methods open a connection,
    apply PRAGMA foreign_keys=ON, and commit/rollback automatically.
    Thread-safety: not assumed – call only from the UI thread.
    """

    def __init__(self, path: pathlib.Path = _DB_PATH) -> None:
        self._path = path
        if not path.exists():
            blank = _bundled_blank_db()
            if blank:
                shutil.copy2(blank, path)
        self._init_schema()

    # ── Life-cycle ──────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.executescript(_DDL)
            # Migrate existing databases: add set_id to rush_sessions if absent
            cols = {row[1] for row in con.execute("PRAGMA table_info(rush_sessions)").fetchall()}
            if "set_id" not in cols:
                con.execute(
                    "ALTER TABLE rush_sessions ADD COLUMN set_id INTEGER REFERENCES puzzle_sets(id) ON DELETE CASCADE"
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self._path)
        con.execute("PRAGMA foreign_keys = ON")
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    # ── Puzzle-set CRUD ─────────────────────────────────────────────────────────

    def import_pgn(self, name: str, pgn_path: str) -> int:
        """
        Parse a PGN file and store every game as a puzzle in a new set.
        Returns the new set's id.
        Raises ValueError if the file contains no games.
        """
        with open(pgn_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        pgn_io = io.StringIO(content)
        games: list[tuple] = []   # (index, title, white, black, event, fen, pgn_text)
        index = 0
        while True:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                break
            h = game.headers
            title = h.get("Event", f"Puzzle {index + 1}")
            white = h.get("White", "?")
            black = h.get("Black", "?")
            event = h.get("Event", "")
            fen   = h.get("FEN", "")
            # Serialise back to PGN text for storage
            exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
            pgn_text = game.accept(exporter)
            games.append((index, title, white, black, event, fen, pgn_text))
            index += 1

        if not games:
            raise ValueError("No games found in the PGN file.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO puzzle_sets (name, pgn_path, total_puzzles, created_at)"
                " VALUES (?, ?, ?, ?)",
                (name, pgn_path, len(games), now),
            )
            set_id = cur.lastrowid
            con.executemany(
                "INSERT INTO puzzles (set_id, index_in_set, title, white, black, event, fen, pgn_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (set_id, idx, title, white, black, event, fen, pgn_text)
                    for (idx, title, white, black, event, fen, pgn_text) in games
                ],
            )
        return set_id

    def import_san(self, name: str, san_path: str) -> int:
        """
        Parse a Lichess JSON puzzle file and store every puzzle in a new set.
        Returns the new set's id.

        Expected JSON format – a list of objects, each with:
            FEN       : starting position
            MovesSAN  : space-separated SAN solution moves
            Themes    : (optional) space-separated theme tags used as title

        Example entry:
            {
              "FEN": "6k1/pp5p/2rp2p1/4rbB1/8/8/PP1K1PPP/3RR3 b - - 1 21",
              "MovesSAN": "Rc2#",
              "Themes": "endgame mate mateIn1 oneMove"
            }

        Raises ValueError if the file contains no valid puzzles.
        """
        with open(san_path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Expected a JSON array at the top level.")

        games: list[tuple] = []
        for i, entry in enumerate(data):
            if not isinstance(entry, dict):
                continue
            fen       = (entry.get("FEN") or "").strip()
            moves_str = (entry.get("MovesSAN") or "").strip()
            themes    = (entry.get("Themes") or "").strip()
            if not fen or not moves_str:
                continue

            title = themes or f"Puzzle {i + 1}"

            try:
                board = chess.Board(fen)
            except Exception:
                continue

            game = chess.pgn.Game()
            game.setup(board)
            game.headers["FEN"]   = fen
            game.headers["Event"] = title
            game.headers["White"] = "?"
            game.headers["Black"] = "?"

            node = game
            valid = True
            for san in moves_str.split():
                try:
                    move = board.parse_san(san)
                    node = node.add_variation(move)
                    board.push(move)
                except Exception:
                    valid = False
                    break

            if not valid or node is game:
                continue

            exporter = chess.pgn.StringExporter(
                headers=True, variations=False, comments=False
            )
            pgn_text = game.accept(exporter)
            games.append((len(games), title, "?", "?", title, fen, pgn_text))

        if not games:
            raise ValueError("No valid puzzles found in the JSON file.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO puzzle_sets (name, pgn_path, total_puzzles, created_at)"
                " VALUES (?, ?, ?, ?)",
                (name, san_path, len(games), now),
            )
            set_id = cur.lastrowid
            con.executemany(
                "INSERT INTO puzzles (set_id, index_in_set, title, white, black, event, fen, pgn_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (set_id, idx, title, white, black, event, fen, pgn_text)
                    for (idx, title, white, black, event, fen, pgn_text) in games
                ],
            )
        return set_id

    def create_empty_set(self, name: str) -> int:
        """Create an empty puzzle set with no puzzles. Returns the new set id."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO puzzle_sets (name, pgn_path, total_puzzles, created_at)"
                " VALUES (?, NULL, 0, ?)",
                (name, now),
            )
            return cur.lastrowid

    def add_puzzle(
        self,
        set_id: int,
        pgn_text: str,
        title: str = "",
        white: str = "?",
        black: str = "?",
        event: str = "",
        fen: str = "",
    ) -> int:
        """
        Append a single puzzle to an existing set.
        Returns the new puzzle's id.
        The set's total_puzzles counter is incremented automatically.
        """
        with self._connect() as con:
            index_row = con.execute(
                "SELECT COALESCE(MAX(index_in_set) + 1, 0) AS next_idx"
                " FROM puzzles WHERE set_id = ?",
                (set_id,),
            ).fetchone()
            next_idx = index_row["next_idx"]

            cur = con.execute(
                "INSERT INTO puzzles (set_id, index_in_set, title, white, black, event, fen, pgn_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (set_id, next_idx, title, white, black, event, fen, pgn_text),
            )
            puzzle_id = cur.lastrowid
            con.execute(
                "UPDATE puzzle_sets SET total_puzzles = total_puzzles + 1 WHERE id = ?",
                (set_id,),
            )
        return puzzle_id

    def remove_puzzle(self, puzzle_id: int) -> None:
        """Delete a single puzzle and decrement the parent set's total_puzzles."""
        with self._connect() as con:
            row = con.execute(
                "SELECT set_id FROM puzzles WHERE id = ?", (puzzle_id,)
            ).fetchone()
            if row is None:
                return
            set_id = row["set_id"]
            con.execute("DELETE FROM puzzles WHERE id = ?", (puzzle_id,))
            con.execute(
                "UPDATE puzzle_sets SET total_puzzles = MAX(0, total_puzzles - 1) WHERE id = ?",
                (set_id,),
            )

    def list_sets(self) -> list[PuzzleSetRow]:
        """Return all puzzle sets with aggregated solved/failed counts."""
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT
                    ps.id,
                    ps.name,
                    ps.pgn_path,
                    ps.total_puzzles,
                    ps.created_at,
                    ps.last_played_at,
                    COUNT(CASE WHEN st.last_result = 'solved' THEN 1 END) AS solved,
                    COUNT(CASE WHEN st.last_result = 'failed' THEN 1 END) AS failed
                FROM puzzle_sets ps
                LEFT JOIN puzzles p  ON p.set_id = ps.id
                LEFT JOIN puzzle_stats st ON st.puzzle_id = p.id
                GROUP BY ps.id
                ORDER BY ps.created_at DESC
                """
            ).fetchall()
        return [
            PuzzleSetRow(
                id=r["id"],
                name=r["name"],
                pgn_path=r["pgn_path"],
                total_puzzles=r["total_puzzles"],
                created_at=r["created_at"],
                last_played_at=r["last_played_at"],
                solved=r["solved"],
                failed=r["failed"],
            )
            for r in rows
        ]

    def get_set(self, set_id: int) -> Optional[PuzzleSetRow]:
        sets = [s for s in self.list_sets() if s.id == set_id]
        return sets[0] if sets else None

    def rename_set(self, set_id: int, new_name: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE puzzle_sets SET name = ? WHERE id = ?",
                (new_name, set_id),
            )

    def delete_set(self, set_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM puzzle_sets WHERE id = ?", (set_id,))

    def touch_set(self, set_id: int) -> None:
        """Update last_played_at timestamp."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as con:
            con.execute(
                "UPDATE puzzle_sets SET last_played_at = ? WHERE id = ?",
                (now, set_id),
            )

    # ── Puzzle loading ──────────────────────────────────────────────────────────

    def load_puzzles(self, set_id: int) -> list[PuzzleRow]:
        """
        Return all puzzles in the set (with latest stats) ordered by index.
        """
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT
                    p.id, p.set_id, p.index_in_set,
                    p.title, p.white, p.black, p.event, p.fen, p.pgn_text,
                    COALESCE(st.solved_count, 0)  AS solved_count,
                    COALESCE(st.failed_count, 0)  AS failed_count,
                    st.last_result,
                    st.last_played_at
                FROM puzzles p
                LEFT JOIN puzzle_stats st ON st.puzzle_id = p.id
                WHERE p.set_id = ?
                ORDER BY p.index_in_set
                """,
                (set_id,),
            ).fetchall()
        return [
            PuzzleRow(
                id=r["id"],
                set_id=r["set_id"],
                index_in_set=r["index_in_set"],
                title=r["title"] or "",
                white=r["white"] or "?",
                black=r["black"] or "?",
                event=r["event"] or "",
                fen=r["fen"] or "",
                pgn_text=r["pgn_text"],
                solved_count=r["solved_count"],
                failed_count=r["failed_count"],
                last_result=r["last_result"],
                last_played_at=r["last_played_at"],
            )
            for r in rows
        ]

    # ── Stats recording ─────────────────────────────────────────────────────────

    def record_solved(self, puzzle_id: int) -> None:
        """Increment solved_count and set last_result = 'solved'."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO puzzle_stats (puzzle_id, solved_count, failed_count, last_result, last_played_at)
                VALUES (?, 1, 0, 'solved', ?)
                ON CONFLICT(puzzle_id) DO UPDATE SET
                    solved_count   = solved_count + 1,
                    last_result    = 'solved',
                    last_played_at = excluded.last_played_at
                """,
                (puzzle_id, now),
            )

    def record_failed(self, puzzle_id: int) -> None:
        """Increment failed_count; only set last_result='failed' if not already solved this session."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO puzzle_stats (puzzle_id, solved_count, failed_count, last_result, last_played_at)
                VALUES (?, 0, 1, 'failed', ?)
                ON CONFLICT(puzzle_id) DO UPDATE SET
                    failed_count   = failed_count + 1,
                    last_result    = CASE WHEN last_result = 'solved' THEN 'solved' ELSE 'failed' END,
                    last_played_at = excluded.last_played_at
                """,
                (puzzle_id, now),
            )

    def reset_stats(self, set_id: int) -> None:
        """Wipe all puzzle_stats and rush session rows for a set (allow starting fresh)."""
        with self._connect() as con:
            con.execute(
                """
                DELETE FROM puzzle_stats
                WHERE puzzle_id IN (SELECT id FROM puzzles WHERE set_id = ?)
                """,
                (set_id,),
            )
            con.execute(
                "DELETE FROM rush_sessions WHERE set_id = ?",
                (set_id,),
            )

    # ── Rush session history ────────────────────────────────────────────────────

    def record_rush_session(self, mode_key: str, score: int, elapsed_s: float, set_id: int | None = None) -> None:
        """Persist a completed rush session (call once per session end)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as con:
            con.execute(
                "INSERT INTO rush_sessions (mode, score, elapsed_s, played_at, set_id) VALUES (?, ?, ?, ?, ?)",
                (mode_key, score, round(elapsed_s, 1), now, set_id),
            )

    def get_rush_history(self, mode_key: str, set_id: int | None = None, limit: int = 30) -> list[tuple[str, int]]:
        """Return up to *limit* rush sessions for a mode, oldest first.

        When *set_id* is given only sessions for that set are returned.
        Returns a list of (played_at, score) tuples suitable for charting.
        """
        with self._connect() as con:
            if set_id is not None:
                rows = con.execute(
                    """
                    SELECT played_at, score
                    FROM   rush_sessions
                    WHERE  mode = ? AND set_id = ?
                    ORDER  BY played_at DESC
                    LIMIT  ?
                    """,
                    (mode_key, set_id, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    """
                    SELECT played_at, score
                    FROM   rush_sessions
                    WHERE  mode = ?
                    ORDER  BY played_at DESC
                    LIMIT  ?
                    """,
                    (mode_key, limit),
                ).fetchall()
        # reverse so the list is chronological (oldest first)
        return [(r["played_at"], r["score"]) for r in reversed(rows)]

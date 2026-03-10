"""
Engine wrapper – optional Stockfish integration.

If Stockfish is not installed the application still runs; engine-dependent
features (analysis evaluation bar) are simply disabled.
"""

import shutil
from typing import Optional

import chess
import chess.engine


# Common executable names / locations on different platforms
_STOCKFISH_CANDIDATES = [
    "stockfish",
    "stockfish.exe",
    r"C:\Program Files\Stockfish\stockfish.exe",
    r"C:\stockfish\stockfish.exe",
    "/usr/bin/stockfish",
    "/usr/local/bin/stockfish",
    "/opt/homebrew/bin/stockfish",
]


def find_stockfish() -> Optional[str]:
    """Return the path of the first locatable Stockfish binary, or None."""
    for candidate in _STOCKFISH_CANDIDATES:
        path = shutil.which(candidate) or (candidate if shutil.os.path.isfile(candidate) else None)
        if path:
            return path
    return None


class EngineManager:
    """
    Thin wrapper around python-chess's UCI engine interface.

    All public methods are safe to call even when no engine is available –
    they simply return None / False.
    """

    def __init__(self):
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._engine_path: Optional[str] = None
        self.available: bool = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self, path: Optional[str] = None) -> bool:
        """
        Start the engine.  If *path* is None the manager searches for
        Stockfish automatically.  Returns True on success.
        """
        self.stop()
        engine_path = path or find_stockfish()
        if not engine_path:
            self.available = False
            return False
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(engine_path)
            self._engine_path = engine_path
            self.available = True
            return True
        except Exception:
            self._engine = None
            self.available = False
            return False

    def stop(self) -> None:
        """Quit the engine process cleanly."""
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None
        self.available = False

    # ── Analysis ───────────────────────────────────────────────────────────────

    def analyse(
        self,
        board: chess.Board,
        limit: chess.engine.Limit = None,
        depth: int = 15,
    ) -> Optional[chess.engine.InfoDict]:
        """
        Run a quick analysis and return the info dict.
        Returns None when the engine is unavailable.
        """
        if not self.available or self._engine is None:
            return None
        limit = limit or chess.engine.Limit(depth=depth)
        try:
            return self._engine.analyse(board, limit)
        except Exception:
            return None

    def get_best_move(
        self,
        board: chess.Board,
        time_limit: float = 0.5,
    ) -> Optional[chess.Move]:
        """
        Ask the engine for the best move under *time_limit* seconds.
        Returns None when unavailable.
        """
        if not self.available or self._engine is None:
            return None
        try:
            result = self._engine.play(board, chess.engine.Limit(time=time_limit))
            return result.move
        except Exception:
            return None

    def get_evaluation(
        self,
        board: chess.Board,
        depth: int = 15,
    ) -> Optional[float]:
        """
        Return a centipawn evaluation from White's point of view,
        clamped to ±1000. Returns None when unavailable or on error.
        """
        info = self.analyse(board, depth=depth)
        if info is None:
            return None
        score = info.get("score")
        if score is None:
            return None
        pov = score.white()
        if pov.is_mate():
            return 1000.0 if pov.mate() > 0 else -1000.0
        cp = pov.score()
        return max(-1000.0, min(1000.0, float(cp))) if cp is not None else None

    # ── Context manager support ────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop()

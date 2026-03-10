"""
Leaderboard – persists top-3 Puzzle Rush scores per mode to a JSON file
stored in the user's home directory (~/.chess_karma_scores.json).

Score entries
─────────────
  score      – puzzles fully solved
  elapsed_s  – seconds taken (timed: actual time used; survival: total elapsed)
  date       – human-readable timestamp

Ranking
───────
  Primary key  : score   (higher = better)
  Tiebreaker   : elapsed_s (lower = better for timed; for survival both equal rank)
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from chess_karma.core.rush_manager import RushMode

# Stored next to the user's home directory so it persists across runs
_SAVE_PATH = pathlib.Path.home() / ".chess_karma_scores.json"

_MODE_KEYS: dict[RushMode, str] = {
    RushMode.THREE_MIN: "3min",
    RushMode.FIVE_MIN:  "5min",
    RushMode.SURVIVAL:  "survival",
}

MAX_ENTRIES = 3


@dataclass
class ScoreEntry:
    score: int
    elapsed_s: float
    date: str

    def display_time(self, mode: RushMode) -> str:
        """Format elapsed_s for display depending on mode."""
        if mode == RushMode.SURVIVAL:
            # survival: show elapsed as a stopwatch
            m, s = divmod(int(self.elapsed_s), 60)
            return f"{m}:{s:02d}"
        else:
            # timed: show how much time was used out of the limit
            m, s = divmod(int(self.elapsed_s), 60)
            return f"{m}:{s:02d}"


class Leaderboard:
    """Loads and saves top-3 scores per Puzzle Rush mode."""

    def __init__(self) -> None:
        self._data: dict[str, list[dict]] = {k: [] for k in _MODE_KEYS.values()}
        self._load()

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_top(self, mode: RushMode) -> list[ScoreEntry]:
        """Return the current top-3 entries for a mode (best first)."""
        key = _MODE_KEYS[mode]
        return [ScoreEntry(**e) for e in self._data.get(key, [])]

    def submit(self, mode: RushMode, score: int, elapsed_s: float) -> int:
        """
        Add a new score entry and keep the top MAX_ENTRIES.

        Returns the new entry's rank (1 = best) or 0 if it didn't place.
        """
        key = _MODE_KEYS[mode]
        new_entry = {
            "score":     score,
            "elapsed_s": round(elapsed_s, 1),
            "date":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        entries: list[dict] = self._data.setdefault(key, [])
        entries.append(new_entry)

        # Sort: higher score first; on tie, lower elapsed time first
        entries.sort(key=lambda e: (-e["score"], e["elapsed_s"]))

        # Find the rank of the new entry before truncating
        try:
            rank = next(
                i + 1
                for i, e in enumerate(entries)
                if e is new_entry
            )
        except StopIteration:
            rank = 0

        self._data[key] = entries[:MAX_ENTRIES]
        self._save()
        return rank if rank <= MAX_ENTRIES else 0

    def is_high_score(self, mode: RushMode, score: int, elapsed_s: float) -> bool:
        """True if this score would make it into the top-3."""
        entries = self._data.get(_MODE_KEYS[mode], [])
        if len(entries) < MAX_ENTRIES:
            return True
        # Would it beat the last entry?
        last = entries[-1]
        if score > last["score"]:
            return True
        if score == last["score"] and elapsed_s < last["elapsed_s"]:
            return True
        return False

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if _SAVE_PATH.exists():
                loaded = json.loads(_SAVE_PATH.read_text(encoding="utf-8"))
                for key in self._data:
                    if key in loaded and isinstance(loaded[key], list):
                        self._data[key] = loaded[key]
        except Exception:
            pass

    def _save(self) -> None:
        try:
            _SAVE_PATH.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

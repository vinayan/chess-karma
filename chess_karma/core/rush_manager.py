"""
RushManager – state model for a Puzzle Rush session.

Modes
─────
  3min      – 3-minute countdown; end on timeout or 3 failures
  5min      – 5-minute countdown; end on timeout or 3 failures
  survival  – no time limit; end on 3 failures

Failure = one incorrect move attempt.
Score   = number of puzzles fully solved before the session ends.
"""

from __future__ import annotations

import random
import time
from enum import Enum
from typing import Optional


class RushMode(Enum):
    THREE_MIN = "3min"
    FIVE_MIN  = "5min"
    SURVIVAL  = "survival"


_TIME_LIMITS: dict[RushMode, Optional[float]] = {
    RushMode.THREE_MIN: 180.0,
    RushMode.FIVE_MIN:  300.0,
    RushMode.SURVIVAL:  None,
}

MAX_FAILURES = 3


class RushManager:
    """
    Tracks all mutable state for a single Puzzle Rush session.

    Usage
    ─────
    1. Construct with mode + total number of available puzzles.
    2. Call start() when the first puzzle is shown.
    3. For each player move call record_correct() or record_failure().
    4. Poll is_over() or is_time_up() to detect end conditions.
    5. Read score / failures / lives_left for display.
    6. Call end() explicitly to freeze elapsed time.
    """

    def __init__(self, mode: RushMode, puzzle_count: int) -> None:
        self.mode = mode
        self.time_limit: Optional[float] = _TIME_LIMITS[mode]

        # Session statistics
        self.score: int = 0       # puzzles fully solved
        self.failures: int = 0    # wrong move attempts

        # Shuffled puzzle index list so each run is in a different order
        self._order: list[int] = list(range(puzzle_count))
        random.shuffle(self._order)
        self._order_pos: int = 0  # pointer into _order

        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    # ── Life-cycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Record the session start time."""
        self._start_time = time.monotonic()

    def end(self) -> None:
        """Freeze the session; subsequent calls to elapsed_s() return the same value."""
        if self._end_time is None:
            self._end_time = time.monotonic()

    # ── Puzzle ordering ────────────────────────────────────────────────────────

    def next_puzzle_index(self) -> Optional[int]:
        """Return the next puzzle index from the shuffled order, or None if exhausted."""
        if self._order_pos < len(self._order):
            idx = self._order[self._order_pos]
            self._order_pos += 1
            return idx
        return None

    def current_puzzle_index(self) -> Optional[int]:
        """Return the puzzle index currently being solved (last returned by next_puzzle_index)."""
        pos = self._order_pos - 1
        if 0 <= pos < len(self._order):
            return self._order[pos]
        return None

    # ── Event recording ────────────────────────────────────────────────────────

    def record_correct(self) -> None:
        """Call when a puzzle is fully solved."""
        self.score += 1

    def record_failure(self) -> bool:
        """
        Call when the player makes an incorrect move.
        Returns True if the session should end (MAX_FAILURES reached).
        """
        self.failures += 1
        if self.failures >= MAX_FAILURES:
            self.end()
            return True
        return False

    # ── State queries ──────────────────────────────────────────────────────────

    @property
    def lives_left(self) -> int:
        return max(0, MAX_FAILURES - self.failures)

    def elapsed_s(self) -> float:
        """Seconds since start (frozen once end() is called)."""
        if self._start_time is None:
            return 0.0
        ref = self._end_time if self._end_time is not None else time.monotonic()
        return ref - self._start_time

    def remaining_s(self) -> Optional[float]:
        """Seconds remaining for timed modes; None for survival."""
        if self.time_limit is None:
            return None
        return max(0.0, self.time_limit - self.elapsed_s())

    def is_time_up(self) -> bool:
        r = self.remaining_s()
        return r is not None and r <= 0.0

    def is_over(self) -> bool:
        return self._end_time is not None or self.is_time_up() or self.failures >= MAX_FAILURES

    # ── Display helpers ────────────────────────────────────────────────────────

    def format_timer(self) -> str:
        """
        Human-readable timer string.
        Timed modes: countdown  "2:47"
        Survival:    stopwatch  "1:23"
        """
        if self.time_limit is not None:
            secs = int(self.remaining_s() or 0)
        else:
            secs = int(self.elapsed_s())
        m, s = divmod(secs, 60)
        return f"{m}:{s:02d}"

    def format_lives(self) -> str:
        """Returns a hearts string e.g.  '♥ ♥ ♡'"""
        filled = "♥"
        empty  = "♡"
        return "  ".join(
            filled if i < self.lives_left else empty
            for i in range(MAX_FAILURES)
        )

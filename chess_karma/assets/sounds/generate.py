"""
Sound asset generator.

Creates all required WAV files inside chess_karma/assets/sounds/ using only
the Python standard library (wave + struct + math).  The files are generated
once and reused on subsequent launches.

Sound design
────────────
move     – short woody tap  (sine burst, fast decay, ~90 ms)
capture  – heavier thud     (lower-pitched sine burst, ~120 ms)
success  – bright fanfare   (three ascending notes C5-E5-G5, ~600 ms total)
fail     – descending buzz  (square wave, ~350 ms)
"""

from __future__ import annotations

import math
import pathlib
import struct
import wave

# ── Output directory ───────────────────────────────────────────────────────────
_SOUNDS_DIR = pathlib.Path(__file__).parent

# ── Audio constants ────────────────────────────────────────────────────────────
_SAMPLE_RATE = 44100
_CHANNELS    = 1
_SAMPWIDTH   = 2           # 16-bit PCM
_MAX_AMP     = 32000       # keep headroom below 32767

# ── Internal helpers ───────────────────────────────────────────────────────────

def _write_wav(path: pathlib.Path, samples: list[float]) -> None:
    """Write a mono 16-bit PCM WAV file from a list of float samples in [-1, 1]."""
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(_SAMPWIDTH)
        wf.setframerate(_SAMPLE_RATE)
        raw = struct.pack(f"<{len(samples)}h", *(int(s * _MAX_AMP) for s in samples))
        wf.writeframes(raw)


def _sine_burst(freq: float, duration: float, decay: float = 8.0) -> list[float]:
    """
    Sine wave with exponential decay envelope.

    freq     – frequency in Hz
    duration – total length in seconds
    decay    – envelope time-constant (higher = shorter click)
    """
    n = int(_SAMPLE_RATE * duration)
    return [
        math.sin(2 * math.pi * freq * i / _SAMPLE_RATE) * math.exp(-decay * i / _SAMPLE_RATE)
        for i in range(n)
    ]


def _square_burst(freq: float, duration: float, decay: float = 5.0) -> list[float]:
    """Square wave with exponential decay (buzzy quality)."""
    n = int(_SAMPLE_RATE * duration)
    return [
        math.copysign(1.0, math.sin(2 * math.pi * freq * i / _SAMPLE_RATE))
        * math.exp(-decay * i / _SAMPLE_RATE)
        for i in range(n)
    ]


def _note(freq: float, duration: float, attack: float = 0.01, release: float = 0.05) -> list[float]:
    """Smooth piano-like note with attack/release envelope."""
    n = int(_SAMPLE_RATE * duration)
    attack_n  = int(_SAMPLE_RATE * attack)
    release_n = int(_SAMPLE_RATE * release)
    samples = []
    for i in range(n):
        # Harmonic richness: fundamental + 2nd + 3rd partial
        s = (
            0.60 * math.sin(2 * math.pi * freq       * i / _SAMPLE_RATE) +
            0.25 * math.sin(2 * math.pi * freq * 2.0 * i / _SAMPLE_RATE) +
            0.15 * math.sin(2 * math.pi * freq * 3.0 * i / _SAMPLE_RATE)
        )
        # Envelope
        if i < attack_n:
            env = i / attack_n
        elif i > n - release_n:
            env = (n - i) / release_n
        else:
            env = 1.0
        samples.append(s * env)
    return samples


def _concat(parts: list[list[float]]) -> list[float]:
    out: list[float] = []
    for p in parts:
        out.extend(p)
    return out


def _normalise(samples: list[float], peak: float = 0.90) -> list[float]:
    max_val = max(abs(s) for s in samples) or 1.0
    scale = peak / max_val
    return [s * scale for s in samples]


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_all(force: bool = False) -> None:
    """
    Generate all sound assets.  Skips files that already exist unless
    *force* is True.
    """
    _gen_move(force)
    _gen_capture(force)
    _gen_success(force)
    _gen_fail(force)


def _gen_move(force: bool) -> None:
    path = _SOUNDS_DIR / "move.wav"
    if path.exists() and not force:
        return
    # Woody tap: mid-range sine burst, quick decay
    samples = _sine_burst(freq=680, duration=0.09, decay=10)
    _write_wav(path, _normalise(samples))


def _gen_capture(force: bool) -> None:
    path = _SOUNDS_DIR / "capture.wav"
    if path.exists() and not force:
        return
    # Heavier thud: lower frequency, slightly longer
    samples = _sine_burst(freq=390, duration=0.13, decay=8)
    _write_wav(path, _normalise(samples))


def _gen_success(force: bool) -> None:
    path = _SOUNDS_DIR / "success.wav"
    if path.exists() and not force:
        return
    # Three ascending notes: C5 (523 Hz) – E5 (659 Hz) – G5 (784 Hz)
    silence = [0.0] * int(_SAMPLE_RATE * 0.04)  # 40 ms gap between notes
    parts = [
        _note(523.25, 0.18),
        silence,
        _note(659.25, 0.18),
        silence,
        _note(783.99, 0.28),
    ]
    _write_wav(path, _normalise(_concat(parts)))


def _gen_fail(force: bool) -> None:
    path = _SOUNDS_DIR / "fail.wav"
    if path.exists() and not force:
        return
    # Descending buzzer: two short square-wave pulses stepping down
    gap = [0.0] * int(_SAMPLE_RATE * 0.03)
    parts = [
        _square_burst(freq=320, duration=0.16, decay=4),
        gap,
        _square_burst(freq=220, duration=0.20, decay=3),
    ]
    _write_wav(path, _normalise(_concat(parts), peak=0.70))

"""
SoundManager - low-latency audio playback for Chess Karma.

Primary backend  : winsound (Windows built-in, uses OS audio routing)
Fallback backend : QSoundEffect (cross-platform, Qt multimedia)

All MP3 source files are converted to WAV on first run via miniaudio.

Sound events
------------
  play_move()    - quiet piece placement
  play_capture() - piece takes another piece
  play_castle()  - castling move
  play_check()   - king placed in check
"""

from __future__ import annotations

import pathlib
import sys
import threading

_SOUNDS_DIR = pathlib.Path(__file__).parent.parent / "assets" / "sounds"

_STEMS = ("move", "capture", "castle", "check")

# ---------------------------------------------------------------------------
# Detect available backends
# ---------------------------------------------------------------------------
_USE_WINSOUND = sys.platform == "win32"

if not _USE_WINSOUND:
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QSoundEffect
        _USE_QSOUNDEFFECT = True
    except Exception:
        _USE_QSOUNDEFFECT = False
else:
    _USE_QSOUNDEFFECT = False


class SoundManager:
    """
    Manages sound playback for Chess Karma.
    On Windows uses winsound (SND_ASYNC) which always routes through the
    OS default playback device regardless of Qt audio settings.
    All methods are safe to call when audio is unavailable.
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._ensure_wavs()
        self._paths: dict[str, pathlib.Path | None] = {}
        self._fx: dict[str, object] = {}

        for stem in _STEMS:
            wav = _SOUNDS_DIR / (stem + ".wav")
            self._paths[stem] = wav if wav.exists() else None

        if _USE_QSOUNDEFFECT:
            self._load_qsoundeffects()

    # -- Public API ------------------------------------------------------------

    def play_move(self) -> None:
        self._play("move")

    def play_capture(self) -> None:
        self._play("capture")

    def play_castle(self) -> None:
        self._play("castle")

    def play_check(self) -> None:
        self._play("check")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    # -- Internal helpers ------------------------------------------------------

    def _play(self, stem: str) -> None:
        if not self._enabled:
            return
        if _USE_WINSOUND:
            self._play_winsound(stem)
        elif _USE_QSOUNDEFFECT:
            self._play_qsoundeffect(stem)

    def _play_winsound(self, stem: str) -> None:
        """Play via Windows winsound in a daemon thread.

        SND_ASYNC is avoided because Bluetooth A2DP has a ~200 ms wake-up
        latency; the async fire-and-forget call returns before the BT device
        is ready and the audio is silently dropped.  Running synchronous
        (blocking) playback inside a daemon thread lets BT wake up while the
        UI stays responsive.
        """
        import winsound
        path = self._paths.get(stem)
        if path is None:
            return
        flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT

        def _run() -> None:
            try:
                winsound.PlaySound(str(path), flags)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def _play_qsoundeffect(self, stem: str) -> None:
        from PyQt6.QtMultimedia import QSoundEffect
        fx = self._fx.get(stem)
        if fx is None:
            return
        try:
            if fx.status() == QSoundEffect.Status.Ready:
                fx.play()
        except Exception:
            pass

    def _load_qsoundeffects(self) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QSoundEffect
        for stem, path in self._paths.items():
            if path is None:
                self._fx[stem] = None
                continue
            try:
                fx = QSoundEffect()
                fx.setSource(QUrl.fromLocalFile(str(path.resolve())))
                fx.setVolume(0.9)
                self._fx[stem] = fx
            except Exception:
                self._fx[stem] = None

    @staticmethod
    def _ensure_wavs() -> None:
        """Convert any MP3 that lacks a WAV counterpart, then synthesise fallbacks."""
        # 1. Convert user MP3s -> WAV via miniaudio
        try:
            import wave as _wave
            import miniaudio as _ma
            for stem in _STEMS:
                mp3 = _SOUNDS_DIR / (stem + ".mp3")
                wav = _SOUNDS_DIR / (stem + ".wav")
                if mp3.exists() and not wav.exists():
                    decoded = _ma.decode_file(
                        str(mp3),
                        output_format=_ma.SampleFormat.SIGNED16,
                        nchannels=1,
                        sample_rate=44100,
                    )
                    with _wave.open(str(wav), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(44100)
                        wf.writeframes(decoded.samples)
        except Exception:
            pass

        # 2. Synthesise any still-missing WAVs as silent fallbacks
        try:
            from chess_karma.assets.sounds.generate import generate_all
            generate_all()
        except Exception:
            pass

"""Non-destructive edits: every function returns a new AudioClip and leaves its input untouched."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Literal

import numpy as np

from .analysis import detect_silence, from_db, to_db
from .clip import AudioClip
from .loudness import measure_loudness

Curve = Literal["linear", "cosine"]
DEFAULT_CROSSFADE = 0.005  # seconds blended across a cut so the join does not click


def _frames(clip: AudioClip, seconds: float) -> int:
    return clip.time_to_frame(seconds)


def _ramp(n: int, curve: Curve) -> np.ndarray:
    """0 -> 1 over ``n`` samples."""
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    return t if curve == "linear" else (0.5 - 0.5 * np.cos(np.pi * t)).astype(np.float32)


def keep(clip: AudioClip, start: float, stop: float) -> AudioClip:
    """Trim to ``[start, stop]``, discarding everything outside."""
    a, b = _frames(clip, start), _frames(clip, stop)
    if b <= a:
        raise ValueError("the range to keep is empty")
    return AudioClip(clip.samples[:, a:b], clip.sample_rate)


def remove_ranges(
    clip: AudioClip, ranges: Iterable[tuple[float, float]], crossfade: float = DEFAULT_CROSSFADE
) -> AudioClip:
    """Delete every ``(start, stop)`` range and join what remains, blending each join over ``crossfade`` seconds."""
    spans = sorted((_frames(clip, a), _frames(clip, b)) for a, b in ranges)
    merged: list[list[int]] = []
    for a, b in spans:
        if b <= a:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    pieces, cursor = [], 0
    for a, b in merged:
        if a > cursor:
            pieces.append(clip.samples[:, cursor:a])
        cursor = max(cursor, b)
    if cursor < clip.frames:
        pieces.append(clip.samples[:, cursor:])
    if not pieces:
        raise ValueError("that would delete the whole clip")

    blend = round(crossfade * clip.sample_rate)
    joined = pieces[0]
    for piece in pieces[1:]:
        joined = _join(joined, piece, blend)
    return AudioClip(joined, clip.sample_rate)


def cut(
    clip: AudioClip, start: float, stop: float, crossfade: float = DEFAULT_CROSSFADE
) -> AudioClip:
    """Delete ``[start, stop]`` and close the gap."""
    return remove_ranges(clip, [(start, stop)], crossfade)


def _join(left: np.ndarray, right: np.ndarray, blend: int) -> np.ndarray:
    n = min(blend, left.shape[1], right.shape[1])
    if n <= 1:
        return np.concatenate([left, right], axis=1)
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    mixed = left[:, -n:] * (1 - ramp) + right[:, :n] * ramp
    return np.concatenate([left[:, :-n], mixed, right[:, n:]], axis=1)


def fade(
    clip: AudioClip,
    start: float,
    stop: float,
    direction: Literal["in", "out"],
    curve: Curve = "cosine",
) -> AudioClip:
    """Fade the samples in ``[start, stop]`` from silence up (``in``) or down to silence (``out``)."""
    a, b = _frames(clip, start), _frames(clip, stop)
    if b - a < 2:
        return clip
    ramp = _ramp(b - a, curve)
    gain = ramp if direction == "in" else ramp[::-1]
    out = clip.samples.copy()
    out[:, a:b] *= gain
    if direction == "in":
        out[:, :a] = 0.0  # a fade-in over a selection implies silence before it
    else:
        out[:, b:] = 0.0
    return AudioClip(out, clip.sample_rate)


def fade_in(clip: AudioClip, duration: float, curve: Curve = "cosine") -> AudioClip:
    """Fade in over the first ``duration`` seconds."""
    return fade(clip, 0.0, min(duration, clip.duration), "in", curve)


def fade_out(clip: AudioClip, duration: float, curve: Curve = "cosine") -> AudioClip:
    """Fade out over the last ``duration`` seconds."""
    return fade(clip, max(clip.duration - duration, 0.0), clip.duration, "out", curve)


def silence_range(clip: AudioClip, start: float, stop: float) -> AudioClip:
    """Replace ``[start, stop]`` with silence (the length does not change)."""
    a, b = _frames(clip, start), _frames(clip, stop)
    out = clip.samples.copy()
    out[:, a:b] = 0.0
    return AudioClip(out, clip.sample_rate)


def gain_db(clip: AudioClip, db: float) -> AudioClip:
    return clip.gain(from_db(db))


def normalize_peak(clip: AudioClip, target_db: float = -1.0) -> AudioClip:
    """Scale so the loudest sample sits at ``target_db`` dBFS. Silent clips are returned unchanged."""
    peak = clip.peak()
    if peak <= 1e-9:
        return clip
    return gain_db(clip, target_db - float(to_db(peak)))


def normalize_loudness(
    clip: AudioClip, target_lufs: float = -16.0, ceiling_db: float = -1.0
) -> tuple[AudioClip, float]:
    """Scale to ``target_lufs`` integrated loudness without letting the peak pass ``ceiling_db``.

    Returns ``(clip, gain_applied_db)``. The gain is reduced when reaching the target would clip, so
    the result can end up quieter than requested; compare ``measure_loudness`` if that matters.
    """
    integrated = measure_loudness(clip).integrated
    if not math.isfinite(integrated) or clip.peak() <= 1e-9:
        return clip, 0.0
    wanted = target_lufs - integrated
    headroom = ceiling_db - float(to_db(clip.peak()))
    applied = min(wanted, headroom)
    return gain_db(clip, applied), applied


def trim_silence(
    clip: AudioClip, threshold_db: float = -50.0, padding: float = 0.05, min_duration: float = 0.1
) -> AudioClip:
    """Remove quiet stretches at the start and end, keeping ``padding`` seconds of lead-in and tail."""
    mono = clip.samples.max(axis=0) if clip.channels > 1 else clip.channel(0)
    quiet = detect_silence(mono, clip.sample_rate, threshold_db, min_duration)
    start, stop = 0.0, clip.duration
    if quiet and quiet[0][0] <= 1e-6:
        start = max(quiet[0][1] - padding, 0.0)
    if quiet and quiet[-1][1] >= clip.duration - 0.011:
        stop = min(quiet[-1][0] + padding, clip.duration)
    return clip if (start <= 0 and stop >= clip.duration) else keep(clip, start, stop)


def silent_ranges(
    clip: AudioClip, threshold_db: float = -50.0, min_duration: float = 0.3
) -> list[tuple[float, float]]:
    """Time ranges where every channel stays below ``threshold_db``."""
    loudest = np.abs(clip.samples).max(axis=0)
    return detect_silence(loudest, clip.sample_rate, threshold_db, min_duration)

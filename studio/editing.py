"""Maps the edit actions in the UI to library operations, so the rules live in one testable place."""

from __future__ import annotations

from audiowave import AudioClip, Loop
from audiowave.core import edit, measure_loudness

DEFAULT_FADE = 0.5  # seconds, when no selection is made


class EditError(ValueError):
    """The action cannot be applied right now (the message is shown to the user)."""


ACTIONS = (
    "trim", "cut", "fade_in", "fade_out", "silence_selection",
    "normalize_peak", "normalize_loudness", "trim_silence", "remove_silences",
)  # fmt: skip


def _need_selection(selection: Loop | None, what: str) -> Loop:
    if selection is None or selection.length <= 0.01:
        raise EditError(f"Select a region first (drag on the ruler) to {what}.")
    return selection


def apply_action(
    action: str,
    clip: AudioClip,
    selection: Loop | None = None,
    value: float | None = None,
    silences: list[Loop] | None = None,
) -> tuple[AudioClip, str]:
    """Apply ``action`` and return ``(new_clip, label)``. Raises :class:`EditError` if it does not apply."""
    try:
        return _apply(action, clip, selection, value, silences or [])
    except EditError:
        raise
    except ValueError as error:  # the library refuses empty results
        raise EditError(str(error).capitalize() + ".") from error


def _apply(
    action: str, clip: AudioClip, selection: Loop | None, value: float | None, silences: list[Loop]
) -> tuple[AudioClip, str]:
    if action == "trim":
        s = _need_selection(selection, "trim to it")
        return edit.keep(clip, s.start, s.end), f"Trim to {s.length:.1f} s"
    if action == "cut":
        s = _need_selection(selection, "cut it")
        return edit.cut(clip, s.start, s.end), f"Cut {s.length:.1f} s"
    if action in ("fade_in", "fade_out"):
        direction = "in" if action == "fade_in" else "out"
        if selection is not None and selection.length > 0.01:
            return edit.fade(
                clip, selection.start, selection.end, direction
            ), f"Fade {direction} selection"
        seconds = min(DEFAULT_FADE, clip.duration)
        fn = edit.fade_in if direction == "in" else edit.fade_out
        return fn(clip, seconds), f"Fade {direction} {seconds:g} s"
    if action == "silence_selection":
        s = _need_selection(selection, "silence it")
        return edit.silence_range(clip, s.start, s.end), "Silence selection"
    if action == "normalize_peak":
        target = -1.0 if value is None else value
        return edit.normalize_peak(clip, target), f"Normalize peak to {target:g} dBFS"
    if action == "normalize_loudness":
        target = -16.0 if value is None else value
        out, applied = edit.normalize_loudness(clip, target)
        if applied == 0.0 and out is clip:
            raise EditError("This clip is too quiet or too short to measure its loudness.")
        return out, f"Normalize to {target:g} LUFS ({applied:+.1f} dB)"
    if action == "trim_silence":
        out = edit.trim_silence(clip)
        if out is clip:
            raise EditError("There is no silence at the start or end to trim.")
        return out, f"Trim silence ({clip.duration - out.duration:.1f} s removed)"
    if action == "remove_silences":
        if not silences:
            raise EditError("Find silences first, then remove them.")
        out = edit.remove_ranges(clip, [(s.start, s.end) for s in silences])
        return out, f"Remove {len(silences)} silence{'s' if len(silences) != 1 else ''}"
    raise EditError(f"Unknown action: {action}")


def measure(clip: AudioClip):
    """Loudness measurement, for use as a background task."""
    return measure_loudness(clip)

"""Things a user can place on the timeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Loop:
    """A repeat region in seconds. Always normalised so ``start <= end``."""

    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start > self.end:
            start, end = self.end, self.start
            object.__setattr__(self, "start", start)
            object.__setattr__(self, "end", end)

    @property
    def length(self) -> float:
        return self.end - self.start

    def contains(self, t: float) -> bool:
        return self.start <= t <= self.end


@dataclass(frozen=True)
class Marker:
    """A named point in time."""

    time: float
    label: str = ""

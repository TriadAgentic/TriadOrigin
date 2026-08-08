"""Causal clocks and watermarks (MOD-003, Doc 02 §02.2, Doc 04 §04.3).

Domain clocks are explicit and never inferred from envelope emission time (Doc 03 §03.3). A detector
distinguishes *event time* (when it happened at the venue), *availability/watermark time* (when the
dependency window completed), *knowledge time* (when we learned it) and *publication time*.

A watermark completes a partition up to a finalized event time; a finalized bar is eligible only
after its close event is received and its watermark completes. A cross-venue reader never uses a
later venue update early.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from .canonical import INT64_MAX, INT64_MIN


class ClockError(ValueError):
    """A causal-clock ordering violation. Fail closed."""


@dataclass(frozen=True)
class Clocks:
    """The four canonical clocks carried by a semantic fact (all integer microseconds)."""

    event_time_us: int
    availability_time_us: int
    knowledge_time_us: int
    publication_time_us: int

    def __post_init__(self) -> None:
        for name, value in (
            ("event_time_us", self.event_time_us),
            ("availability_time_us", self.availability_time_us),
            ("knowledge_time_us", self.knowledge_time_us),
            ("publication_time_us", self.publication_time_us),
        ):
            _require_int64(value, name)
        # Knowledge cannot precede availability; availability cannot precede the event; publication
        # cannot precede knowledge. These are causal, not operational, constraints.
        if self.availability_time_us < self.event_time_us:
            raise ClockError("availability precedes event time")
        if self.knowledge_time_us < self.availability_time_us:
            raise ClockError("knowledge precedes availability")
        if self.publication_time_us < self.knowledge_time_us:
            raise ClockError("publication precedes knowledge")


class Watermark:
    """Monotonic per-partition watermark with bounded allowed lateness."""

    __slots__ = ("_allowed_lateness_us", "_completed_through_us", "_lock")

    def __init__(self, allowed_lateness_us: int, completed_through_us: int = -1) -> None:
        _require_int64(allowed_lateness_us, "allowed_lateness_us", non_negative=True)
        _require_int64(completed_through_us, "completed_through_us")
        if completed_through_us < -1:
            raise ClockError("completed_through_us must be -1 or non-negative")
        self._allowed_lateness_us = allowed_lateness_us
        self._completed_through_us = completed_through_us
        self._lock = RLock()

    @property
    def allowed_lateness_us(self) -> int:
        return self._allowed_lateness_us

    @property
    def completed_through_us(self) -> int:
        with self._lock:
            return self._completed_through_us

    def advance(self, finalized_event_time_us: int) -> None:
        """Advance the watermark to a newly finalized event time. Monotonic; never goes backward."""
        _require_int64(finalized_event_time_us, "finalized_event_time_us", non_negative=True)
        with self._lock:
            if finalized_event_time_us < self._completed_through_us:
                raise ClockError(
                    f"watermark cannot retreat: {finalized_event_time_us} < "
                    f"{self._completed_through_us}")
            self._completed_through_us = finalized_event_time_us

    def is_complete_for(self, as_of_event_time_us: int) -> bool:
        """Has the partition completed through ``as_of_event_time_us``?"""
        _require_int64(as_of_event_time_us, "as_of_event_time_us", non_negative=True)
        with self._lock:
            return self._completed_through_us >= as_of_event_time_us

    def is_late(self, event_time_us: int) -> bool:
        """A record older than ``completed_through - allowed_lateness`` is a late correction."""
        _require_int64(event_time_us, "event_time_us", non_negative=True)
        with self._lock:
            if self._completed_through_us < 0:
                return False
            return event_time_us < self._completed_through_us - self._allowed_lateness_us


def assert_not_future_venue_read(
    reader_knowledge_us: int, other_venue_knowledge_us: int
) -> None:
    """Reject a fact that was not yet known at the reader's knowledge time."""
    _require_int64(reader_knowledge_us, "reader_knowledge_us", non_negative=True)
    _require_int64(other_venue_knowledge_us, "other_venue_knowledge_us", non_negative=True)
    if other_venue_knowledge_us > reader_knowledge_us:
        raise ClockError("cross-venue read would consume a future venue update early")


def _require_int64(value: object, name: str, *, non_negative: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ClockError(f"{name} must be a signed-int64 integer")
    if value < INT64_MIN or value > INT64_MAX:
        raise ClockError(f"{name} is outside signed-int64 range")
    if non_negative and value < 0:
        raise ClockError(f"{name} must be non-negative")
    return value

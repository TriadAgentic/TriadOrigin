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
        # Knowledge cannot precede availability; availability cannot precede the event; publication
        # cannot precede knowledge. These are causal, not operational, constraints.
        if self.availability_time_us < self.event_time_us:
            raise ClockError("availability precedes event time")
        if self.knowledge_time_us < self.availability_time_us:
            raise ClockError("knowledge precedes availability")
        if self.publication_time_us < self.knowledge_time_us:
            raise ClockError("publication precedes knowledge")


@dataclass
class Watermark:
    """Monotonic per-partition watermark with bounded allowed lateness."""

    allowed_lateness_us: int
    completed_through_us: int = -1

    def advance(self, finalized_event_time_us: int) -> None:
        """Advance the watermark to a newly finalized event time. Monotonic; never goes backward."""
        if finalized_event_time_us < self.completed_through_us:
            raise ClockError(
                f"watermark cannot retreat: {finalized_event_time_us} < {self.completed_through_us}")
        self.completed_through_us = finalized_event_time_us

    def is_complete_for(self, as_of_event_time_us: int) -> bool:
        """Has the partition completed through ``as_of_event_time_us``?"""
        return self.completed_through_us >= as_of_event_time_us

    def is_late(self, event_time_us: int) -> bool:
        """A record older than ``completed_through - allowed_lateness`` is a late correction."""
        if self.completed_through_us < 0:
            return False
        return event_time_us < self.completed_through_us - self.allowed_lateness_us


def assert_not_future_venue_read(reader_knowledge_us: int, other_venue_event_us: int) -> None:
    """A cross-venue atom never consumes a later venue update early (Doc 02 §02.11)."""
    if other_venue_event_us > reader_knowledge_us:
        raise ClockError("cross-venue read would consume a future venue update early")

"""Partition key, single-writer coordinator, and the E01 partition input-quality machine.

- ``PartitionKey`` = ``(venue_model, canonical_instrument_id, semantic_timeframe)`` (Doc 02 §02.2).
  One logical writer orders each partition.
- ``PartitionCoordinator`` enforces single-writer ownership and a deterministic partition order
  (recorded local receipt order plus source-specific venue sequence — no fabricated total exchange
  order across connections).
- ``QualityMachine`` is the pure E01 input-quality state machine (Doc 04 §04.3). Operational quality
  can block a semantic transition without changing already-confirmed semantic history.

MOD-002 (partition_coordinator) + the E01 partition-quality machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True, order=True)
class PartitionKey:
    venue_model: str
    canonical_instrument_id: str
    semantic_timeframe: str

    def __str__(self) -> str:
        return f"{self.venue_model}|{self.canonical_instrument_id}|{self.semantic_timeframe}"


class PartitionError(RuntimeError):
    """Single-writer or ordering violation. Fail closed."""


@dataclass
class PartitionCoordinator:
    """Grants exactly one writer per partition and hands out monotonic sequence numbers."""

    _owner: dict[PartitionKey, str] = field(default_factory=dict)
    _seq: dict[PartitionKey, int] = field(default_factory=dict)

    def claim(self, key: PartitionKey, writer_id: str) -> None:
        current = self._owner.get(key)
        if current is not None and current != writer_id:
            raise PartitionError(
                f"partition {key} already owned by {current!r}; two writers not permitted")
        self._owner[key] = writer_id
        self._seq.setdefault(key, -1)

    def next_seq(self, key: PartitionKey, writer_id: str) -> int:
        if self._owner.get(key) != writer_id:
            raise PartitionError(f"{writer_id!r} does not own partition {key}")
        self._seq[key] += 1
        return self._seq[key]


def deterministic_order(events: list[dict]) -> list[dict]:
    """Order events within a partition by (venue_sequence, receive_sequence, local receipt).

    Cross-connection events have no fabricated total exchange order; this preserves the
    source-specific venue sequence and the recorded local receipt order as the tie-break.
    """
    def _key(e: dict) -> tuple:
        return (
            _as_int(e.get("venue_sequence"), default=0),
            _as_int(e.get("receive_sequence"), default=0),
            _as_int(e.get("local_receipt_mono_ns"), default=0),
            str(e.get("raw_event_id", "")),
        )

    return sorted(events, key=_key)


def _as_int(v, default: int) -> int:
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# --- E01 partition input-quality machine (Doc 04 §04.3) ------------------------------------------
class Quality(str, Enum):
    INIT = "INIT"
    SYNCING = "SYNCING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    GAPPED = "GAPPED"
    STALE = "STALE"
    RESYNCING = "RESYNCING"


class QualityEvent(str, Enum):
    START = "START"
    SNAPSHOT_ALIGNED = "SNAPSHOT_ALIGNED"
    SNAPSHOT_TIMEOUT = "SNAPSHOT_TIMEOUT"
    OPTIONAL_STALE = "OPTIONAL_STALE"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    FRESHNESS_EXCEEDED = "FRESHNESS_EXCEEDED"
    RECOVERY_BEGIN = "RECOVERY_BEGIN"
    RESNAPSHOT_COMPLETE = "RESNAPSHOT_COMPLETE"
    METADATA_INVALID = "METADATA_INVALID"


# (from_state, event) -> to_state. Unknown combinations reject with a named reason (fail closed).
_QUALITY_TABLE: dict[tuple[Quality, QualityEvent], Quality] = {
    (Quality.INIT, QualityEvent.START): Quality.SYNCING,
    (Quality.SYNCING, QualityEvent.SNAPSHOT_ALIGNED): Quality.READY,
    (Quality.SYNCING, QualityEvent.SNAPSHOT_TIMEOUT): Quality.DEGRADED,
    (Quality.READY, QualityEvent.OPTIONAL_STALE): Quality.DEGRADED,
    (Quality.READY, QualityEvent.SEQUENCE_GAP): Quality.GAPPED,
    (Quality.DEGRADED, QualityEvent.SEQUENCE_GAP): Quality.GAPPED,
    (Quality.READY, QualityEvent.FRESHNESS_EXCEEDED): Quality.STALE,
    (Quality.DEGRADED, QualityEvent.FRESHNESS_EXCEEDED): Quality.STALE,
    (Quality.GAPPED, QualityEvent.RECOVERY_BEGIN): Quality.RESYNCING,
    (Quality.STALE, QualityEvent.RECOVERY_BEGIN): Quality.RESYNCING,
    (Quality.DEGRADED, QualityEvent.RECOVERY_BEGIN): Quality.RESYNCING,
    (Quality.RESYNCING, QualityEvent.RESNAPSHOT_COMPLETE): Quality.READY,
}

# Metadata invalidity can strike from any state (Doc 04 §04.3 "ANY").
_ANY_STATE_EVENTS = {QualityEvent.METADATA_INVALID: Quality.DEGRADED}

# Only READY authorizes new entries / new semantic transitions.
_ENTRY_ELIGIBLE = {Quality.READY}


class QualityTransitionError(RuntimeError):
    """An undefined partition-quality transition. Fail closed."""


def quality_transition(state: Quality, event: QualityEvent) -> Quality:
    if event in _ANY_STATE_EVENTS:
        return _ANY_STATE_EVENTS[event]
    to = _QUALITY_TABLE.get((state, event))
    if to is None:
        raise QualityTransitionError(f"no transition from {state.value} on {event.value}")
    return to


def entry_eligible(state: Quality) -> bool:
    """Is the partition healthy enough to authorize a new/increasing semantic transition?"""
    return state in _ENTRY_ELIGIBLE

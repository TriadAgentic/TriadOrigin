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
from threading import RLock

from .canonical import (
    CanonicalError,
    canonical_json,
    loads_canonical,
    nfc,
    str_to_tick,
    tick_to_str,
)


@dataclass(frozen=True, order=True)
class PartitionKey:
    venue_model: str
    canonical_instrument_id: str
    semantic_timeframe: str

    def __post_init__(self) -> None:
        for name, value in (
            ("venue_model", self.venue_model),
            ("canonical_instrument_id", self.canonical_instrument_id),
            ("semantic_timeframe", self.semantic_timeframe),
        ):
            if not isinstance(value, str) or not value or "|" in value:
                raise PartitionError(
                    f"partition {name} must be a non-empty string without the '|' delimiter"
                )
            normalized = nfc(value)
            try:
                canonical_json(normalized)
            except (CanonicalError, UnicodeError, RecursionError) as exc:
                raise PartitionError(
                    f"partition {name} is not canonical-wire encodable"
                ) from exc
            object.__setattr__(self, name, normalized)

    def __str__(self) -> str:
        return f"{self.venue_model}|{self.canonical_instrument_id}|{self.semantic_timeframe}"


class PartitionError(RuntimeError):
    """Single-writer or ordering violation. Fail closed."""


@dataclass
class PartitionCoordinator:
    """Grants exactly one writer per partition and hands out monotonic sequence numbers."""

    _owner: dict[PartitionKey, str] = field(default_factory=dict)
    _seq: dict[PartitionKey, int] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def claim(self, key: PartitionKey, writer_id: str) -> None:
        if not isinstance(key, PartitionKey):
            raise PartitionError("partition claim requires a canonical PartitionKey")
        writer_id = _canonical_writer_id(writer_id)
        with self._lock:
            current = self._owner.get(key)
            if current is not None and current != writer_id:
                raise PartitionError(
                    f"partition {key} already owned by {current!r}; two writers not permitted")
            self._owner[key] = writer_id
            self._seq.setdefault(key, -1)

    def next_seq(self, key: PartitionKey, writer_id: str) -> int:
        if not isinstance(key, PartitionKey):
            raise PartitionError("partition sequence requires a canonical PartitionKey")
        writer_id = _canonical_writer_id(writer_id)
        with self._lock:
            if self._owner.get(key) != writer_id:
                raise PartitionError(f"{writer_id!r} does not own partition {key}")
            self._seq[key] += 1
            return self._seq[key]


def _canonical_writer_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PartitionError("partition writer_id must be a non-empty string")
    normalized = nfc(value)
    try:
        canonical_json(normalized)
    except (CanonicalError, UnicodeError, RecursionError) as exc:
        raise PartitionError("partition writer_id is not canonical-wire encodable") from exc
    return normalized


def deterministic_order(events: list[dict]) -> list[dict]:
    """Order by recorded local receipt, with sequence numbers scoped to their source.

    Sequence values from different connections are incomparable. Local monotonic receipt is the
    cross-source order; source identity and receive sequence only break an equal-receipt tie. A
    receive-sequence regression within one source is rejected instead of silently fabricating a
    causal order.
    """
    def _key(e: dict) -> tuple:
        body = _event_body(e)
        return (
            _required_int(body, "local_receipt_mono_ns"),
            _source_key(body),
            _required_int(body, "receive_sequence"),
            _required_str(body, "raw_event_id"),
        )

    unique: list[dict] = []
    seen: set[bytes] = set()
    for event in events:
        if not isinstance(event, dict):
            raise PartitionError("ordered input event must be an object")
        try:
            encoded = canonical_json(event)
        except CanonicalError as exc:
            raise PartitionError("ordered input event is not canonical") from exc
        if encoded in seen:
            continue  # exact retransmission is idempotent
        seen.add(encoded)
        normalized = loads_canonical(encoded)
        if not isinstance(normalized, dict):  # pragma: no cover - guarded above
            raise PartitionError("ordered input event must be an object")
        unique.append(normalized)

    ordered = sorted(unique, key=_key)
    last_receive: dict[tuple[str, str, str, int], int] = {}
    for event in ordered:
        body = _event_body(event)
        source = _source_key(body)
        receive = _required_int(body, "receive_sequence")
        prior = last_receive.get(source)
        if prior is not None and receive <= prior:
            raise PartitionError(
                f"receive_sequence regression for source {source}: {receive} <= {prior}")
        last_receive[source] = receive
    return ordered


def _event_body(event: dict) -> dict:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else event


def _required(body: dict, name: str):
    value = body.get(name)
    if value is None or value == "":
        raise PartitionError(f"event missing required ordering field {name!r}")
    return value


def _required_int(body: dict, name: str) -> int:
    value = _required(body, name)
    try:
        if isinstance(value, bool):
            raise CanonicalError("boolean is not an ordering integer")
        if isinstance(value, int):
            tick_to_str(value)  # signed-int64 boundary
            parsed = value
        elif isinstance(value, str):
            parsed = str_to_tick(value)
        else:
            raise CanonicalError(f"unsupported ordering type {type(value).__name__}")
    except CanonicalError as exc:
        raise PartitionError(f"ordering field {name!r} is not an integer: {value!r}") from exc
    if name in {"connection_epoch", "receive_sequence", "local_receipt_mono_ns"} and parsed < 0:
        raise PartitionError(f"ordering field {name!r} must be non-negative: {value!r}")
    return parsed


def _required_str(body: dict, name: str) -> str:
    value = _required(body, name)
    if not isinstance(value, str):
        raise PartitionError(f"ordering field {name!r} is not a string: {value!r}")
    return value


def _source_key(body: dict) -> tuple[str, str, str, int]:
    return (
        _required_str(body, "venue"),
        _required_str(body, "route_family"),
        _required_str(body, "source_stream"),
        _required_int(body, "connection_epoch"),
    )


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

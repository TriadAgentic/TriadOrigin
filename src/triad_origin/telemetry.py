"""Evidence telemetry: funnel counters and named zero reasons (MOD-019, Doc 05 §05.11).

Bounded-cardinality only: labels are service, contract major, topic, capsule, symbol capability
group, state/reason enum, arm and environment. Event/order/candidate IDs never become metric labels.
A capsule that produces no candidate emits a **named zero reason**, not silence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from threading import RLock

from .canonical import INT64_MAX, CanonicalError, canonical_json, nfc

# The capsule funnel stages (Doc 05 §05.11): examine -> atom -> confirmation -> touch ->
# candidate -> withdraw.
FUNNEL_STAGES = ("examined", "formations", "confirmations", "touches", "invalidations",
                 "candidates", "withdrawals")

# A closed set of named zero reasons — silence is never a result (Doc 02 §02.14).
ZERO_REASONS = (
    "WARMUP_INCOMPLETE",
    "PARTITION_NOT_READY",
    "NO_ELIGIBLE_STRUCTURE",
    "DEPARTURE_NOT_MET",
    "FRESH_FLOW_MISSING",
    "RR_BELOW_FLOOR",
    "FIRST_TOUCH_CONSUMED",
    "DATA_INVALID",
    "PARAMETER_ABSENT",
)
MAX_SERIES = 4_096
MAX_KEY_LABELS = 8
MAX_LABEL_LENGTH = 128


class TelemetryError(ValueError):
    pass


@dataclass
class EvidenceTelemetry:
    """Pure accumulation of bounded funnel/zero-reason counters. No clock, no I/O."""

    _funnel: Counter = field(default_factory=Counter)
    _zero: Counter = field(default_factory=Counter)
    max_series: int = MAX_SERIES
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_series, bool)
            or not isinstance(self.max_series, int)
            or not 1 <= self.max_series <= MAX_SERIES
        ):
            raise TelemetryError(f"max_series must be an integer in 1..{MAX_SERIES}")

    def bump(self, stage: str, key: tuple[str, ...], n: int = 1) -> None:
        if stage not in FUNNEL_STAGES:
            raise TelemetryError(f"unknown funnel stage: {stage}")
        normalized = _validate_key_and_count(key, n)
        series = (stage, *normalized)
        with self._lock:
            self._reserve_series(self._funnel, series)
            if self._funnel[series] > INT64_MAX - n:
                raise TelemetryError("telemetry counter would overflow signed-int64")
            self._funnel[series] += n

    def zero(self, reason: str, key: tuple[str, ...], n: int = 1) -> None:
        if reason not in ZERO_REASONS:
            raise TelemetryError(f"unknown zero reason: {reason} (silence is never a result)")
        normalized = _validate_key_and_count(key, n)
        series = (reason, *normalized)
        with self._lock:
            self._reserve_series(self._zero, series)
            if self._zero[series] > INT64_MAX - n:
                raise TelemetryError("telemetry counter would overflow signed-int64")
            self._zero[series] += n

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {
                "funnel": {_encode_key(k): v for k, v in sorted(self._funnel.items())},
                "zero_reasons": {_encode_key(k): v for k, v in sorted(self._zero.items())},
            }

    def _reserve_series(self, counter: Counter, series: tuple[str, ...]) -> None:
        if series in counter:
            return
        if len(self._funnel) + len(self._zero) >= self.max_series:
            raise TelemetryError("telemetry series cardinality limit reached")


def _validate_key_and_count(key: tuple[str, ...], n: int) -> tuple[str, ...]:
    if not isinstance(key, tuple) or not key or len(key) > MAX_KEY_LABELS:
        raise TelemetryError("telemetry key must be a non-empty tuple")
    if any(
        not isinstance(label, str) or not label or len(label) > MAX_LABEL_LENGTH
        for label in key
    ):
        raise TelemetryError("telemetry labels must be bounded non-empty strings")
    if isinstance(n, bool) or not isinstance(n, int) or not 0 < n <= INT64_MAX:
        raise TelemetryError("telemetry increment must be a positive integer")
    normalized = tuple(nfc(label) for label in key)
    try:
        canonical_json(normalized)
    except (CanonicalError, UnicodeError, RecursionError) as exc:
        raise TelemetryError("telemetry labels must be canonical-wire encodable") from exc
    return normalized


def _encode_key(key: tuple[str, ...]) -> str:
    """Injective canonical encoding; label delimiters can never collide or overwrite."""
    return canonical_json(list(key)).decode("utf-8")

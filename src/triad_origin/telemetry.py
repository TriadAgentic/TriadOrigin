"""Evidence telemetry: funnel counters and named zero reasons (MOD-019, Doc 05 §05.11).

Bounded-cardinality only: labels are service, contract major, topic, capsule, symbol capability
group, state/reason enum, arm and environment. Event/order/candidate IDs never become metric labels.
A capsule that produces no candidate emits a **named zero reason**, not silence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

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


class TelemetryError(ValueError):
    pass


@dataclass
class EvidenceTelemetry:
    """Pure accumulation of bounded funnel/zero-reason counters. No clock, no I/O."""

    _funnel: Counter = field(default_factory=Counter)
    _zero: Counter = field(default_factory=Counter)

    def bump(self, stage: str, key: tuple[str, ...], n: int = 1) -> None:
        if stage not in FUNNEL_STAGES:
            raise TelemetryError(f"unknown funnel stage: {stage}")
        self._funnel[(stage, *key)] += n

    def zero(self, reason: str, key: tuple[str, ...], n: int = 1) -> None:
        if reason not in ZERO_REASONS:
            raise TelemetryError(f"unknown zero reason: {reason} (silence is never a result)")
        self._zero[(reason, *key)] += n

    def snapshot(self) -> dict[str, dict]:
        return {
            "funnel": {"|".join(map(str, k)): v for k, v in sorted(self._funnel.items())},
            "zero_reasons": {"|".join(map(str, k)): v for k, v in sorted(self._zero.items())},
        }

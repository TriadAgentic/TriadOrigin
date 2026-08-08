"""Contract ingress boundary gate (MOD-001, Doc 03 §03.1, Doc 05 §05.4).

Every authoritative event validates at the consuming boundary. Unknown/invalid/stale input never
defaults: it is rejected and a ``quarantine_record.v1`` is produced with a raw reference (no
fabricated normalization). Authority-path events are additionally fenced by producer epoch per
scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import contracts
from .canonical import canonical_json, sha256_hex


@dataclass
class Accepted:
    event: dict
    epoch: int | None


@dataclass
class Quarantined:
    record: dict  # a triad.quarantine_record.v1 event body


@dataclass
class ContractIngress:
    """Validates + fences incoming events at a boundary, quarantining anything unsafe."""

    boundary: str
    _epoch: dict[str, int] = field(default_factory=dict)

    def ingest(
        self,
        event: dict,
        *,
        expected_schema: str | None = None,
        fence_scope: str | None = None,
        observed_at_us: int = 0,
    ) -> Accepted | Quarantined:
        try:
            contracts.validate(event, schema_id=expected_schema)
        except contracts.ContractError as exc:
            return self._quarantine(event, str(exc), observed_at_us)

        epoch: int | None = None
        schema_id = event.get("schema", "")
        if fence_scope is not None or "producer_epoch" in event:
            scope = fence_scope or schema_id
            try:
                epoch = contracts.assert_epoch_ge(event, self._epoch.get(scope, -1))
            except contracts.StaleEpochError as exc:
                return self._quarantine(event, str(exc), observed_at_us)
            self._epoch[scope] = epoch

        return Accepted(event=event, epoch=epoch)

    def _quarantine(self, event: Any, reason: str, observed_at_us: int) -> Quarantined:
        try:
            raw = canonical_json(event) if isinstance(event, dict) else str(event).encode()
        except (TypeError, ValueError):
            # Quarantine must remain available for non-canonical input. Only the digest is exposed.
            raw = repr(event).encode("utf-8", errors="backslashreplace")
        digest = sha256_hex(raw)
        record = {
            "quarantine_id": "qtn_" + digest[:40],
            "source": str(event.get("producer_service") or "unknown") if isinstance(event, dict) else "unknown",
            "boundary": self.boundary,
            "raw_reference": "sha256:" + digest,
            "rejection_reason": reason,
            "contract_id": str(event.get("schema") or "unknown") if isinstance(event, dict) else "unknown",
            "observed_at_us": observed_at_us,
        }
        contracts.validate_payload("triad.quarantine_record.v1", record)
        return Quarantined(record=record)

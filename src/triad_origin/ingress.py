"""Contract ingress boundary gate (MOD-001, Doc 03 §03.1, Doc 05 §05.4).

Every authoritative event validates at the consuming boundary. Unknown/invalid/stale input never
defaults: it is rejected and a ``quarantine_record.v1`` is produced with a raw reference (no
fabricated normalization). Authority-path events are additionally fenced by producer epoch per
scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from . import contracts
from .canonical import (
    INT64_MAX,
    CanonicalError,
    canonical_json,
    loads_canonical,
    nfc,
    sha256_hex,
)


@dataclass(frozen=True)
class Accepted:
    _event_canonical: bytes
    epoch: int | None

    @property
    def event(self) -> dict:
        value = loads_canonical(self._event_canonical)
        if not isinstance(value, dict):  # pragma: no cover - constructor invariant
            raise RuntimeError("accepted event snapshot is not an object")
        return value


@dataclass(frozen=True)
class Quarantined:
    _record_canonical: bytes

    @property
    def record(self) -> dict:
        value = loads_canonical(self._record_canonical)
        if not isinstance(value, dict):  # pragma: no cover - constructor invariant
            raise RuntimeError("quarantine snapshot is not an object")
        return value


@dataclass(frozen=True)
class ContractIngress:
    """Validates + fences incoming events at a boundary, quarantining anything unsafe."""

    boundary: str
    _epoch: dict[str, int] = field(default_factory=dict, init=False, repr=False, compare=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "boundary",
            _strict_metadata_text(self.boundary, label="ingress boundary"),
        )

    def ingest(
        self,
        event: dict,
        *,
        expected_schema: str | None = None,
        fence_scope: str | None = None,
        observed_at_us: int = 0,
    ) -> Accepted | Quarantined:
        safe_observed_at = _safe_observed_at(observed_at_us)
        if safe_observed_at is None:
            return self._quarantine(
                event,
                "observed_at_us must be a non-negative signed-int64 integer",
                0,
            )
        try:
            encoded = canonical_json(event)
            normalized = loads_canonical(encoded)
            if not isinstance(normalized, dict):  # pragma: no cover - canonicalized event type
                raise CanonicalError("event root must be an object")
            contracts.validate(normalized, schema_id=expected_schema)
        except (CanonicalError, UnicodeError, RecursionError, contracts.ContractError) as exc:
            return self._quarantine(event, str(exc), safe_observed_at)

        epoch: int | None = None
        schema_id = normalized.get("schema", "")
        if fence_scope is not None or "producer_epoch" in normalized:
            try:
                scope = _strict_metadata_text(
                    fence_scope if fence_scope is not None else schema_id,
                    label="fence scope",
                )
            except ValueError:
                return self._quarantine(
                    normalized,
                    "fence scope must be a canonical non-empty string",
                    safe_observed_at,
                )
            # The epoch check and high-water update are one atomic operation. Concurrent lower
            # epochs can never overwrite a previously accepted higher epoch.
            with self._lock:
                try:
                    epoch = contracts.assert_epoch_ge(normalized, self._epoch.get(scope, -1))
                except contracts.StaleEpochError as exc:
                    return self._quarantine(normalized, str(exc), safe_observed_at)
                self._epoch[scope] = epoch

        # Return a canonical deep copy, never an alias to caller-owned mutable input.
        return Accepted(_event_canonical=canonical_json(normalized), epoch=epoch)

    def _quarantine(self, event: Any, reason: str, observed_at_us: int) -> Quarantined:
        try:
            raw = canonical_json(event)
        except (TypeError, ValueError, UnicodeError, RecursionError):
            # Quarantine must remain available for non-canonical input. Only the digest is exposed.
            try:
                raw = repr(event).encode("utf-8", errors="backslashreplace")
            except (TypeError, ValueError, UnicodeError, RecursionError):
                raw = b"unrepresentable-input"
        digest = sha256_hex(raw)
        source = event.get("producer_service") if isinstance(event, dict) else None
        contract_id = event.get("schema") if isinstance(event, dict) else None
        record = {
            "quarantine_id": "qtn_" + digest[:40],
            "source": _safe_metadata_text(source, fallback="unknown"),
            "boundary": self.boundary,
            "raw_reference": "sha256:" + digest,
            "rejection_reason": _safe_metadata_text(
                reason, fallback="non-canonical input rejected", limit=512
            ),
            "contract_id": _safe_metadata_text(contract_id, fallback="unknown"),
            "observed_at_us": observed_at_us,
        }
        contracts.validate_payload("triad.quarantine_record.v1", record)
        return Quarantined(_record_canonical=canonical_json(record))


def _strict_metadata_text(value: Any, *, label: str, limit: int = 256) -> str:
    """Return bounded NFC text that is itself canonical-wire encodable."""
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ValueError(f"{label} must be a non-empty string of at most {limit} characters")
    normalized = nfc(value)
    try:
        canonical_json(normalized)
    except CanonicalError as exc:
        raise ValueError(f"{label} is not canonical-wire encodable") from exc
    return normalized


def _safe_metadata_text(value: Any, *, fallback: str, limit: int = 256) -> str:
    try:
        return _strict_metadata_text(value, label="quarantine metadata", limit=limit)
    except ValueError:
        return fallback


def _safe_observed_at(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value > INT64_MAX:
        return None
    return value

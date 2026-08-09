"""Verify-only producer-lease fencing at the E02 boundary (CON-023 / Doc 04 §04.16).

Deploy is not authority. An E02-owned topic is written only by the holder of a scoped producer
lease carrying a **monotonic fencing token**. This in-process verifier tracks the highest accepted
token per scope and rejects lower/expired/revoked tokens even when a later-timestamped payload
arrives — clock ordering never beats fencing. Durable per-scope restore remains a B02 blocker;
ORIGIN never issues, activates, coordinates, or supersedes a lease, which are external governance
responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock

from .canonical import INT64_MAX, CanonicalError, canonical_json, nfc


class LeaseState(str, Enum):
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class Lease:
    lease_id: str
    scope: str
    producer_service: str
    producer_instance_id: str
    fencing_token: int
    activation_manifest_id: str
    state: LeaseState


@dataclass
class ConsumerFence:
    """A consumer's per-scope fence for already validated external leases.

    Lease acceptance advances only to a structurally valid, externally activated token. Writes
    must then carry that exact accepted token: an unseen higher value is not authority.
    """

    _highest: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _revoked: set[str] = field(default_factory=set, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def accept(self, lease: Lease) -> bool:
        """Fence an externally validated active lease; this method never issues authority."""
        if not isinstance(lease, Lease):
            return False
        if lease.state is not LeaseState.ACTIVE:
            return False
        text_fields = (
            lease.lease_id,
            lease.scope,
            lease.producer_service,
            lease.producer_instance_id,
            lease.activation_manifest_id,
        )
        if (
            not all(_canonical_nonempty_text(value) is not None for value in text_fields)
            or isinstance(lease.fencing_token, bool)
            or not isinstance(lease.fencing_token, int)
            or lease.fencing_token <= 0
            or lease.fencing_token > INT64_MAX
        ):
            return False
        # A revocation is terminal for this verifier instance. Re-authorizing a scope requires a
        # separately ratified, cryptographically verified replacement path, which is blocked by
        # B00 and intentionally absent from this repository today.
        scope = _canonical_nonempty_text(lease.scope)
        assert scope is not None  # checked above
        with self._lock:
            if scope in self._revoked:
                return False
            highest = self._highest.get(scope, 0)
            if lease.fencing_token <= highest:
                return False  # stale epoch; reject even if it "arrives later"
            self._highest[scope] = lease.fencing_token
            return True

    def revoke(self, scope: str) -> None:
        normalized = _canonical_nonempty_text(scope)
        if normalized is None:
            return
        with self._lock:
            self._revoked.add(normalized)

    def export_state(self) -> dict:
        """Closed, canonical per-scope fence state for checkpoint sealing (CTRL-B02-002)."""
        with self._lock:
            return {
                "highest": dict(sorted(self._highest.items())),
                "revoked": sorted(self._revoked),
            }

    def restore_state(self, state: dict) -> None:
        """Restore a sealed fence state before any consumption. Fail closed on any malformation.

        Restore is only lawful onto a fresh fence — merging into a live fence could silently
        lower a high-water mark.
        """
        if not isinstance(state, dict) or set(state) != {"highest", "revoked"}:
            raise ValueError("fence state must be exactly {'highest', 'revoked'}")
        highest = state["highest"]
        revoked = state["revoked"]
        if not isinstance(highest, dict) or not isinstance(revoked, list):
            raise ValueError("fence state field types are wrong")
        for scope, token in highest.items():
            if _canonical_nonempty_text(scope) is None:
                raise ValueError(f"fence scope is not canonical text: {scope!r}")
            if isinstance(token, bool) or not isinstance(token, int) or not (
                    0 < token <= INT64_MAX):
                raise ValueError(f"fence token out of domain for scope {scope!r}")
        for scope in revoked:
            if _canonical_nonempty_text(scope) is None:
                raise ValueError(f"revoked scope is not canonical text: {scope!r}")
        with self._lock:
            if self._highest or self._revoked:
                raise ValueError("fence state restore requires a fresh fence")
            self._highest.update({scope: token for scope, token in highest.items()})
            self._revoked.update(revoked)

    def accepts_write(self, scope: str, fencing_token: int) -> bool:
        """Accept only the exact token of an active lease previously accepted for ``scope``."""
        normalized = _canonical_nonempty_text(scope)
        if normalized is None:
            return False
        if isinstance(fencing_token, bool) or not isinstance(fencing_token, int):
            return False
        with self._lock:
            if normalized in self._revoked:
                return False
            accepted = self._highest.get(normalized)
            return accepted is not None and fencing_token == accepted


def _canonical_nonempty_text(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 256:
        return None
    normalized = nfc(value)
    try:
        canonical_json(normalized)
    except (CanonicalError, UnicodeError, RecursionError):
        return None
    return normalized

"""Verify-only producer-lease fencing at the E02 boundary (CON-023 / Doc 04 §04.16).

Deploy is not authority. An E02-owned topic is written only by the holder of a scoped producer
lease carrying a **monotonic fencing token**. Consumers persist the highest accepted token per scope
and reject lower/expired/revoked tokens even when a later-timestamped payload arrives — clock
ordering never beats fencing. ORIGIN never issues, activates, coordinates, or supersedes a lease;
those are external governance responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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

    def with_state(self, state: LeaseState) -> "Lease":
        return Lease(self.lease_id, self.scope, self.producer_service, self.producer_instance_id,
                     self.fencing_token, self.activation_manifest_id, state)


@dataclass
class ConsumerFence:
    """A consumer's per-scope fence. Accepts only strictly-higher tokens (Doc 04 §04.16)."""

    _highest: dict[str, int] = field(default_factory=dict)
    _revoked: set[str] = field(default_factory=set)

    def accept(self, lease: Lease) -> bool:
        """Fence an externally validated active lease; this method never issues authority."""
        if lease.state is not LeaseState.ACTIVE:
            return False
        # A revocation is terminal for this verifier instance. Re-authorizing a scope requires a
        # separately ratified, cryptographically verified replacement path, which is blocked by
        # B00 and intentionally absent from this repository today.
        if lease.scope in self._revoked:
            return False
        highest = self._highest.get(lease.scope, 0)
        if lease.fencing_token <= highest:
            return False  # stale epoch; reject even if it "arrives later"
        self._highest[lease.scope] = lease.fencing_token
        return True

    def revoke(self, scope: str) -> None:
        self._revoked.add(scope)

    def accepts_write(self, scope: str, fencing_token: int) -> bool:
        """Would a message stamped with ``fencing_token`` be accepted for ``scope``?"""
        if scope in self._revoked:
            return False
        return fencing_token >= self._highest.get(scope, 0) and fencing_token > 0

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


@dataclass
class ConsumerFence:
    """A consumer's per-scope fence for already validated external leases.

    Lease acceptance advances only to a structurally valid, externally activated token. Writes
    must then carry that exact accepted token: an unseen higher value is not authority.
    """

    _highest: dict[str, int] = field(default_factory=dict)
    _revoked: set[str] = field(default_factory=set)

    def accept(self, lease: Lease) -> bool:
        """Fence an externally validated active lease; this method never issues authority."""
        if lease.state is not LeaseState.ACTIVE:
            return False
        if (
            not all(
                isinstance(value, str) and bool(value)
                for value in (
                    lease.lease_id,
                    lease.scope,
                    lease.producer_service,
                    lease.producer_instance_id,
                    lease.activation_manifest_id,
                )
            )
            or isinstance(lease.fencing_token, bool)
            or not isinstance(lease.fencing_token, int)
            or lease.fencing_token <= 0
        ):
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
        """Accept only the exact token of an active lease previously accepted for ``scope``."""
        if scope in self._revoked:
            return False
        if isinstance(fencing_token, bool) or not isinstance(fencing_token, int):
            return False
        accepted = self._highest.get(scope)
        return accepted is not None and fencing_token == accepted

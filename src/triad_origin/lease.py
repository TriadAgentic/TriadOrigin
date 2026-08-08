"""Producer lease and fencing machine (CON-023 / Doc 04 §04.16).

Deploy is not authority. A candidate/money topic is written only by the holder of a scoped producer
lease carrying a **monotonic fencing token**. Consumers persist the highest accepted token per scope
and reject lower/expired/revoked tokens even when a later-timestamped payload arrives — clock
ordering never beats fencing. A restart never inherits a lease; a replacement requests a strictly
higher token.
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


class LeaseError(RuntimeError):
    pass


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
class LeaseCoordinator:
    """Issues strictly monotonic fencing tokens per authority scope."""

    _highest: dict[str, int] = field(default_factory=dict)
    _active: dict[str, Lease] = field(default_factory=dict)
    _counter: int = 0

    def issue(self, scope: str, producer_service: str, producer_instance_id: str,
              activation_manifest_id: str) -> Lease:
        token = self._highest.get(scope, 0) + 1
        self._highest[scope] = token
        self._counter += 1
        lease = Lease(
            lease_id=f"lease_{self._counter}",
            scope=scope,
            producer_service=producer_service,
            producer_instance_id=producer_instance_id,
            fencing_token=token,
            activation_manifest_id=activation_manifest_id,
            state=LeaseState.ISSUED,
        )
        return lease

    def activate(self, lease: Lease) -> Lease:
        prior = self._active.get(lease.scope)
        if prior is not None and prior.fencing_token >= lease.fencing_token:
            raise LeaseError("cannot activate a lease with a non-greater token")
        active = lease.with_state(LeaseState.ACTIVE)
        self._active[lease.scope] = active
        return active

    def revoke(self, scope: str) -> Lease | None:
        active = self._active.get(scope)
        if active is None:
            return None
        revoked = active.with_state(LeaseState.REVOKED)
        del self._active[scope]
        return revoked

    def supersede(self, scope: str, producer_service: str, producer_instance_id: str,
                  activation_manifest_id: str) -> Lease:
        """Rollback/promotion: revoke the entry authority, then issue a strictly higher token."""
        self.revoke(scope)
        return self.activate(self.issue(scope, producer_service, producer_instance_id,
                                        activation_manifest_id))


@dataclass
class ConsumerFence:
    """A consumer's per-scope fence. Accepts only strictly-higher tokens (Doc 04 §04.16)."""

    _highest: dict[str, int] = field(default_factory=dict)
    _revoked: set[str] = field(default_factory=set)

    def accept(self, lease: Lease) -> bool:
        """Return True iff this lease may write its scope now; persist the token if so."""
        if lease.state in (LeaseState.REVOKED, LeaseState.EXPIRED, LeaseState.SUPERSEDED):
            return False
        if lease.scope in self._revoked and lease.fencing_token <= self._highest.get(lease.scope, 0):
            return False
        highest = self._highest.get(lease.scope, 0)
        if lease.fencing_token <= highest:
            return False  # stale epoch; reject even if it "arrives later"
        self._highest[lease.scope] = lease.fencing_token
        self._revoked.discard(lease.scope)
        return True

    def revoke(self, scope: str) -> None:
        self._revoked.add(scope)

    def accepts_write(self, scope: str, fencing_token: int) -> bool:
        """Would a message stamped with ``fencing_token`` be accepted for ``scope``?"""
        if scope in self._revoked:
            return fencing_token > self._highest.get(scope, 0)
        return fencing_token >= self._highest.get(scope, 0) and fencing_token > 0

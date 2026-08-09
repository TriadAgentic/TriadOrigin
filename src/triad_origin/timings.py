"""RC4 deterministic timing law (the 17 declared bounds).

The RC4 Four-Plane/Lever addendum declares exact timing bounds for lever caching, control
polling, OFF-transition deadlines, attestation freshness, shadow persistence/health, private
state freshness, producer-lease cadence and clock skew. This module is the ONE in-repo source of
those values, drift-locked against the vendored RC4 control bundle
(``docs/control/rc4_control_bundle.json``) by test.

Consumers receive values (or ages computed by callers) as plain integers — nothing here reads a
clock, and nothing on the semantic path may. A missing/unknown bound is a hard error: timing law
is never defaulted silently (the no-hidden-experiment rule applied to time).
"""

from __future__ import annotations

TIMINGS_VERSION = "rc4-timings.v1"

# Values are UTC-agnostic durations in milliseconds (RC4 addendum, issued 2026-08-09).
_RC4_TIMINGS_MS = {
    "clock_skew_max_ms": 250,
    "control_poll_interval_ms": 1000,
    "environment_attestation_max_age_ms": 60000,
    "environment_drain_review_interval_ms": 1000,
    "environment_drain_timeout_ms": 300000,
    "lever_cache_max_age_ms": 2000,
    "off_entry_block_deadline_ms": 2000,
    "post_change_side_effect_audit_ms": 900000,
    "private_state_max_age_ms": 5000,
    "producer_lease_renew_interval_ms": 5000,
    "producer_lease_ttl_ms": 15000,
    "runtime_attestation_interval_ms": 5000,
    "runtime_attestation_max_age_ms": 15000,
    "shadow_health_heartbeat_interval_ms": 1000,
    "shadow_health_max_age_ms": 5000,
    "shadow_rejection_persist_deadline_ms": 100,
    "shadow_resolver_backlog_max_age_ms": 60000,
}

def timings_ms() -> dict:
    """A fresh copy of the full timing table (callers cannot mutate the law)."""
    return dict(_RC4_TIMINGS_MS)


# Read-only view for equality checks; treat as immutable (the capability gate bans the types
# import, so immutability is by convention + the copy accessor above).
TIMINGS_MS = _RC4_TIMINGS_MS


class TimingError(KeyError):
    """An unknown timing bound was requested — fail closed, never default."""


def timing_ms(name: str) -> int:
    """Return the declared bound in milliseconds; unknown names fail closed."""
    try:
        return TIMINGS_MS[name]
    except KeyError as exc:
        raise TimingError(f"unknown RC4 timing bound: {name!r}") from exc


def is_stale(age_ms: int, bound_name: str) -> bool:
    """Pure staleness predicate: the caller supplies the age; nothing here reads a clock.

    A negative age (clock inversion upstream) is stale by definition — an unbelievable clock is
    never fresh.
    """
    if isinstance(age_ms, bool) or not isinstance(age_ms, int):
        raise TimingError("age_ms must be an int")
    if age_ms < 0:
        return True
    return age_ms > timing_ms(bound_name)

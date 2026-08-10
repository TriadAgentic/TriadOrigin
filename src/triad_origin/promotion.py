"""Deny-capable promotion verifier (B01C-ID-01/ID-02, plan §4.4).

Promotion is **verification only** — nothing in this module arms a system, sets a lever, contacts a
venue, or grants activation. ``verify_promotion`` returns a verdict whose ``activation_result`` is
the invariant :data:`~triad_origin.governance.ACTIVATION_RESULT` (``DENIED_SAFE_HOLD``) on every
path, PASS or REFUSE. This plan authorizes neither TESTNET nor LIVE; the verifier can only REFUSE.

Two projections are checked (plan §4.4):

* the **environment-invariant projection** — the closed :data:`INVARIANT_FIELDS` set of build /
  config / contract / binding / strategy / adapter-lifecycle / instrument / SBOM / authority /
  trust-registry / registry digests. Full equality against a projection bound by a current PASS
  proving receipt; a present-but-failed, stale, wrong-scope, or differently-bound receipt is
  refused (ID-01).
* the **environment-specific projections** — the closed :data:`ENVIRONMENT_FIELDS` set. Distinct
  environments may never reuse an account, credential reference, or route
  (:data:`ISOLATED_ENV_IDENTITY_FIELDS`) — TESTNET and destination mappings stay isolated (ID-02).

The wire contracts for these projections (``invariant_projection.v1`` / ``environment_projection.v1``
/ ``promotion_verdict.v1``) ride the single corrective contract-train (WP-B01C-02) once the B00R
ledger root validates; this module's closed field sets track plan §4.4 and reconcile with them.

Deterministic, keyless, side-effect-free. No lever, venue, or credential import (DARK boundary).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import governance
from .canonical import canonical_json, is_sha256_hex, sha256_hex

# The environment-INVARIANT material (plan §4.4). Equal across every environment; a change here is a
# new build, never a promotion. Each value is a strict lowercase-hex sha256 (B01C-CON-05).
INVARIANT_FIELDS = (
    "build_artifact_digest",
    "config_bundle_digest",
    "contract_manifest_digest",
    "binding_bundle_digest",
    "strategy_digest",
    "adapter_lifecycle_digest",
    "instrument_semantics_digest",
    "sbom_digest",
    "authority_policy_digest",
    "trust_registry_digest",
    "registry_digest",
)

# The environment-SPECIFIC mapping (plan §4.4). Bound per environment, never folded into the
# invariant identity.
ENVIRONMENT_FIELDS = (
    "venue_environment",
    "account_id",
    "credential_reference",
    "endpoint",
    "transport",
    "route",
)

# Identities that MUST NOT be reused across two distinct environments — TESTNET/destination
# isolation. A shared account, credential, or route between environments is refused.
ISOLATED_ENV_IDENTITY_FIELDS = ("account_id", "credential_reference", "route")

ACTIVATION_RESULT = governance.ACTIVATION_RESULT  # DENIED_SAFE_HOLD — invariant on every path.


@dataclass(frozen=True)
class PromotionVerdict:
    """The pure result of a promotion verification. ``activation_result`` is always denied.

    ``verified`` True means the invariant projection is provably bound to a current PASS proving
    receipt AND every supplied environment mapping is isolated — it is NOT an activation grant.
    Activation remains the operator's signed ceremony; this verdict sets no lever and touches no
    venue.
    """

    verified: bool
    reason: str
    activation_result: str = ACTIVATION_RESULT


def _refuse(reason: str) -> PromotionVerdict:
    return PromotionVerdict(verified=False, reason=reason)


def invariant_projection_digest(invariant_projection: dict) -> str:
    """Canonical sha256 of a well-formed invariant projection (fail closed on shape)."""
    _assert_closed_digest_map(invariant_projection, INVARIANT_FIELDS, "invariant_projection")
    return sha256_hex(canonical_json(dict(sorted(invariant_projection.items()))))


def _assert_closed_digest_map(node: object, fields: tuple[str, ...], where: str) -> None:
    if not isinstance(node, dict):
        raise governance.GovernanceError(f"{where}_NOT_OBJECT")
    keys = set(node)
    missing = set(fields) - keys
    extra = keys - set(fields)
    if missing:
        raise governance.GovernanceError(f"{where}_MISSING_FIELDS:{sorted(missing)}")
    if extra:
        raise governance.GovernanceError(f"{where}_EXTRA_FIELDS:{sorted(extra)}")
    for field in fields:
        if not is_sha256_hex(node[field]):
            raise governance.GovernanceError(f"{where}_FIELD_NOT_HEX64:{field}")


def _assert_environment_projection(node: object, where: str) -> None:
    if not isinstance(node, dict):
        raise governance.GovernanceError(f"{where}_NOT_OBJECT")
    keys = set(node)
    missing = set(ENVIRONMENT_FIELDS) - keys
    extra = keys - set(ENVIRONMENT_FIELDS)
    if missing:
        raise governance.GovernanceError(f"{where}_MISSING_FIELDS:{sorted(missing)}")
    if extra:
        raise governance.GovernanceError(f"{where}_EXTRA_FIELDS:{sorted(extra)}")
    for field in ENVIRONMENT_FIELDS:
        value = node[field]
        if not isinstance(value, str) or value == "" or "*" in value:
            raise governance.GovernanceError(f"{where}_FIELD_INVALID:{field}")


def verify_environment_isolation(environments: dict) -> PromotionVerdict:
    """Refuse any account/credential/route reuse across two distinct environments (ID-02, §4.4).

    ``environments`` maps an environment name to its :data:`ENVIRONMENT_FIELDS` projection. Each
    projection is closed and non-empty; a shared isolated identity between two distinct environments
    is refused by name. A single environment trivially passes.
    """
    if not isinstance(environments, dict) or not environments:
        return _refuse("ENVIRONMENTS_EMPTY")
    try:
        for name, projection in sorted(environments.items()):
            _assert_environment_projection(projection, f"environment[{name}]")
    except governance.GovernanceError as exc:
        return _refuse(str(exc))
    for field in ISOLATED_ENV_IDENTITY_FIELDS:
        seen: dict[str, str] = {}
        for name, projection in sorted(environments.items()):
            value = projection[field]
            prior = seen.get(value)
            if prior is not None and prior != name:
                return _refuse(
                    f"CROSS_ENVIRONMENT_IDENTITY_REUSE:{field}={value!r} in {prior!r} and {name!r}")
            seen[value] = name
    return PromotionVerdict(verified=True, reason="ENVIRONMENTS_ISOLATED")


def verify_promotion(
    *,
    invariant_projection: dict,
    proving_receipt: dict,
    milestone: str,
    trust: dict[str, dict] | None = None,
    environments: dict | None = None,
    threshold: int = 2,
    required_roles: tuple[str, ...] = ("EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER"),
    now_us: int | None = None,
    verify_fn=None,
) -> PromotionVerdict:
    """Deny-capable promotion verification. Activation is denied on every path.

    A verified result requires ALL of:

    * a well-formed invariant projection (exactly :data:`INVARIANT_FIELDS`, each strict hex64);
    * a proving receipt that :func:`~triad_origin.governance.validate_receipt_v3` rules
      ``PASS_REPOSITORY_SAFE_HOLD`` for ``milestone`` (status / result / signature / trust /
      validity window / scope / chronology / ancestry) — anything else (FAIL/BLOCKED/UNAVAILABLE)
      refuses with that reason (ID-01);
    * the receipt BINDS this exact projection: its ``evidence_sha256s`` contains the projection's
      canonical digest — a PASS receipt that proves a different projection is refused (ID-01);
    * every supplied environment mapping is isolated (ID-02, §4.4).

    The verifier sets no lever and contacts no venue; even a verified verdict is only permission for
    a separate signed activation ceremony, never an activation itself.
    """
    try:
        digest = invariant_projection_digest(invariant_projection)
    except governance.GovernanceError as exc:
        return _refuse(str(exc))

    result, reason = governance.validate_receipt_v3(
        proving_receipt, milestone=milestone, trust=trust, threshold=threshold,
        required_roles=required_roles, now_us=now_us, verify_fn=verify_fn)
    if result != governance.RESULT_PASS:
        return _refuse(f"PROVING_RECEIPT_NOT_PASS:{result}:{reason}")

    evidence = proving_receipt.get("payload", {}).get("evidence_sha256s")
    if not isinstance(evidence, list) or digest not in evidence:
        return _refuse("PROVING_RECEIPT_DOES_NOT_BIND_INVARIANT_PROJECTION")

    if environments is not None:
        isolation = verify_environment_isolation(environments)
        if not isolation.verified:
            return isolation

    return PromotionVerdict(verified=True, reason="OK")

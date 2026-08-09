"""The signed, multi-domain configuration bundle (B07 milestone deliverable bullet 1).

Materializes a content-addressed **signed configuration bundle** covering the thirteen domains
named by the B07 milestone text verbatim, in order: capsules, geometry, lifecycle, regime
eligibility, symbols, staleness, timing, selected-policy references, transport bindings,
compatibility, treatment/rollback, secrets allowlist, and exact four-plane manifest
(:data:`DOMAINS`).

Two domains are genuinely **contract-shaped** in this repository rather than scalar-parameter
rows — compatibility (:data:`triad.compatibility_manifest.v1`) and the exact four-plane manifest
(:data:`triad.engine_control_manifest.v2`, already built in B01/B05) — and are referenced by
contract id rather than forced into a fictional parameter mapping.

Every other domain is anchored to a **minimum verified set** of :mod:`triad_origin.config.parameters`
rows, hand-checked against the source bundle's own ``name``/``category``/``formula_refs`` text
(:data:`DOMAIN_ANCHORS`). This is deliberately **not** claimed as an exhaustive classification of
all 192 rows — this repository's own law is "no guessed ... mapping" (CLAUDE.md, on an analogous
capsule-ordinal question); an under-complete, explicitly-labelled anchor set is honest, a
force-fit complete one would not be. See ``docs/plan/09_OPEN_QUESTIONS.md`` row E25 for the
disposition record.

``build_signed_bundle`` is a pure function: it reads only its ``registry``/``contract_registry``
arguments, performs no clock/I/O/network, and returns a content-addressed, self-signing envelope
(the same blank-signature-field-then-hash pattern used by the B-series evidence receipts) — every
domain names both its MATERIALIZED members (id + value) and its PENDING/REFUSED members (id +
status), never a silent omission.
"""

from __future__ import annotations

from ..canonical import canonical_json, sha256_hex
from . import parameters as _parameters

# The thirteen domains, verbatim order from the B07 milestone deliverable text.
DOMAINS = (
    "capsules",
    "geometry",
    "lifecycle",
    "regime_eligibility",
    "symbols",
    "staleness",
    "timing",
    "selected_policy_references",
    "transport_bindings",
    "compatibility",
    "treatment_rollback",
    "secrets_allowlist",
    "exact_four_plane_manifest",
)

# Domains anchored to specific parameter ids (hand-verified against name/category/formula_refs —
# see the module docstring). A domain absent here (or with an empty tuple) has no verified
# parameter-row anchor; that is an honest fact, not a defect.
DOMAIN_ANCHORS: dict[str, tuple[str, ...]] = {
    "capsules": ("PAR-118", "PAR-174", "PAR-175", "PAR-176", "PAR-177", "PAR-178"),
    "geometry": ("PAR-045", "PAR-061", "PAR-172", "PAR-173"),
    "lifecycle": ("PAR-051", "PAR-162", "PAR-163"),
    "regime_eligibility": ("PAR-042", "PAR-109", "PAR-178"),
    "symbols": ("PAR-026", "PAR-027", "PAR-110", "PAR-119"),
    "staleness": ("PAR-016", "PAR-017", "PAR-018", "PAR-128"),
    "timing": ("PAR-003", "PAR-004", "PAR-019", "PAR-020", "PAR-065", "PAR-083", "PAR-092",
               "PAR-144"),
    "selected_policy_references": (),  # contract-shaped: see DOMAIN_CONTRACTS
    "transport_bindings": ("PAR-013", "PAR-014", "PAR-015", "PAR-149", "PAR-150", "PAR-151",
                            "PAR-152"),
    "compatibility": (),  # contract-shaped: see DOMAIN_CONTRACTS
    "treatment_rollback": ("PAR-009", "PAR-088", "PAR-116", "PAR-125", "RC3-PAR-EXP-001",
                            "RC3-PAR-EXP-002"),
    "secrets_allowlist": ("PAR-129", "PAR-130", "PAR-131", "PAR-132", "PAR-133", "PAR-134",
                           "PAR-135", "PAR-136", "PAR-137", "PAR-138", "RC3-PAR-MCP-001"),
    "exact_four_plane_manifest": (),  # contract-shaped: see DOMAIN_CONTRACTS
}

# Domains that are genuinely contract-shaped (a whole vendored schema, not a scalar parameter).
DOMAIN_CONTRACTS: dict[str, tuple[str, ...]] = {
    "selected_policy_references": ("triad.decision.v2",),
    "compatibility": ("triad.compatibility_manifest.v1",),
    "exact_four_plane_manifest": ("triad.engine_control_manifest.v2",
                                   "triad.runtime_lever_registry.v1"),
}

BUNDLE_VERSION = "origin.signed_config_bundle.b07.v1"


class SignedBundleError(RuntimeError):
    """The signed configuration bundle could not be built — fail closed, never a partial bundle."""


def _domain_view(registry: "_parameters.ParameterRegistry", domain: str) -> dict:
    materialized: dict[str, dict] = {}
    pending: dict[str, str] = {}
    for pid in DOMAIN_ANCHORS.get(domain, ()):
        row = registry.row(pid)  # raises ParameterUnknownError if the anchor id is itself wrong
        if row["status"] in _parameters.MATERIALIZABLE_STATUSES:
            materialized[pid] = row
        else:
            pending[pid] = row["status"]
    return {
        "materialized": dict(sorted(materialized.items())),
        "pending": dict(sorted(pending.items())),
        "referenced_contracts": list(DOMAIN_CONTRACTS.get(domain, ())),
    }


def build_signed_bundle(
    registry: "_parameters.ParameterRegistry",
    known_contract_ids: frozenset,
) -> dict:
    """Build the signed, content-addressed, thirteen-domain configuration bundle.

    ``known_contract_ids`` (e.g. ``frozenset(triad_origin.contracts.known_contracts())``) is
    checked so a domain can never reference a contract id that does not exist in the registry —
    a stale/typo'd contract reference fails the whole build closed, never silently.
    """
    unknown_contracts = sorted(
        cid for ids in DOMAIN_CONTRACTS.values() for cid in ids if cid not in known_contract_ids)
    if unknown_contracts:
        raise SignedBundleError(
            f"signed bundle references unknown contract ids: {unknown_contracts}")
    domains = {}
    for domain in DOMAINS:
        domains[domain] = _domain_view(registry, domain)
    unsigned = {
        "bundle_version": BUNDLE_VERSION,
        "parameter_digest": registry.parameter_digest,
        "domains": dict(sorted(domains.items())),
        "signature": "",
    }
    signature = sha256_hex(canonical_json(unsigned))
    signed = dict(unsigned)
    signed["signature"] = signature
    return signed


def verify_signed_bundle(bundle: dict) -> bool:
    """Recompute the bundle's own content-addressed signature and compare (never trust, recompute)."""
    if not isinstance(bundle, dict) or "signature" not in bundle:
        return False
    unsigned = dict(bundle)
    claimed = unsigned.pop("signature")
    unsigned["signature"] = ""
    return sha256_hex(canonical_json(unsigned)) == claimed

"""RC4 lever/refusal/combination law — the ONE in-repo source of the four-plane lever vocabulary.

Drift-locked against the vendored RC4 addendum (``docs/control/rc4_control_bundle.json``
``lever_law``/``refusals`` sections, LEV-0001..LEV-0047 §L0/§L2) by test — this module never
restates a number the bundle already carries; it is the code that ACTS on those numbers.

**The four canonical fields** (frozen, never a generic "mode" — LEV-0004): ``venue_environment``
(``LIVE``/``TESTNET``/``OFF``), ``venue_activation`` (``LIVE``/``OFF``), ``paper_activation``
(``LIVE``/``OFF``), ``shadow_activation`` (``LIVE`` — the ONE user-unswitchable field; RC4's
``SHADOW_CAPTURE_OFF_FORBIDDEN``). Values are **exact, case-sensitive, uncoerced strings** — the
35-member :data:`INVALID_ALIASES` set (``"live"``, ``"1"``, ``"DARK"``, ``""``, ``"null"``, …) is
refused by name, never silently normalized (LEV-0004: ``aliases: false``, ``coercion: false``,
``trim_input: false``).

**The 32 refusal codes** (:data:`REFUSAL_CODES`, LEV-0011 "register every refusal code and bind
it to alert/incident/receipt semantics") each carry a ``meaning`` and a ``minimum_action`` — the
exact narrowing the estate's own ARM-02 doctrine calls "fix-forward-while-armed": a refusal NEVER
disarms `shadow_activation` (SHADOW is the one always-on population, ratified LEV-0002) and NEVER
widens; it only ever forces `venue_activation`/`paper_activation` toward ``OFF`` for the affected
scope while existing exit/reconciliation/protection authority is explicitly preserved.

**Refusal-code reachability is honestly split** (recorded per-code in :data:`REFUSAL_SCOPE`):

* ``EVENT_LOCAL`` — decidable from one manifest/attestation payload alone; :func:`resolve_manifest`
  implements every one of these directly, in the RC4-declared priority order (first-failing wins).
* ``STATEFUL_IN_REPO`` — decidable from ORIGIN's own owned state (the append-only lever registry,
  the SHADOW/PAPER ledgers, the declared :mod:`triad_origin.timings` bounds); implemented in the
  sibling :mod:`triad_origin.control` modules that own that state, each importing
  :data:`REFUSAL_CODES`/:func:`containment_action` from here rather than re-deriving them.
* ``EXTERNAL_EVIDENCE`` — the refusal names a fact this repository does not itself observe (open
  venue exposure, venue-effect reconciliation, opposite-environment reachability — E08/E09/venue
  truth, ``REFERENCE_ONLY``/``OUT_OF_REPO`` per this repo's own CLAUDE.md ownership law). This
  module still REGISTERS the code, its meaning, and its containment action (LEV-0011 is satisfied
  for the registration half); classifying whether it FIRES requires an explicit, named boolean the
  caller supplies (never inferred, never defaulted) — see :func:`classify_external_refusal`.

No code here reads a wall clock, opens a socket, or holds a credential (Doc 04 §04.17).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ACTIVATION_ENUM = ("LIVE", "OFF")
VENUE_ENVIRONMENT_ENUM = ("LIVE", "TESTNET", "OFF")
SHADOW_ACTIVATION_ENUM = ("LIVE",)

# The RC4-declared 35 forbidden lever-slot values (LEV-0004/LEV-0047). Exact strings, exact case.
INVALID_ALIASES = frozenset({
    "live", "testnet", "off", "ON", "ENABLED", "DISABLED", "TRUE", "FALSE", "true", "false",
    "1", "0", "DARK", "SHADOW", "PAPER", "DRYRUN", "DRY-RUN", "SIMULATED", "SIMULATION", "CANARY",
    "PRODUCTION", "PROD", "DEV", "STAGE", "ARMED", "DISARMED", "OPERATIONAL", "execution",
    "small_live", "PILOT", "log", "enforce", "trigger_veto", "", "null",
})

# The RC4-declared 10 valid (venue_environment, venue_activation, paper_activation) combinations.
# shadow_activation is always "LIVE" and is not itself a combination axis (LEV-0002/LEV-0005).
VALID_COMBINATIONS = (
    {"venue_environment": "LIVE", "venue_activation": "LIVE", "paper_activation": "LIVE"},
    {"venue_environment": "LIVE", "venue_activation": "LIVE", "paper_activation": "OFF"},
    {"venue_environment": "LIVE", "venue_activation": "OFF", "paper_activation": "LIVE"},
    {"venue_environment": "LIVE", "venue_activation": "OFF", "paper_activation": "OFF"},
    {"venue_environment": "TESTNET", "venue_activation": "LIVE", "paper_activation": "LIVE"},
    {"venue_environment": "TESTNET", "venue_activation": "LIVE", "paper_activation": "OFF"},
    {"venue_environment": "TESTNET", "venue_activation": "OFF", "paper_activation": "LIVE"},
    {"venue_environment": "TESTNET", "venue_activation": "OFF", "paper_activation": "OFF"},
    {"venue_environment": "OFF", "venue_activation": "OFF", "paper_activation": "LIVE"},
    {"venue_environment": "OFF", "venue_activation": "OFF", "paper_activation": "OFF"},
)

# The RC4-required non-authoritative baseline (master plan field order): OFF/OFF/OFF/LIVE.
BASELINE_MANIFEST = {
    "venue_environment": "OFF", "venue_activation": "OFF", "paper_activation": "OFF",
    "shadow_activation": "LIVE",
}

_OFF_SCOPE_ACTION = {
    "venue_activation": "OFF", "paper_activation": None, "shadow_activation": "LIVE",
}
_BOTH_OFF_SCOPE_ACTION = {
    "venue_activation": "OFF", "paper_activation": "OFF", "shadow_activation": "LIVE",
}
_QUARANTINE_ACTION = {
    "venue_activation": "OFF", "paper_activation": "OFF", "shadow_activation": "LIVE",
    "quarantine": True,
}
_REJECT_LOCAL_ACTION = {
    "reject_record": True, "shadow_activation": "LIVE", "widen_execution_activation": False,
}

# REFUSAL_CODES: code -> {"meaning": str, "minimum_action": dict}. Byte-identical to the vendored
# RC4 ``refusals`` list (drift-locked by test) with the ``minimum_action`` PROSE compiled into the
# structured containment dict every consumer applies via :func:`containment_action`.
REFUSAL_CODES: dict[str, dict[str, Any]] = {
    "VENUE_ENVIRONMENT_VALUE_INVALID": {
        "meaning": "venue_environment is missing or not exactly LIVE, TESTNET, or OFF.",
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "VENUE_ACTIVATION_VALUE_INVALID": {
        "meaning": "venue_activation is missing or not exactly LIVE or OFF.",
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "PAPER_ACTIVATION_VALUE_INVALID": {
        "meaning": "paper_activation is missing or not exactly LIVE or OFF.",
        "minimum_action": {"paper_activation": "OFF", "venue_activation": None,
                           "shadow_activation": "LIVE"},
    },
    "ACTIVATION_VALUE_INVALID": {
        "meaning": ("A registered component or feature activation is missing or not exactly "
                    "LIVE or OFF."),
        "minimum_action": _BOTH_OFF_SCOPE_ACTION,
    },
    "SCOPE_VALUE_INVALID": {
        "meaning": "A manifest scope is missing, malformed, contains a wildcard, or is not exact.",
        "minimum_action": _BOTH_OFF_SCOPE_ACTION,
    },
    "OFF_WITH_LIVE_VENUE_ACTIVATION": {
        "meaning": "venue_environment OFF is paired with venue_activation LIVE.",
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "OFF_TRANSITION_EXPOSURE_REMAINS": {
        "meaning": ("venue_environment OFF requested while positions, orders, reservations, or "
                    "protection lifecycle remain."),
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "LIVE_TESTNET_BINDING_FORBIDDEN": {
        "meaning": ("LIVE record contains any testnet endpoint, account, credential, order, "
                    "fill, ledger, or route."),
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "TESTNET_LIVE_BINDING_FORBIDDEN": {
        "meaning": ("TESTNET record contains any live endpoint, account, credential, order, "
                    "fill, ledger, or route."),
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN": {
        "meaning": "One activation/evidence bundle contains both LIVE and TESTNET members.",
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN": {
        "meaning": ("LIVE↔TESTNET transition did not pass through OFF activation, "
                    "reconciliation, flatness, isolation, and OFF environment."),
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "LIVE_PROMOTION_RECEIPT_MISSING": {
        "meaning": ("LIVE activation lacks a current successful TESTNET promotion receipt for "
                    "the same build, contracts, strategy, scope, and venue lifecycle."),
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "LEGACY_LEVER_ALIAS_FORBIDDEN": {
        "meaning": ("A legacy word, boolean, integer, blank, null, or coercion was supplied to a "
                    "canonical lever slot."),
        "minimum_action": _BOTH_OFF_SCOPE_ACTION,
    },
    "LEVER_REGISTRY_INCOMPLETE": {
        "meaning": "A required component or feature is absent, duplicated, unknown, or not digest-bound.",
        "minimum_action": _BOTH_OFF_SCOPE_ACTION,
    },
    "RUNTIME_LEVER_ATTESTATION_MISMATCH": {
        "meaning": "Runtime readback differs from the signed manifest or accepted revision.",
        "minimum_action": _BOTH_OFF_SCOPE_ACTION,
    },
    "LEVER_REVISION_STALE": {
        "meaning": "A command, lease, route, or runtime readback carries a superseded revision.",
        "minimum_action": _BOTH_OFF_SCOPE_ACTION,
    },
    "PRODUCER_LEASE_MISSING": {
        "meaning": "Non-OFF authority lacks one current fenced producer lease for the exact scope.",
        "minimum_action": _BOTH_OFF_SCOPE_ACTION,
    },
    "PRODUCER_LEASE_CONFLICT": {
        "meaning": "More than one non-OFF producer claims an overlapping scope.",
        "minimum_action": _BOTH_OFF_SCOPE_ACTION,
    },
    "VENUE_ENVIRONMENT_UNVERIFIED": {
        "meaning": "Venue/account environment cannot be verified from authoritative venue evidence.",
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "VENUE_BINDING_MISMATCH": {
        "meaning": ("Top-level environment or scope differs from the manifest venue/account/route "
                    "binding."),
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "OPPOSITE_ENVIRONMENT_REACHABLE": {
        "meaning": "The engine instance can reach both LIVE and TESTNET authority surfaces.",
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "PRIVATE_STATE_STALE": {
        "meaning": "Order, position, or protection truth exceeds the declared freshness bound.",
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "UNKNOWN_SUBMIT_UNRECONCILED": {
        "meaning": ("A venue submit has unknown effect and cannot be classified as rejected or "
                    "routed to SHADOW until private-state reconciliation proves zero venue "
                    "effect."),
        "minimum_action": _OFF_SCOPE_ACTION,
    },
    "SHADOW_CAPTURE_OFF_FORBIDDEN": {
        "meaning": "An attempt was made to set mandatory shadow capture to OFF.",
        "minimum_action": _REJECT_LOCAL_ACTION,
    },
    "SHADOW_REJECTION_NOT_PERSISTED": {
        "meaning": ("A shadow-tradeable REJECTED candidate was not durably persisted to the "
                    "SHADOW recorder inside the deadline."),
        "minimum_action": _QUARANTINE_ACTION,
    },
    "SHADOW_HEALTH_STALE": {
        "meaning": ("The mandatory SHADOW writer heartbeat or processable resolver watermark "
                    "exceeds its declared freshness bound."),
        "minimum_action": _QUARANTINE_ACTION,
    },
    "SHADOW_UNTRADEABLE": {
        "meaning": ("An event or candidate fails the shadow-tradeability contract and is "
                    "recorded without fabricating geometry or a trade."),
        "minimum_action": _REJECT_LOCAL_ACTION,
    },
    "SHADOW_LINEAGE_INCOMPLETE": {
        "meaning": ("Candidate, rejection, shadow trade, resolver, or outcome lineage is missing "
                    "or ambiguous."),
        "minimum_action": _QUARANTINE_ACTION,
    },
    "SHADOW_MONEY_CONTAMINATION": {
        "meaning": ("Shadow evidence contains a venue money fact or a money metric combines "
                    "shadow and venue populations."),
        "minimum_action": _QUARANTINE_ACTION,
    },
    "PAPER_VENUE_EFFECT_FORBIDDEN": {
        "meaning": "A PAPER record, credential, route, or command can reach a venue effect.",
        "minimum_action": _QUARANTINE_ACTION,
    },
    "PAPER_LEDGER_CONTAMINATION": {
        "meaning": ("PAPER demo facts were combined with SHADOW, TESTNET, or LIVE outcome/PnL "
                    "denominators."),
        "minimum_action": {"reject_aggregation": True, "paper_activation": "OFF",
                           "shadow_activation": "LIVE"},
    },
    "ACCEPTED_CANDIDATE_UNRECORDED": {
        "meaning": ("A complete accepted candidate reached neither PAPER nor venue and has no "
                    "SHADOW non-execution record."),
        "minimum_action": _QUARANTINE_ACTION,
    },
}

# Reachability class per code — see the module docstring's three-way split.
REFUSAL_SCOPE: dict[str, str] = {
    "VENUE_ENVIRONMENT_VALUE_INVALID": "EVENT_LOCAL",
    "VENUE_ACTIVATION_VALUE_INVALID": "EVENT_LOCAL",
    "PAPER_ACTIVATION_VALUE_INVALID": "EVENT_LOCAL",
    "ACTIVATION_VALUE_INVALID": "EVENT_LOCAL",
    "SCOPE_VALUE_INVALID": "EVENT_LOCAL",
    "OFF_WITH_LIVE_VENUE_ACTIVATION": "EVENT_LOCAL",
    "OFF_TRANSITION_EXPOSURE_REMAINS": "EXTERNAL_EVIDENCE",
    "LIVE_TESTNET_BINDING_FORBIDDEN": "EVENT_LOCAL",
    "TESTNET_LIVE_BINDING_FORBIDDEN": "EVENT_LOCAL",
    "MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN": "EVENT_LOCAL",
    "DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN": "STATEFUL_IN_REPO",
    "LIVE_PROMOTION_RECEIPT_MISSING": "EVENT_LOCAL",
    "LEGACY_LEVER_ALIAS_FORBIDDEN": "EVENT_LOCAL",
    "LEVER_REGISTRY_INCOMPLETE": "STATEFUL_IN_REPO",
    "RUNTIME_LEVER_ATTESTATION_MISMATCH": "STATEFUL_IN_REPO",
    "LEVER_REVISION_STALE": "STATEFUL_IN_REPO",
    "PRODUCER_LEASE_MISSING": "STATEFUL_IN_REPO",
    "PRODUCER_LEASE_CONFLICT": "STATEFUL_IN_REPO",
    "VENUE_ENVIRONMENT_UNVERIFIED": "EXTERNAL_EVIDENCE",
    "VENUE_BINDING_MISMATCH": "EVENT_LOCAL",
    "OPPOSITE_ENVIRONMENT_REACHABLE": "EXTERNAL_EVIDENCE",
    "PRIVATE_STATE_STALE": "EXTERNAL_EVIDENCE",
    "UNKNOWN_SUBMIT_UNRECONCILED": "EXTERNAL_EVIDENCE",
    "SHADOW_CAPTURE_OFF_FORBIDDEN": "EVENT_LOCAL",
    "SHADOW_REJECTION_NOT_PERSISTED": "STATEFUL_IN_REPO",
    "SHADOW_HEALTH_STALE": "STATEFUL_IN_REPO",
    "SHADOW_UNTRADEABLE": "EVENT_LOCAL",
    "SHADOW_LINEAGE_INCOMPLETE": "EVENT_LOCAL",
    "SHADOW_MONEY_CONTAMINATION": "EVENT_LOCAL",
    "PAPER_VENUE_EFFECT_FORBIDDEN": "EVENT_LOCAL",
    "PAPER_LEDGER_CONTAMINATION": "STATEFUL_IN_REPO",
    "ACCEPTED_CANDIDATE_UNRECORDED": "STATEFUL_IN_REPO",
}

assert set(REFUSAL_CODES) == set(REFUSAL_SCOPE), "every refusal code must carry a reachability class"


class LeverLawError(ValueError):
    """A lever-law usage error (an unknown refusal code, a malformed evidence input)."""


@dataclass(frozen=True)
class LeverResolution:
    """The outcome of :func:`resolve_manifest`: accepted, or the first-failing named refusal."""

    accepted: bool
    refusal_code: str | None = None
    meaning: str | None = None
    minimum_action: dict | None = None


def _accepted() -> LeverResolution:
    return LeverResolution(accepted=True)


def _refused(code: str) -> LeverResolution:
    row = REFUSAL_CODES[code]
    return LeverResolution(
        accepted=False, refusal_code=code, meaning=row["meaning"],
        minimum_action=dict(row["minimum_action"]))


def is_valid_lever_value(value: object) -> bool:
    """Exact-string, case-sensitive membership in {"LIVE", "OFF"} — no aliasing, no coercion."""
    return isinstance(value, str) and value in ACTIVATION_ENUM


def is_invalid_alias(value: object) -> bool:
    return isinstance(value, str) and value in INVALID_ALIASES


def _wildcard_or_blank(value: object) -> bool:
    if isinstance(value, str):
        return value == "" or "*" in value
    if isinstance(value, dict):
        return not value or any(_wildcard_or_blank(v) for v in value.values())
    if isinstance(value, list):
        return len(value) == 0 or any(_wildcard_or_blank(v) for v in value)
    return value is None


def resolve_manifest(payload: dict) -> LeverResolution:
    """Apply the full EVENT_LOCAL refusal law to one ``engine_control_manifest.v2``-shaped payload.

    First-failing code wins, in the RC4-declared priority order (value validity before
    combination law before binding/receipt cross-checks). Every STATEFUL_IN_REPO/EXTERNAL_EVIDENCE
    code is registered in :data:`REFUSAL_CODES` but is never raised here — see the module
    docstring's reachability split; sibling modules that own that state call
    :func:`refuse` directly with the applicable code.
    """
    if not isinstance(payload, dict):
        raise LeverLawError("manifest payload must be an object")

    venue_environment = payload.get("venue_environment")
    venue_activation = payload.get("venue_activation")
    paper_activation = payload.get("paper_activation")
    shadow_activation = payload.get("shadow_activation")

    if venue_environment not in VENUE_ENVIRONMENT_ENUM or is_invalid_alias(venue_environment):
        return _refused("VENUE_ENVIRONMENT_VALUE_INVALID")
    if not is_valid_lever_value(venue_activation):
        return _refused("VENUE_ACTIVATION_VALUE_INVALID")
    if not is_valid_lever_value(paper_activation):
        return _refused("PAPER_ACTIVATION_VALUE_INVALID")
    if shadow_activation != "LIVE":
        return _refused("SHADOW_CAPTURE_OFF_FORBIDDEN")

    activations = payload.get("activations")
    if activations is not None:
        if not isinstance(activations, dict):
            return _refused("ACTIVATION_VALUE_INVALID")
        for value in activations.values():
            if not is_valid_lever_value(value):
                return _refused("ACTIVATION_VALUE_INVALID")

    scope = payload.get("scope")
    if scope is not None and _wildcard_or_blank(scope):
        return _refused("SCOPE_VALUE_INVALID")

    combo = {"venue_environment": venue_environment, "venue_activation": venue_activation,
             "paper_activation": paper_activation}
    if combo not in VALID_COMBINATIONS:
        # Every remaining structurally-valid-but-unlisted combination is exactly the
        # OFF-paired-with-LIVE-venue-activation shape (the only axis VALID_COMBINATIONS excludes).
        return _refused("OFF_WITH_LIVE_VENUE_ACTIVATION")

    venue_binding = payload.get("venue_binding")
    if isinstance(venue_binding, dict):
        binding_env = venue_binding.get("environment")
        if binding_env is not None and binding_env != venue_environment:
            return _refused("VENUE_BINDING_MISMATCH")
        if venue_environment == "LIVE" and _binding_names_testnet(venue_binding):
            return _refused("LIVE_TESTNET_BINDING_FORBIDDEN")
        if venue_environment == "TESTNET" and _binding_names_live(venue_binding):
            return _refused("TESTNET_LIVE_BINDING_FORBIDDEN")

    if venue_environment == "LIVE" and venue_activation == "LIVE":
        receipt = payload.get("testnet_promotion_receipt")
        if not isinstance(receipt, dict) or not receipt:
            return _refused("LIVE_PROMOTION_RECEIPT_MISSING")

    return _accepted()


_TESTNET_BINDING_KEYS = ("testnet_endpoint", "testnet_account", "testnet_credential",
                        "testnet_order", "testnet_fill", "testnet_ledger", "testnet_route")
_LIVE_BINDING_KEYS = ("live_endpoint", "live_account", "live_credential", "live_order",
                     "live_fill", "live_ledger", "live_route")


def _binding_names_testnet(binding: dict) -> bool:
    return any(k in _TESTNET_BINDING_KEYS for k in binding)


def _binding_names_live(binding: dict) -> bool:
    return any(k in _LIVE_BINDING_KEYS for k in binding)


def refuse(code: str) -> LeverResolution:
    """Build the named refusal for a STATEFUL_IN_REPO/EXTERNAL_EVIDENCE code (sibling modules)."""
    if code not in REFUSAL_CODES:
        raise LeverLawError(f"unknown refusal code: {code!r}")
    return _refused(code)


def classify_external_refusal(code: str, fired: bool) -> LeverResolution | None:
    """The EXTERNAL_EVIDENCE codes: the caller states the fact explicitly (never inferred).

    Returns the named refusal when ``fired`` is True, else ``None`` (accepted-by-this-check).
    Raises if ``code`` is not registered as EXTERNAL_EVIDENCE — the honest-scope law extends to
    the classifier itself.
    """
    if REFUSAL_SCOPE.get(code) != "EXTERNAL_EVIDENCE":
        raise LeverLawError(f"{code!r} is not an EXTERNAL_EVIDENCE refusal code")
    if not isinstance(fired, bool):
        raise LeverLawError("fired must be an explicit bool — never inferred")
    return _refused(code) if fired else None


def containment_action(refusal_code: str, current: dict) -> dict:
    """Apply the named refusal's minimum_action to ``current`` (a four-plane manifest dict).

    NARROWING only: ``shadow_activation`` is never touched away from ``LIVE``; a ``None`` action
    value means "leave this field as the caller's current value" (some refusals narrow only one
    axis, e.g. PAPER_ACTIVATION_VALUE_INVALID leaves venue_activation untouched).
    """
    if refusal_code not in REFUSAL_CODES:
        raise LeverLawError(f"unknown refusal code: {refusal_code!r}")
    action = REFUSAL_CODES[refusal_code]["minimum_action"]
    result = dict(current)
    for key, value in action.items():
        if key in ("venue_environment", "venue_activation", "paper_activation",
                   "shadow_activation") and value is not None:
            result[key] = value
        elif key not in ("venue_environment", "venue_activation", "paper_activation",
                        "shadow_activation"):
            result[key] = value
    result["shadow_activation"] = "LIVE"
    return result

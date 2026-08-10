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

* ``EVENT_LOCAL`` — decidable from one manifest/attestation/bundle payload alone. The per-manifest
  ones (value/alias validity · the combination law · the venue_binding cross-checks · the LIVE/LIVE
  promotion receipt) are raised directly by :func:`resolve_manifest` in the RC4 canonical evaluation
  order (parse exact bytes → validate closed enums → validate the venue pair → binding → receipt;
  first-failing wins). The cross-MEMBER one — ``MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN`` — is raised by
  :func:`resolve_bundle` over a bundle of members (a single manifest whose ``venue_binding`` itself
  names both a live_* and a testnet_* member is also caught in :func:`resolve_manifest`). The
  ``SHADOW_*``/``PAPER_*`` event-local codes are raised by the sibling SHADOW/PAPER ledger that owns
  that event stream (e.g. ``SHADOW_MONEY_CONTAMINATION`` in :mod:`shadow_ledger`,
  ``PAPER_VENUE_EFFECT_FORBIDDEN`` in :mod:`paper_ledger`), each importing :data:`REFUSAL_CODES`
  from here rather than re-deriving the vocabulary.
* ``STATEFUL_IN_REPO`` — decidable from ORIGIN's own owned state (the append-only lever registry,
  the SHADOW/PAPER ledgers, the declared :mod:`triad_origin.timings` bounds). The lever-registry
  ones (``DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN``, ``LEVER_REGISTRY_INCOMPLETE``,
  ``RUNTIME_LEVER_ATTESTATION_MISMATCH``, ``LEVER_REVISION_STALE``) are raised by
  :mod:`lever_registry`; the SHADOW-freshness/persistence ones by :mod:`shadow_ledger`/
  :mod:`shadow_health`. ``PAPER_LEDGER_CONTAMINATION`` and ``ACCEPTED_CANDIDATE_UNRECORDED`` name
  cross-population aggregation / coverage state that only a COMPOSING driver observes (the PAPER
  ledger owns one population and never reads another's — LEV-0084); they are registered here
  (LEV-0011) but stay registration-only until that composing surface exists.
* ``EXTERNAL_EVIDENCE`` — the refusal names a fact this repository does not itself observe (open
  venue exposure, venue-effect reconciliation, opposite-environment reachability, and the producer
  LEASE facts — the lease coordinator/durable fencing ledger is ``OUT_OF_REPO`` per this repo's own
  CLAUDE.md ownership law, so ``PRODUCER_LEASE_MISSING``/``PRODUCER_LEASE_CONFLICT`` are external
  facts, not in-repo state — E08/E09/venue/governance truth). This module still REGISTERS the code,
  its meaning, and its containment action (LEV-0011 is satisfied for the registration half);
  classifying whether it FIRES requires an explicit, named boolean the caller supplies (never
  inferred, never defaulted) — see :func:`classify_external_refusal`.

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

# The four frozen canonical lever field names (LEV-0004) — the ONE in-repo list a reserved-key
# guard (lever_registry) and :func:`containment_action` both read, never a re-typed literal.
CANONICAL_LEVER_FIELDS = (
    "venue_environment", "venue_activation", "paper_activation", "shadow_activation",
)

# venue_environment's two "population" words: they ARE members of :data:`INVALID_ALIASES`, but on
# the venue_environment slot specifically the RC4 field-enum law (LEV-V-0062/0063: "SHADOW/PAPER is
# a population, not a venue environment value") resolves them ``VENUE_ENVIRONMENT_VALUE_INVALID``,
# not ``LEGACY_LEVER_ALIAS_FORBIDDEN``. On any OTHER canonical slot they stay legacy aliases.
_ENV_POPULATION_VALUES = frozenset({"SHADOW", "PAPER"})

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
    # The lease coordinator / durable fencing ledger is OUT_OF_REPO (this repo's CLAUDE.md
    # ownership law + docs/plan/02_TRACEABILITY): overlapping-scope prevention at issuance is the
    # coordinator's, and different-scope overlap is undetectable from ORIGIN's own equal-token
    # split-brain latch. These are therefore EXTERNAL_EVIDENCE facts the caller supplies, not
    # in-repo state — reachable via :func:`classify_external_refusal` (COV-7 reconciliation).
    "PRODUCER_LEASE_MISSING": "EXTERNAL_EVIDENCE",
    "PRODUCER_LEASE_CONFLICT": "EXTERNAL_EVIDENCE",
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


def _slot_refusal(payload: dict, key: str, enum: tuple, value_invalid_code: str) -> str | None:
    """Classify one canonical lever slot in the RC4 canonical evaluation order (§04): parse exact
    bytes (do NOT trim, case-fold, alias, coerce, or default) BEFORE validating the closed enum.

    * a missing key is the field's own ``*_VALUE_INVALID`` (the code's meaning: "missing or not
      exactly …" — never treated as a JSON-null alias);
    * a PRESENT non-string (JSON ``true``/``1``/``null``) is a coercion attempt →
      ``LEGACY_LEVER_ALIAS_FORBIDDEN`` (LEV-V-0047..0055);
    * a string carrying leading/trailing whitespace would need trimming →
      ``LEGACY_LEVER_ALIAS_FORBIDDEN`` (LEV-V-0056..0059);
    * a string that is a known legacy alias/word/blank/null →
      ``LEGACY_LEVER_ALIAS_FORBIDDEN`` (LEV-V-0012..0046), EXCEPT the venue_environment population
      carve-out (SHADOW/PAPER → ``VENUE_ENVIRONMENT_VALUE_INVALID``, LEV-V-0062/0063);
    * a well-formed string simply not in the field's closed enum is the field's ``*_VALUE_INVALID``
      (e.g. ``TESTNET`` on an activation slot — LEV-V-0060/0061).

    Returns the first-failing refusal code for this slot, or ``None`` when the value is exactly a
    member of ``enum``.
    """
    if key not in payload:
        return value_invalid_code
    value = payload[key]
    if not isinstance(value, str):
        return "LEGACY_LEVER_ALIAS_FORBIDDEN"
    if value != value.strip():
        return "LEGACY_LEVER_ALIAS_FORBIDDEN"
    if value in INVALID_ALIASES and not (
        key == "venue_environment" and value in _ENV_POPULATION_VALUES
    ):
        return "LEGACY_LEVER_ALIAS_FORBIDDEN"
    if value not in enum:
        return value_invalid_code
    return None


_RECEIPT_PASS_RESULTS = ("PASS", "SUCCESS")
# The manifest digest/scope fields a TESTNET promotion receipt must equal for LIVE/LIVE (LEV-0042).
_RECEIPT_EQUALITY_FIELDS = (
    "build_commit", "build_digest", "scope", "config_bundle_sha256", "contract_manifest_sha256",
    "parameter_digest", "strategy_digest", "adapter_digest", "registry_digest",
)


def _promotion_receipt_ok(payload: dict, receipt: dict) -> bool:
    """LEV-0042 / LEV-V-0074/0075/0085/0086/0087: the in-repo, honest-null half of the LIVE/LIVE
    promotion-receipt gate. RC4 semantic_rules[2] / refusals[11] / LEV-0042 require a *current
    successful same-digest* TESTNET promotion receipt for LIVE activation; that full binding — an
    AFFIRMATIVE PASS result AND equality against EVERY manifest-declared digest/scope — is the
    operator/estate **G-8/G-9 same-digest TESTNET certificate + production-risk signing** (an
    EXTERNAL_EVIDENCE gate, out of ORIGIN's scope: ORIGIN never activates, activation_result is
    always ``DENIED_SAFE_HOLD``). See ``docs/plan/09_OPEN_QUESTIONS.md`` E43 and
    ``docs/plan/08_BUILD_CHECKLIST.md`` G-8/G-9.

    What THIS predicate enforces (additive + honest-null, deliberately a subset so the receipt is
    never asked to match a digest the manifest does not itself carry): a receipt whose PROVIDED
    ``result`` is present and not a PASS/SUCCESS, OR whose PROVIDED digest/scope field disagrees
    with a digest the manifest DOES declare, OR that is expired against a provided evaluation clock,
    refuses ``LIVE_PROMOTION_RECEIPT_MISSING``. It does NOT, in-repo, demand an affirmative result
    or force digest presence — a receipt object's presence is the in-repo gate; the affirmative
    same-digest binding is the out-of-repo estate certificate above. This honest-null subset is
    pinned by ``tests/control/test_lever_law.py`` and the ``e2e_audit.py`` lever walk.
    """
    result = receipt.get("result")
    if result is not None and result not in _RECEIPT_PASS_RESULTS:
        return False
    for field in _RECEIPT_EQUALITY_FIELDS:
        if field in payload and field in receipt and payload[field] != receipt[field]:
            return False
    expires_at = receipt.get("expires_at_us")
    evaluated_at = payload.get("evaluation_clock_us")
    if (isinstance(expires_at, int) and not isinstance(expires_at, bool)
            and isinstance(evaluated_at, int) and not isinstance(evaluated_at, bool)
            and expires_at <= evaluated_at):
        return False
    return True


def resolve_manifest(payload: dict) -> LeverResolution:
    """Apply the full EVENT_LOCAL refusal law to one ``engine_control_manifest.v2``-shaped payload.

    First-failing code wins, in the RC4 canonical evaluation order (§04: exact-byte/alias parse
    before closed-enum validation before the venue pair before binding/receipt cross-checks). Every
    STATEFUL_IN_REPO/EXTERNAL_EVIDENCE code is registered in :data:`REFUSAL_CODES` but is never
    raised here — see the module docstring's reachability split; sibling modules that own that state
    call :func:`refuse` directly with the applicable code. A whole-bundle mix is
    :func:`resolve_bundle`'s job, not this one.
    """
    if not isinstance(payload, dict):
        raise LeverLawError("manifest payload must be an object")

    shadow_activation = payload.get("shadow_activation")

    for key, enum, code in (
        ("venue_environment", VENUE_ENVIRONMENT_ENUM, "VENUE_ENVIRONMENT_VALUE_INVALID"),
        ("venue_activation", ACTIVATION_ENUM, "VENUE_ACTIVATION_VALUE_INVALID"),
        ("paper_activation", ACTIVATION_ENUM, "PAPER_ACTIVATION_VALUE_INVALID"),
    ):
        refusal = _slot_refusal(payload, key, enum, code)
        if refusal is not None:
            return _refused(refusal)
    if shadow_activation != "LIVE":
        return _refused("SHADOW_CAPTURE_OFF_FORBIDDEN")

    venue_environment = payload["venue_environment"]
    venue_activation = payload["venue_activation"]
    paper_activation = payload["paper_activation"]

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
        # LEV-V-0083/0084: venue_binding's account/venue must equal the manifest scope's when both
        # name them — a duplicate fact that disagrees refuses BEFORE authority (LEV-0041).
        if isinstance(scope, dict):
            for field in ("account_ref", "venue_id"):
                scoped = scope.get(field)
                bound = venue_binding.get(field)
                if scoped is not None and bound is not None and scoped != bound:
                    return _refused("VENUE_BINDING_MISMATCH")
        if venue_environment == "LIVE" and _binding_names_testnet(venue_binding):
            return _refused("LIVE_TESTNET_BINDING_FORBIDDEN")
        if venue_environment == "TESTNET" and _binding_names_live(venue_binding):
            return _refused("TESTNET_LIVE_BINDING_FORBIDDEN")
        # LEV-V-0080: a single binding naming BOTH a live_* and a testnet_* member is a
        # mixed-environment bundle regardless of the top-level environment (the two conditionals
        # above already caught the more-specific LIVE-with-testnet / TESTNET-with-live cases).
        if _binding_names_testnet(venue_binding) and _binding_names_live(venue_binding):
            return _refused("MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN")

    if venue_environment == "LIVE" and venue_activation == "LIVE":
        receipt = payload.get("testnet_promotion_receipt")
        if not isinstance(receipt, dict) or not receipt:
            return _refused("LIVE_PROMOTION_RECEIPT_MISSING")
        if not _promotion_receipt_ok(payload, receipt):
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


def _member_environments(member: dict) -> set:
    """Every venue environment a single bundle member signals — its explicit ``environment`` tag
    (LIVE/TESTNET only) plus any live_*/testnet_* order/fill/account/route/endpoint key it names."""
    envs: set = set()
    declared = member.get("environment")
    if declared in ("LIVE", "TESTNET"):
        envs.add(declared)
    if _binding_names_live(member):
        envs.add("LIVE")
    if _binding_names_testnet(member):
        envs.add("TESTNET")
    return envs


def resolve_bundle(members: list) -> LeverResolution:
    """LEV-0099 / LEV-V-0080: refuse a WHOLE evidence/authority bundle that mixes LIVE and TESTNET
    members (orders, fills, accounts, or routes) — never retain a supposedly safe subset.

    A bundle whose union of member environments contains BOTH LIVE and TESTNET refuses
    ``MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN``; the whole bundle is rejected, never the offending
    member alone. A malformed member (not an object) or a non-list bundle is a usage error (fail
    closed, raised — never a silent partial accept).
    """
    if not isinstance(members, (list, tuple)):
        raise LeverLawError("bundle members must be a list")
    seen: set = set()
    for member in members:
        if not isinstance(member, dict):
            raise LeverLawError("each bundle member must be an object")
        seen |= _member_environments(member)
    if "LIVE" in seen and "TESTNET" in seen:
        return _refused("MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN")
    return _accepted()


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
        if key in CANONICAL_LEVER_FIELDS and value is not None:
            result[key] = value
        elif key not in CANONICAL_LEVER_FIELDS:
            result[key] = value
    result["shadow_activation"] = "LIVE"
    return result

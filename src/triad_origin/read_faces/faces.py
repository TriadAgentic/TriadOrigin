"""The six RC4 §L6 read faces (B08 — LEV-0110..0115) over the B05 four-plane substrate.

Each function is a pure, read-only PROJECTION of already-computed substrate state into the ONE
shared :class:`triad_origin.read_faces.envelope.ReadFaceEnvelope`. A face never mutates state,
arms, activates, switches, reaches a venue/credential/order/money path, or reads a clock — every
'current' fact (``as_of_us`` snapshot instant, ``watermark_us`` source watermark, the projected
state) is caller-supplied, and a fact the substrate does not hold is an honest
``UNAVAILABLE``/``NOT_MEASURABLE`` facet, never a fabricated zero (RC3 W25 "no empty green").

**The six faces** (``docs/control/rc4_control_bundle.json`` tasks, instruction quoted verbatim):

* **LEV-0110 · :func:`get_engine_lever_registry`** — "Add get_engine_lever_registry returning raw
  source plus canonical venue_environment, venue_activation, paper_activation, shadow_activation,
  proof, revision, and freshness." Projects :class:`triad_origin.control.lever_registry.LeverRegistry`
  state. The registry persists ``venue_environment`` (effective) + the LEV-0032 per-engine/component/
  feature ``levers`` table + the accepted digest/revision + attestations; it does NOT persist the
  ``venue_activation``/``paper_activation`` top-level values, so those two canonical facets are
  honestly ``NOT_MEASURABLE`` from registry state (present-but-silent), ``shadow_activation`` is the
  structural invariant ``("LIVE",)`` (never fabricated), and ``requested`` values live only in an
  incoming manifest — carried SEPARATELY from ``effective`` and ``proof`` (LEV-0120).
* **LEV-0111 · :func:`get_engine_lever_attestation`** — "Add get_engine_lever_attestation returning
  process readback, hashes, account/route environment, leases, and mismatches." Projects the
  registry's ``attestations`` table + mismatch detection against the current revision/digest; the
  rich proof (process readback / route / account / lease) lives only in the
  ``runtime_lever_attestation.v1`` wire contract, never in machine state, so those facets are honest
  ``NOT_MEASURABLE``.
* **LEV-0112 · :func:`get_engine_lever_history`** — "Add get_engine_lever_history returning
  immutable transitions and side-effect census references." Projects a caller-supplied ORDERED,
  immutable transition stream (the machine keeps no history in state — it lives in the event tape /
  journal), bounded and paginated, each row carrying its LEV-0057 post-change side-effect census
  reference (honest-null when not supplied — LEV-0109/LEV-V-0123: never infer OFF from absence,
  report the census only).
* **LEV-0113 · :func:`get_shadow_health`** — "Add get_shadow_health returning fixed activation LIVE,
  rejection coverage, persist latency, backlog, resolver health, and contamination." Projects
  :class:`triad_origin.control.shadow_health.ShadowHealth` gauges/counters and LANDS the LEV-0088
  coverage compute (100%-reconciliation over the SHADOW ledger vs a caller-supplied presented total,
  as an EXACT integer pair — no float — honest ``NOT_MEASURABLE`` when the presented total has no
  in-repo source). SHADOW ACTIVATION (the always-LIVE, unswitchable lever) is shown SEPARATELY from
  SHADOW HEALTH (the gauges/counters) — LEV-0118.
* **LEV-0114 · :func:`get_four_plane_status`** — "Add get_four_plane_status returning separate
  SHADOW, PAPER, TESTNET, and LIVE counts, freshness, outcomes, and authority evidence." SHADOW and
  PAPER counts come from their ledgers; TESTNET and LIVE hold NO venue truth in-repo (DARK posture),
  so their counts are honest ``UNAVAILABLE`` — never an inferred OFF (LEV-V-0122); ``requested`` (the
  required non-authoritative baseline manifest), ``effective`` (registry ``venue_environment``) and
  ``proof`` (accepted digest) are carried SEPARATELY (LEV-0120).
* **LEV-0115 · :func:`get_engine_inventory_reconciliation`** — "Add get_engine_inventory_reconciliation
  joining registry, payload, relay, config, service, fill, and repository identities." Joins the
  seven caller-supplied engine identities (LEV-0014's axes) into one bounded per-axis reconciliation;
  an axis with only one side is ``NOT_MEASURABLE`` (nothing to reconcile), an absent axis is
  ``UNAVAILABLE`` (E17: name the fact this repo does not observe, never infer it), and a fresh/stale
  mismatch surfaces both facts — never a single green liveness claim (LEV-V-0124).

**THE CROSS-FACE LAWS** (RC4 ``LEV-0116..0123``) every face obeys: raw legacy values are echoed only
under ``raw_legacy_value``, never silently translated (LEV-0116); requested/effective/proof are
distinct (LEV-0120); SHADOW activation is shown separately from SHADOW health (LEV-0118); every read
is bounded/paginated/snapshot-stamped and a named unavailable is preferred to an empty array
(LEV-0122); no token or credential is read or emitted (LEV-0123). The bound is a caller-supplied
fact: this module owns no page-size number (PAR-132..138 are ``PROPOSED_RC2_MUST_RATIFY`` fail-closed
parameters), so ``limit=None`` returns the full, already-finite, caller-supplied collection rather
than inventing a default.

The three reading judgments this module makes — (a) ``venue_activation``/``paper_activation`` are
``NOT_MEASURABLE`` from registry state, (b) the LEV-0088 coverage numerator/denominator sourcing, and
(c) the seven-axis identity JOIN — are registered (never resolved silently in code) as
``docs/plan/09_OPEN_QUESTIONS.md`` row **E38**; the shared envelope's not-a-vendored-contract judgment
is row **E37**.

Pure and side-effect-free: no clock, no network, no I/O, no randomness, no float, no control verb,
no credential. Nothing here reads a system clock, opens a socket, or holds a credential (Doc 04
§04.17 DARK posture).
"""

from __future__ import annotations

from typing import Any

from .. import timings
from ..control import lever_law
from . import envelope as ev

# ---------------------------------------------------------------------------------------------
# The six face names (LEV-0110..0115) — the ONE in-repo spelling, so the checklist / e2e stage /
# MCP surface all name the same string.
# ---------------------------------------------------------------------------------------------
FACE_LEVER_REGISTRY = "get_engine_lever_registry"
FACE_LEVER_ATTESTATION = "get_engine_lever_attestation"
FACE_LEVER_HISTORY = "get_engine_lever_history"
FACE_SHADOW_HEALTH = "get_shadow_health"
FACE_FOUR_PLANE_STATUS = "get_four_plane_status"
FACE_INVENTORY_RECONCILIATION = "get_engine_inventory_reconciliation"

# The seven engine-identity axes joined by the inventory reconciliation face (LEV-0014/0115), in the
# fixed declared order (deterministic — the semantic path admits no unordered output).
INVENTORY_AXES = ("registry", "payload", "relay", "config", "service", "fill", "repository")

# Source-identity strings (named, per RC3 W25 "response names plane, source, freshness and
# completeness"). These name the in-repo state a face projects; they are labels, not paths.
_SRC_REGISTRY = "control.lever_registry.LeverRegistry.state"
_SRC_ATTESTATION = "control.lever_registry.LeverRegistry.state.attestations"
_SRC_HISTORY = "control.lever_registry MANIFEST_ACCEPTED event/journal stream"
_SRC_SHADOW_HEALTH = "control.shadow_health.ShadowHealth.state"
_SRC_SHADOW_LEDGER = "control.shadow_ledger.ShadowLedger.state"
_SRC_FOUR_PLANE = "control.{shadow_ledger,paper_ledger,lever_registry}.state"
_SRC_INVENTORY = "caller-supplied engine identity join (LEV-0014/0115)"

# Named absence reasons (never a fabricated value; every honest-null facet NAMES its reason).
_REASON_REGISTRY_STATE_UNAVAILABLE = "LEVER_REGISTRY_STATE_UNAVAILABLE"
_REASON_NO_MANIFEST_ACCEPTED = "NO_MANIFEST_ACCEPTED_VENUE_ENVIRONMENT_UNVERIFIED"
_REASON_ACTIVATION_NOT_PERSISTED = "ACTIVATION_VALUE_NOT_PERSISTED_IN_LEVER_REGISTRY_STATE"
_REASON_EFFECT_ENFORCEMENT_NOT_OWNED = "EFFECT_ENFORCEMENT_IS_RUNTIME_ATTESTATION_NOT_CONFIGURATION"
_REASON_RICH_PROOF_WIRE_ONLY = (
    "RICH_ATTESTATION_PROOF_LIVES_IN_runtime_lever_attestation_v1_WIRE_NOT_MACHINE_STATE"
)
_REASON_LEASE_VERIFY_ONLY = "PRODUCER_LEASE_IS_VERIFY_ONLY_NOT_PERSISTED_IN_LEVER_REGISTRY"
_REASON_NO_ATTESTATION_ON_RECORD = "NO_RUNTIME_ATTESTATION_ON_RECORD_FOR_ENGINE"
_REASON_HISTORY_SOURCE_UNAVAILABLE = "LEVER_HISTORY_TRANSITION_STREAM_UNAVAILABLE"
_REASON_CENSUS_EXTERNAL = (
    "POST_CHANGE_SIDE_EFFECT_CENSUS_IS_AN_EXTERNAL_DURABLE_ARTIFACT_LEV_0057_NOT_HELD_IN_REPO"
)
_REASON_CENSUS_MISSING = "SIDE_EFFECT_CENSUS_REFERENCE_NOT_SUPPLIED_FOR_THIS_TRANSITION"
_REASON_SHADOW_HEALTH_STATE_UNAVAILABLE = "SHADOW_HEALTH_STATE_UNAVAILABLE"
_REASON_SHADOW_LEDGER_UNAVAILABLE = "SHADOW_LEDGER_STATE_UNAVAILABLE_COVERAGE_UNCOMPUTABLE"
_REASON_REJECTED_PRESENTED_NO_SOURCE = "REJECTED_INPUTS_PRESENTED_TOTAL_HAS_NO_IN_REPO_SOURCE"
_REASON_PERSIST_LATENCY_TRANSIENT = "REJECTION_PERSIST_LATENCY_IS_TRANSIENT_NOT_STORED_IN_HEALTH_STATE"
_REASON_PAPER_LEDGER_UNAVAILABLE = "PAPER_LEDGER_STATE_UNAVAILABLE"
_REASON_NO_VENUE_TRUTH = "ORIGIN_HOLDS_NO_VENUE_TRUTH_TESTNET_LIVE_NOT_OBSERVED_HERE"
_REASON_INVENTORY_UNAVAILABLE = "NO_ENGINE_IDENTITY_JOIN_SUPPLIED"
_REASON_AXIS_UNAVAILABLE = "AXIS_IDENTITY_NOT_OBSERVED_HERE"
_REASON_AXIS_SINGLE_SIDED = "SINGLE_SIDED_IDENTITY_CONTRADICTION_NOT_MEASURABLE"

# The two RC4 freshness bounds the health/attestation staleness facets read by exact name — never a
# numeric literal (the ONE in-repo timing table owns the numbers).
_BOUND_HEARTBEAT = "shadow_health_max_age_ms"
_BOUND_BACKLOG = "shadow_resolver_backlog_max_age_ms"
_BOUND_PERSIST = "shadow_rejection_persist_deadline_ms"
_BOUND_ATTESTATION = "runtime_attestation_max_age_ms"

# Reuse the ONE honest status vocabulary (no drift): a facet WITHIN a value dict names its own
# AVAILABLE / UNAVAILABLE / NOT_MEASURABLE sub-status the same way the envelope names its overall one.
_AVAILABLE = ev.STATUS_AVAILABLE
_UNAVAILABLE = ev.STATUS_UNAVAILABLE
_NOT_MEASURABLE = ev.STATUS_NOT_MEASURABLE


# ---------------------------------------------------------------------------------------------
# Small fail-closed guards + bounded keyset pagination
# ---------------------------------------------------------------------------------------------
def _require_state_dict(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ev.ReadFaceEnvelopeError(
            f"{name} must be a dict (substrate machine state); got {type(value).__name__}")
    return value


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _decode_cursor(after: object) -> int:
    """A resume cursor is the decimal start-index this module emits (or a plain non-negative int)."""
    if after is None:
        return 0
    if isinstance(after, str):
        if after.isdigit():
            return int(after)
        raise ev.ReadFaceEnvelopeError(
            f"after cursor must be a non-negative decimal string; got {after!r}")
    if _is_plain_int(after) and after >= 0:
        return after
    raise ev.ReadFaceEnvelopeError(
        f"after cursor must be a non-negative decimal string or int; got {after!r}")


def _paginate(ordered_items: list, *, limit: object, after: object) -> tuple[list, str | None]:
    """Positional keyset pagination over a DETERMINISTICALLY-ORDERED list.

    ``after`` names the next start index (the decimal cursor this module emits); the returned cursor
    is the next start index (a non-empty decimal string) or ``None`` when the page completes the
    collection. This module owns no page size: ``limit=None`` returns the full (already-finite,
    caller-supplied) collection — PAR-132..138 stay fail-closed, never a silently invented default.
    """
    start = _decode_cursor(after)
    total = len(ordered_items)
    if start > total:
        start = total
    if limit is None:
        return list(ordered_items[start:]), None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ev.ReadFaceEnvelopeError(f"limit must be a non-negative int or None; got {limit!r}")
    page = list(ordered_items[start:start + limit])
    next_start = start + limit
    cursor = str(next_start) if next_start < total else None
    return page, cursor


def _unavailable_facet(reason: str) -> dict:
    return {"status": _UNAVAILABLE, "reason": reason}


def _not_measurable_facet(reason: str) -> dict:
    return {"status": _NOT_MEASURABLE, "reason": reason}


# ---------------------------------------------------------------------------------------------
# LEV-0110 · get_engine_lever_registry
# ---------------------------------------------------------------------------------------------
def _canonical_from_registry(registry_state: dict) -> dict:
    """The four canonical four-plane values as EFFECTIVE facts of the registry — each honestly
    named: ``venue_environment`` is persisted; ``venue_activation``/``paper_activation`` are NOT
    persisted in registry state (present-but-silent ⇒ NOT_MEASURABLE, never an inferred OFF —
    LEV-V-0122); ``shadow_activation`` is the structural ``("LIVE",)`` invariant, not a guess."""
    venv = registry_state.get("venue_environment")
    if venv is not None:
        env_facet = {"status": _AVAILABLE, "value": venv, "reason": None}
    else:
        env_facet = {"status": _NOT_MEASURABLE, "value": None, "reason": _REASON_NO_MANIFEST_ACCEPTED}
    return {
        "venue_environment": env_facet,
        "venue_activation": {
            "status": _NOT_MEASURABLE, "value": None, "reason": _REASON_ACTIVATION_NOT_PERSISTED},
        "paper_activation": {
            "status": _NOT_MEASURABLE, "value": None, "reason": _REASON_ACTIVATION_NOT_PERSISTED},
        # shadow_activation is the always-LIVE, unswitchable lever (enum ("LIVE",)) — a structural
        # truth, never fabricated.
        "shadow_activation": {
            "status": _AVAILABLE, "value": lever_law.SHADOW_ACTIVATION_ENUM[0], "reason": None},
    }


def _requested_four_plane(manifest: object) -> dict | None:
    """The REQUESTED canonical values — echoed VERBATIM from an incoming manifest (LEV-0116: never
    silently translated). ``None`` when no manifest is supplied: requested is not persisted, it lives
    only in the incoming/pending manifest, kept SEPARATE from effective/proof (LEV-0120)."""
    if manifest is None:
        return None
    _require_state_dict(manifest, "requested_manifest")
    return {field: manifest.get(field) for field in lever_law.CANONICAL_LEVER_FIELDS}


def get_engine_lever_registry(
    *,
    registry_state: dict | None,
    as_of_us: int,
    watermark_us: int | None = None,
    requested_manifest: dict | None = None,
    raw_legacy_values: dict | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """LEV-0110 — project the runtime lever registry: raw source + canonical four-plane values +
    proof + revision + freshness, with requested/effective/proof carried SEPARATELY."""
    if registry_state is None:
        return ev.unavailable(
            face=FACE_LEVER_REGISTRY, source=_SRC_REGISTRY, as_of_us=as_of_us,
            watermark_us=watermark_us, plane=ev.CONTROL_PLANE,
            reason=_REASON_REGISTRY_STATE_UNAVAILABLE)
    _require_state_dict(registry_state, "registry_state")
    if raw_legacy_values is not None:
        _require_state_dict(raw_legacy_values, "raw_legacy_values")

    levers = registry_state.get("levers", {})
    page, cursor = _paginate(sorted(levers.items()), limit=limit, after=after)
    lever_rows = [
        {"lever_key": key, "value": row.get("value"), "digest": row.get("digest"),
         "revision": row.get("revision")}
        for key, row in page
    ]
    value = {
        # The verbatim registry state — the raw source (LEV-0116). Detached at the builder boundary.
        "raw_source": registry_state,
        # Raw legacy values echoed VERBATIM, never translated to LIVE/TESTNET (LEV-0116/LEV-V-0121).
        "raw_legacy_value": raw_legacy_values,
        # requested / effective / proof — SEPARATE (LEV-0120).
        "requested": _requested_four_plane(requested_manifest),
        "effective": {
            "revision": registry_state.get("revision"),
            "accepted_manifest_digest_sha256": registry_state.get("accepted_manifest_digest_sha256"),
            "canonical": _canonical_from_registry(registry_state),
        },
        "proof": {
            "accepted_manifest_digest_sha256": registry_state.get("accepted_manifest_digest_sha256"),
            "attestation_count": len(registry_state.get("attestations", {})),
            # LEV-0120: configuration alone never proves enforcement — that is a runtime-attestation
            # fact, projected by :func:`get_engine_lever_attestation`, not claimable here.
            "effect_enforced": _not_measurable_facet(_REASON_EFFECT_ENFORCEMENT_NOT_OWNED),
        },
        "levers": lever_rows,
    }
    return ev.available(
        face=FACE_LEVER_REGISTRY, source=_SRC_REGISTRY, as_of_us=as_of_us,
        watermark_us=watermark_us, plane=ev.CONTROL_PLANE, value=value,
        returned=len(lever_rows), limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------------------------
# LEV-0111 · get_engine_lever_attestation
# ---------------------------------------------------------------------------------------------
def _attestation_row(engine_id: str, att: dict, *, current_revision: object) -> dict:
    accepted_revision = att.get("accepted_revision")
    age_ms = att.get("attested_age_ms")
    revision_matches = accepted_revision == current_revision
    stale = timings.is_stale(age_ms, _BOUND_ATTESTATION) if _is_plain_int(age_ms) else None
    mismatch = None
    if not revision_matches:
        mismatch = "RUNTIME_LEVER_ATTESTATION_MISMATCH"
    elif stale is True:
        mismatch = "RUNTIME_LEVER_ATTESTATION_MISMATCH"
    return {
        "engine_id": engine_id,
        "accepted_revision": accepted_revision,
        "attested_age_ms": age_ms,
        "current_revision": current_revision,
        "revision_matches_current": revision_matches,
        "stale": stale,
        "mismatch": mismatch,
        # The rich proof (process readback / hashes / route / account / lease) lives ONLY in the
        # runtime_lever_attestation.v1 WIRE contract — never in machine state; honest NOT_MEASURABLE.
        "process_readback": _not_measurable_facet(_REASON_RICH_PROOF_WIRE_ONLY),
        "route_environment": _not_measurable_facet(_REASON_RICH_PROOF_WIRE_ONLY),
        "account_environment": _not_measurable_facet(_REASON_RICH_PROOF_WIRE_ONLY),
        "lease": _not_measurable_facet(_REASON_LEASE_VERIFY_ONLY),
    }


def get_engine_lever_attestation(
    *,
    registry_state: dict | None,
    as_of_us: int,
    watermark_us: int | None = None,
    engine_id: str | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """LEV-0111 — project the runtime attestation table + mismatches; the rich process/route/account/
    lease proof is honest ``NOT_MEASURABLE`` (it lives only on the wire, not in machine state)."""
    if registry_state is None:
        return ev.unavailable(
            face=FACE_LEVER_ATTESTATION, source=_SRC_ATTESTATION, as_of_us=as_of_us,
            watermark_us=watermark_us, plane=ev.CONTROL_PLANE,
            reason=_REASON_REGISTRY_STATE_UNAVAILABLE)
    _require_state_dict(registry_state, "registry_state")
    attestations = registry_state.get("attestations", {})
    current_revision = registry_state.get("revision")
    current_digest = registry_state.get("accepted_manifest_digest_sha256")

    if engine_id is not None:
        if not isinstance(engine_id, str) or engine_id == "":
            raise ev.ReadFaceEnvelopeError("engine_id must be a non-empty string or None")
        att = attestations.get(engine_id)
        if att is None:
            # The registry IS present; this engine simply has no attestation on record — a real,
            # measurable fact (we looked; it is absent), NEVER an inferred OFF (LEV-V-0123).
            value = {
                "engine_id": engine_id, "attested": False, "current_revision": current_revision,
                "reason": _REASON_NO_ATTESTATION_ON_RECORD}
            return ev.available(
                face=FACE_LEVER_ATTESTATION, source=_SRC_ATTESTATION, as_of_us=as_of_us,
                watermark_us=watermark_us, plane=ev.CONTROL_PLANE, value=value)
        value = {
            "engine_id": engine_id, "attested": True,
            "attestation": _attestation_row(engine_id, att, current_revision=current_revision)}
        return ev.available(
            face=FACE_LEVER_ATTESTATION, source=_SRC_ATTESTATION, as_of_us=as_of_us,
            watermark_us=watermark_us, plane=ev.CONTROL_PLANE, value=value, returned=1)

    page, cursor = _paginate(sorted(attestations.items()), limit=limit, after=after)
    rows = [_attestation_row(eid, att, current_revision=current_revision) for eid, att in page]
    value = {
        "current_revision": current_revision,
        "accepted_manifest_digest_sha256": current_digest,
        "attestations": rows,
        "rich_proof_source": "triad.runtime_lever_attestation.v1 wire (not held in machine state)",
    }
    return ev.available(
        face=FACE_LEVER_ATTESTATION, source=_SRC_ATTESTATION, as_of_us=as_of_us,
        watermark_us=watermark_us, plane=ev.CONTROL_PLANE, value=value,
        returned=len(rows), limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------------------------
# LEV-0112 · get_engine_lever_history
# ---------------------------------------------------------------------------------------------
def _census_ref(census: list | None, position: int) -> dict:
    if census is None:
        return {"status": _NOT_MEASURABLE, "ref": None, "reason": _REASON_CENSUS_EXTERNAL}
    ref = census[position]
    if ref is None:
        return {"status": _NOT_MEASURABLE, "ref": None, "reason": _REASON_CENSUS_MISSING}
    if not isinstance(ref, str) or ref == "":
        raise ev.ReadFaceEnvelopeError(
            f"side_effect_census[{position}] must be a non-empty string or None; got {ref!r}")
    return {"status": _AVAILABLE, "ref": ref, "reason": None}


def get_engine_lever_history(
    *,
    transitions: list | None,
    as_of_us: int,
    watermark_us: int | None = None,
    side_effect_census: list | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """LEV-0112 — project the immutable, ordered transition stream + per-transition side-effect
    census references (honest-null when not supplied; never infer OFF from absence)."""
    if transitions is None:
        return ev.unavailable(
            face=FACE_LEVER_HISTORY, source=_SRC_HISTORY, as_of_us=as_of_us,
            watermark_us=watermark_us, plane=ev.CONTROL_PLANE,
            reason=_REASON_HISTORY_SOURCE_UNAVAILABLE)
    if not isinstance(transitions, (list, tuple)):
        raise ev.ReadFaceEnvelopeError(
            f"transitions must be an ordered list/tuple or None; got {type(transitions).__name__}")
    if side_effect_census is not None:
        if not isinstance(side_effect_census, (list, tuple)):
            raise ev.ReadFaceEnvelopeError("side_effect_census must be a parallel list/tuple or None")
        if len(side_effect_census) != len(transitions):
            raise ev.ReadFaceEnvelopeError(
                "side_effect_census must be parallel to transitions (equal length)")

    # The stream order IS the canonical order (an immutable append-only history) — never re-sorted.
    indexed = list(enumerate(transitions))
    page, cursor = _paginate(indexed, limit=limit, after=after)
    rows = [
        {"sequence_index": position, "transition": transition,
         "side_effect_census_ref": _census_ref(side_effect_census, position)}
        for position, transition in page
    ]
    value = {
        "transitions": rows,
        "total_supplied": len(transitions),
        "post_change_side_effect_audit_ms": timings.timing_ms("post_change_side_effect_audit_ms"),
    }
    return ev.available(
        face=FACE_LEVER_HISTORY, source=_SRC_HISTORY, as_of_us=as_of_us,
        watermark_us=watermark_us, plane=ev.CONTROL_PLANE, value=value,
        returned=len(rows), limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------------------------
# LEV-0113 · get_shadow_health  (+ the LEV-0088 coverage compute, landed)
# ---------------------------------------------------------------------------------------------
def _shadow_coverage(ledger_state: object, *, rejected_inputs_presented: object) -> dict:
    """The LEV-0088 100%-reconciliation coverage — an EXACT integer pair (no float), never a
    fabricated ratio. ``reconciled`` = every SHADOW ledger record (a tradeable-hypothesis trade row
    OR an explicit ``SHADOW_UNTRADEABLE`` audit — LEV-0088's two branches). ``fully_reconciled`` is
    ``reconciled == presented``. Honest ``NOT_MEASURABLE`` when the presented total (an external
    fact) is not supplied; ``UNAVAILABLE`` when the ledger itself is absent."""
    if ledger_state is None:
        return _unavailable_facet(_REASON_SHADOW_LEDGER_UNAVAILABLE)
    _require_state_dict(ledger_state, "ledger_state")
    reconciled_tradeable = len(ledger_state.get("trades", {}))
    reconciled_untradeable = len(ledger_state.get("audits", {}))
    reconciled_total = reconciled_tradeable + reconciled_untradeable
    if rejected_inputs_presented is None:
        return {
            "status": _NOT_MEASURABLE, "reason": _REASON_REJECTED_PRESENTED_NO_SOURCE,
            "reconciled_tradeable_hypotheses": reconciled_tradeable,
            "reconciled_untradeable_audits": reconciled_untradeable,
            "reconciled_total": reconciled_total,
            "rejected_inputs_presented": None, "fully_reconciled": None}
    if not _is_plain_int(rejected_inputs_presented) or rejected_inputs_presented < 0:
        raise ev.ReadFaceEnvelopeError(
            "rejected_inputs_presented must be a non-negative int or None; "
            f"got {rejected_inputs_presented!r}")
    return {
        "status": _AVAILABLE, "reason": None,
        "reconciled_tradeable_hypotheses": reconciled_tradeable,
        "reconciled_untradeable_audits": reconciled_untradeable,
        "reconciled_total": reconciled_total,
        "rejected_inputs_presented": rejected_inputs_presented,
        # 100%-reconciliation as an EXACT comparison — no float ratio (determinism law).
        "fully_reconciled": reconciled_total == rejected_inputs_presented}


def get_shadow_health(
    *,
    health_state: dict | None,
    as_of_us: int,
    ledger_state: dict | None = None,
    watermark_us: int | None = None,
    rejected_inputs_presented: int | None = None,
) -> ev.ReadFaceEnvelope:
    """LEV-0113 — project SHADOW health (gauges/counters) with SHADOW ACTIVATION (the always-LIVE
    lever) shown SEPARATELY, and the LEV-0088 coverage compute landed (honest NOT_MEASURABLE when
    coverage cannot be computed)."""
    if health_state is None:
        return ev.unavailable(
            face=FACE_SHADOW_HEALTH, source=_SRC_SHADOW_HEALTH, as_of_us=as_of_us,
            watermark_us=watermark_us, plane=ev.PLANE_SHADOW,
            reason=_REASON_SHADOW_HEALTH_STATE_UNAVAILABLE)
    _require_state_dict(health_state, "health_state")

    heartbeat_age = health_state.get("last_heartbeat_age_ms")
    backlog_age = health_state.get("backlog_age_ms")
    contamination_count = health_state.get("contamination_count", 0)
    value = {
        # SHADOW ACTIVATION — the lever (enum ("LIVE",), unswitchable). SEPARATE from health (LEV-0118).
        "shadow_activation": {
            "value": lever_law.SHADOW_ACTIVATION_ENUM[0], "user_switchable": False,
            "note": "the always-LIVE rejected-trade population lever; not a health signal"},
        # SHADOW HEALTH — the gauges/counters. SEPARATE from activation (LEV-0113). A stale writer
        # never turns SHADOW off; it only narrows the EXECUTION planes.
        "health": {
            "writer_heartbeat_age_ms": heartbeat_age,
            "heartbeat_stale": (
                timings.is_stale(heartbeat_age, _BOUND_HEARTBEAT)
                if _is_plain_int(heartbeat_age) else None),
            "backlog_age_ms": backlog_age,
            "backlog_stale": (
                timings.is_stale(backlog_age, _BOUND_BACKLOG)
                if _is_plain_int(backlog_age) else None),
            "dedupe_count": health_state.get("dedupe_count", 0),
            "collision_count": health_state.get("collision_count", 0),
            "contamination_count": contamination_count,
            "contaminated": contamination_count > 0},
        # Rejection persist latency is a TRANSIENT input, not stored in health state → NOT_MEASURABLE.
        "rejection_persist": {
            "status": _NOT_MEASURABLE, "reason": _REASON_PERSIST_LATENCY_TRANSIENT,
            "deadline_ms": timings.timing_ms(_BOUND_PERSIST)},
        # LEV-0088 coverage — landed here.
        "coverage": _shadow_coverage(
            ledger_state, rejected_inputs_presented=rejected_inputs_presented),
    }
    return ev.available(
        face=FACE_SHADOW_HEALTH, source=_SRC_SHADOW_HEALTH, as_of_us=as_of_us,
        watermark_us=watermark_us, plane=ev.PLANE_SHADOW, value=value)


# ---------------------------------------------------------------------------------------------
# LEV-0114 · get_four_plane_status
# ---------------------------------------------------------------------------------------------
def get_four_plane_status(
    *,
    as_of_us: int,
    shadow_ledger_state: dict | None = None,
    paper_ledger_state: dict | None = None,
    registry_state: dict | None = None,
    watermark_us: int | None = None,
) -> ev.ReadFaceEnvelope:
    """LEV-0114 — the four planes as SEPARATE sub-statuses: SHADOW (always-LIVE lever + ledger
    counts), PAPER (demo, no real money, ledger counts), TESTNET/LIVE (no venue truth in-repo ⇒
    honest UNAVAILABLE, never inferred OFF), plus requested/effective/proof authority evidence."""
    # SHADOW — the always-LIVE lever (structural), counts from the ledger (data, SEPARATE).
    shadow: dict[str, Any] = {
        "activation": lever_law.SHADOW_ACTIVATION_ENUM[0], "user_switchable": False,
        "venue_authority": False}
    if shadow_ledger_state is None:
        shadow["counts"] = _unavailable_facet(_REASON_SHADOW_LEDGER_UNAVAILABLE)
    else:
        _require_state_dict(shadow_ledger_state, "shadow_ledger_state")
        shadow["counts"] = {
            "status": _AVAILABLE, "trades": len(shadow_ledger_state.get("trades", {})),
            "audits": len(shadow_ledger_state.get("audits", {}))}

    # PAPER — demo, no real money, no venue authority; counts from the paper ledger.
    paper: dict[str, Any] = {"demo_account": True, "real_money": False, "venue_authority": False}
    if paper_ledger_state is None:
        paper["counts"] = _unavailable_facet(_REASON_PAPER_LEDGER_UNAVAILABLE)
    else:
        _require_state_dict(paper_ledger_state, "paper_ledger_state")
        accounts = paper_ledger_state.get("accounts", {})
        paper["counts"] = {
            "status": _AVAILABLE, "accounts": len(accounts),
            "orders": sum(len(acct.get("orders", {})) for acct in accounts.values()),
            "fills": sum(len(acct.get("fills", {})) for acct in accounts.values()),
            "trades": len(paper_ledger_state.get("trades", {}))}

    # TESTNET / LIVE — ORIGIN holds NO venue truth (DARK): counts UNAVAILABLE, never inferred OFF.
    testnet = {"venue_authority": False, "status": _UNAVAILABLE, "reason": _REASON_NO_VENUE_TRUTH}
    live = {"venue_authority": False, "status": _UNAVAILABLE, "reason": _REASON_NO_VENUE_TRUTH}

    # Authority evidence — requested / effective / proof, SEPARATE (LEV-0120).
    effective_env = registry_state.get("venue_environment") if isinstance(registry_state, dict) else None
    proof_digest = (
        registry_state.get("accepted_manifest_digest_sha256")
        if isinstance(registry_state, dict) else None)
    if effective_env is not None:
        env_facet = {"status": _AVAILABLE, "value": effective_env, "reason": None}
    else:
        env_facet = {"status": _NOT_MEASURABLE, "value": None, "reason": _REASON_NO_MANIFEST_ACCEPTED}
    authority = {
        "requested_baseline_manifest": dict(lever_law.BASELINE_MANIFEST),
        "effective": {"venue_environment": env_facet},
        "proof": {
            "accepted_manifest_digest_sha256": proof_digest,
            "effect_enforced": _not_measurable_facet(_REASON_EFFECT_ENFORCEMENT_NOT_OWNED)},
        "live_requires_testnet_promotion_receipt": True,
        "paper_substitutes_for_testnet": False,
    }
    value = {
        "planes": {"SHADOW": shadow, "PAPER": paper, "TESTNET": testnet, "LIVE": live},
        "authority_evidence": authority,
    }
    # plane=None: this face spans all four populations (it is not scoped to one).
    return ev.available(
        face=FACE_FOUR_PLANE_STATUS, source=_SRC_FOUR_PLANE, as_of_us=as_of_us,
        watermark_us=watermark_us, plane=None, value=value)


# ---------------------------------------------------------------------------------------------
# LEV-0115 · get_engine_inventory_reconciliation
# ---------------------------------------------------------------------------------------------
def _reconcile_axis(axis: str, supplied: object) -> dict:
    if supplied is None:
        # E17: name the fact this repo does not observe; NEVER infer it.
        return {
            "axis": axis, "status": _UNAVAILABLE, "expected": None, "observed": None,
            "contradiction": None, "freshness_us": None, "reason": _REASON_AXIS_UNAVAILABLE}
    if not isinstance(supplied, dict):
        raise ev.ReadFaceEnvelopeError(
            f"identities[{axis!r}] must be a dict or None; got {type(supplied).__name__}")
    expected = supplied.get("expected")
    observed = supplied.get("observed")
    freshness = supplied.get("freshness_us")
    if freshness is not None and not _is_plain_int(freshness):
        raise ev.ReadFaceEnvelopeError(
            f"identities[{axis!r}].freshness_us must be an int (epoch us) or absent; got {freshness!r}")
    if expected is None and observed is None:
        return {
            "axis": axis, "status": _UNAVAILABLE, "expected": None, "observed": None,
            "contradiction": None, "freshness_us": freshness, "reason": _REASON_AXIS_UNAVAILABLE}
    if expected is None or observed is None:
        # Only one side is present — nothing to reconcile (NOT_MEASURABLE, never a fabricated match).
        return {
            "axis": axis, "status": _NOT_MEASURABLE, "expected": expected, "observed": observed,
            "contradiction": None, "freshness_us": freshness, "reason": _REASON_AXIS_SINGLE_SIDED}
    return {
        "axis": axis, "status": _AVAILABLE, "expected": expected, "observed": observed,
        "contradiction": expected != observed, "freshness_us": freshness, "reason": None}


def get_engine_inventory_reconciliation(
    *,
    as_of_us: int,
    identities: dict | None = None,
    watermark_us: int | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """LEV-0115 — join the seven engine identities into one bounded per-axis reconciliation. An
    absent axis is UNAVAILABLE (never inferred), a single-sided axis is NOT_MEASURABLE, and a
    mismatch surfaces both facts + freshness — never a single green liveness claim (LEV-V-0124)."""
    if identities is None:
        return ev.unavailable(
            face=FACE_INVENTORY_RECONCILIATION, source=_SRC_INVENTORY, as_of_us=as_of_us,
            watermark_us=watermark_us, plane=ev.CONTROL_PLANE, reason=_REASON_INVENTORY_UNAVAILABLE)
    _require_state_dict(identities, "identities")

    axis_rows = [(axis, _reconcile_axis(axis, identities.get(axis))) for axis in INVENTORY_AXES]
    page, cursor = _paginate(axis_rows, limit=limit, after=after)
    rows = [row for _axis, row in page]
    # The contradiction summary is computed over the whole (fixed-cardinality 7) axis set, never a
    # single green: a measured axis whose expected != observed is a named contradiction.
    all_rows = [row for _axis, row in axis_rows]
    measured = [row for row in all_rows if row["status"] == _AVAILABLE]
    contradiction_axes = sorted(row["axis"] for row in measured if row["contradiction"] is True)
    value = {
        "axes": rows,
        "axis_order": list(INVENTORY_AXES),
        "measured_axes": len(measured),
        "contradiction_axes": contradiction_axes,
        "any_contradiction": len(contradiction_axes) > 0,
    }
    return ev.available(
        face=FACE_INVENTORY_RECONCILIATION, source=_SRC_INVENTORY, as_of_us=as_of_us,
        watermark_us=watermark_us, plane=ev.CONTROL_PLANE, value=value,
        returned=len(rows), limit=limit, cursor=cursor)

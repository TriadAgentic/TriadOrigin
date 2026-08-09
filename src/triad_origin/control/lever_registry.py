"""LEV-0032/0040/0043/0048/0050/0051/0053/0055/0058 — the append-only runtime lever registry.

RC4 declares one canonical ``runtime_lever_registry.v1`` and requires every runtime to refuse
money authority until it has ATTESTED the exact current revision, with a bounded local cache and
a durable, monotonic compare-and-swap write path. This module is the pure, in-process
:class:`triad_origin.transition.DeterministicMachine` that state-machines that registry. It holds
no socket, no clock, and no credential (Doc 04 §04.17 DARK posture); every decision is a function
of the four transition inputs.

**Tasks answered here** (RC4 control bundle ``tasks``, exact instruction quoted):

* **LEV-0032** — "Publish runtime_lever_registry.v1 with one unique row for every engine,
  component, and feature lever." :attr:`State["levers"]` is exactly that table, keyed by
  ``lever_key``; a row is created/updated only by an accepted :data:`REGISTER_MANIFEST`.
* **LEV-0040** — "Require one complete activations map: missing, duplicated, reserved, or unknown
  registered keys reject the manifest." Once the registry holds a non-empty baseline key set, a
  new manifest's ``activations`` map must match that key set EXACTLY (a Python dict already makes
  a duplicated key structurally impossible, so this reduces to key-set equality) or the whole
  manifest is refused with ``LEVER_REGISTRY_INCOMPLETE`` and no row moves.
* **LEV-0043** — "Define canonical JSON serialization and signature bytes; reject reordered
  semantic ambiguity and unknown fields." Every stored/compared text field (``manifest_digest_sha256``,
  ``engine_id``) is validated through :func:`triad_origin.canonical.canonical_json`, so the
  identity is byte-canonical and NFC-normalized; each lever row is stamped with the exact
  ``manifest_digest_sha256`` the caller signed for the manifest that last set it — "digest-bound",
  the literal phrase :data:`triad_origin.control.lever_law.REFUSAL_CODES` uses for
  ``LEVER_REGISTRY_INCOMPLETE``'s meaning.
* **LEV-0048** — "Build one signed append-only canonical lever register with monotonic revision
  and compare-and-swap writes." :data:`REGISTER_MANIFEST` accepts a manifest ONLY at
  ``revision == current_revision + 1``; any other revision (behind, ahead, or repeated) is refused
  with ``LEVER_REVISION_STALE`` and the state is left byte-identical — a rejected write is never
  partially applied.
* **LEV-0050** — "Require every runtime to refuse money authority until it accepts and attests the
  exact current revision." :data:`ATTEST_RUNTIME` is the runtime's proof-of-currency: an
  attestation whose ``accepted_manifest_digest_sha256``/``accepted_revision`` do not exactly match
  the registry's own current values is refused with ``RUNTIME_LEVER_ATTESTATION_MISMATCH`` — a
  runtime that never clears this check has, by this registry's own record, never proven it may
  hold money authority (the refusal's ``minimum_action`` forces ``venue_activation``/
  ``paper_activation`` OFF for the caller to apply).
* **LEV-0051** — "Cache lever state for at most 2,000 ms and resolve venue_activation/
  paper_activation OFF on missing, stale, malformed, or conflicting state." :data:`RESOLVE_STALENESS`
  applies :func:`triad_origin.timings.is_stale` against the declared
  ``lever_cache_max_age_ms`` bound (2000, see :mod:`triad_origin.timings`) and, when stale, emits
  the exact :func:`triad_origin.control.lever_law.containment_action` minimum-action a caller must
  force locally — this transition never mutates the registry's own truth, it only reports what a
  stale-cache holder must do (an advisory forced-OFF, not a second copy of the ledger).
* **LEV-0053** — "Implement 5,000 ms lease renewal and 15,000 ms TTL with monotonically increasing
  fencing epochs." This is the ALREADY-BUILT :mod:`triad_origin.lease` module's job
  (``ConsumerFence`` — a monotonic ``fencing_token`` per scope, rejecting a stale epoch even on
  late arrival); this registry's own ``revision`` is a SEPARATE monotonic sequence (the manifest's
  compare-and-swap identity, LEV-0048) and deliberately does not re-implement lease TTL/renewal —
  a producer-lease need is answered by importing :mod:`triad_origin.lease`, never by a second
  fencing mechanism grown here.
* **LEV-0055** — "Emit runtime attestation every 5,000 ms and reject authority after 15,000 ms
  without a current attestation." The 5,000 ms EMIT cadence is the runtime's own external duty
  (out of this module's reach — it has no clock); the 15,000 ms REJECT bound
  (``runtime_attestation_max_age_ms``) is enforced on ingestion by :data:`ATTEST_RUNTIME`, which
  refuses (again ``RUNTIME_LEVER_ATTESTATION_MISMATCH``) a caller-reported ``freshness_age_ms``
  that already exceeds it, even when the digest/revision themselves match exactly.
* **LEV-0058** — "Preserve venue_activation and paper_activation OFF across supervisor restart; no
  legacy variable may re-enable a path." This registry's state is a plain, canonical-JSON
  snapshot (:func:`triad_origin.transition.run`'s ``initial=`` resumes from exactly that snapshot),
  so a restarted supervisor rehydrates the SAME revision/levers/attestations rather than a fresh
  ``OFF`` guess; and no legacy alias can ever reach ``levers``/``accepted_manifest_digest_sha256``
  in the first place, because every manifest is filtered through
  :func:`triad_origin.control.lever_law.resolve_manifest` first, whose 35-member
  ``INVALID_ALIASES`` set (LEV-0004/LEV-0047) refuses every legacy word/boolean/int/blank before
  this module ever sees an accepted value.

Every stop rule above resolves to the SAME containment: ``venue_activation``/``paper_activation``
forced toward ``OFF`` for the affected scope, ``shadow_activation`` left ``LIVE``, existing exit/
reconciliation/protection authority untouched — this module never invents a different containment
shape; it always asks :mod:`triad_origin.control.lever_law` for the named one.

**State shape** (:func:`initial_state`)::

    {"revision": 0, "levers": {}, "accepted_manifest_digest_sha256": None, "attestations": {}}

    # after an accepted REGISTER_MANIFEST:
    {"revision": <int>,
     "levers": {lever_key: {"value": "LIVE" | "OFF", "digest": <manifest_digest_sha256>,
                             "revision": <int>}},
     "accepted_manifest_digest_sha256": <str>,
     "attestations": {engine_id: {"accepted_revision": <int>, "attested_age_ms": <int>}}}

**Envelope kinds**::

    # A signed engine_control_manifest.v2-shaped payload proposing the next registry revision.
    # Every field lever_law.resolve_manifest reads (venue_environment/venue_activation/
    # paper_activation/shadow_activation/scope/activations/venue_binding/testnet_promotion_receipt)
    # lives at the top level of payload, alongside the two fields THIS module reads directly:
    # the explicit next-revision int and the manifest's own content digest.
    {"event_id": str, "kind": "REGISTER_MANIFEST",
     "payload": {"venue_environment": "LIVE" | "TESTNET" | "OFF",
                 "venue_activation": "LIVE" | "OFF", "paper_activation": "LIVE" | "OFF",
                 "shadow_activation": "LIVE", "scope": {...} | None,
                 "activations": {lever_key: "LIVE" | "OFF", ...} | None,
                 "manifest_digest_sha256": str, "revision": int, ...}}

    # A runtime's proof that it has accepted and applied the exact current revision (LEV-0050).
    {"event_id": str, "kind": "ATTEST_RUNTIME",
     "payload": {"engine_id": str, "accepted_manifest_digest_sha256": str | None,
                 "accepted_revision": int, "freshness_age_ms": int}}

    # A pure query: "is engine_id's cached copy of the registry too old to trust?" (LEV-0051).
    {"event_id": str, "kind": "RESOLVE_STALENESS",
     "payload": {"engine_id": str, "cached_age_ms": int}}

Every semantic threshold this module consumes (the 2,000 ms lever-cache bound, the 15,000 ms
runtime-attestation bound) comes from the fixed :mod:`triad_origin.timings` table, never from a
caller-supplied ``params`` value — RC4 declares these bounds as law, not as configuration, so
there is nothing here for a hidden experiment to override. A structurally malformed payload field
(a non-int revision, a non-int freshness/cache age) raises :class:`LeverRegistryError` /
:class:`triad_origin.timings.TimingError` — fail closed, never silently defaulted; a well-typed
but SUBSTANTIVELY wrong value (a stale revision, a digest mismatch, an aged-out attestation) is a
named refusal event, never an exception, because that is an ordinary and expected outcome of an
adversarial or lagging caller, not a programming defect.
"""

from __future__ import annotations

from .. import canonical, timings
from ..transition import Envelope, Event, Params, Quality, State, TransitionResult
from . import lever_law

REGISTER_MANIFEST = "REGISTER_MANIFEST"
ATTEST_RUNTIME = "ATTEST_RUNTIME"
RESOLVE_STALENESS = "RESOLVE_STALENESS"

MANIFEST_REFUSED = "MANIFEST_REFUSED"
MANIFEST_ACCEPTED = "MANIFEST_ACCEPTED"
ATTESTATION_REFUSED = "ATTESTATION_REFUSED"
ATTESTATION_ACCEPTED = "ATTESTATION_ACCEPTED"
STALENESS_FORCED_OFF = "STALENESS_FORCED_OFF"

_LEVER_CACHE_BOUND = "lever_cache_max_age_ms"
_RUNTIME_ATTESTATION_BOUND = "runtime_attestation_max_age_ms"


class LeverRegistryError(ValueError):
    """A lever-registry payload law violation (fail closed, named — never a silent default)."""


def _require_exact_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LeverRegistryError(f"{name} must be an exact int, got {type(value).__name__}")
    return value


def _require_canonical_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LeverRegistryError(f"{name} must be a non-empty string")
    try:
        canonical.canonical_json(value)
    except canonical.CanonicalError as exc:
        raise LeverRegistryError(f"{name} is not canonical-safe text") from exc
    return canonical.nfc(value)


def _refusal_event(event_kind: str, resolution: lever_law.LeverResolution) -> Event:
    return {
        "event_kind": event_kind,
        "refusal_code": resolution.refusal_code,
        "meaning": resolution.meaning,
        "minimum_action": resolution.minimum_action,
    }


class LeverRegistry:
    """The append-only, compare-and-swap runtime lever registry.

    :class:`triad_origin.transition.DeterministicMachine` — see the module docstring for the
    exact state shape, envelope kinds, and the RC4 task each branch answers.
    """

    def initial_state(self) -> State:
        return {
            "revision": 0,
            "levers": {},
            "accepted_manifest_digest_sha256": None,
            "attestations": {},
        }

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        kind = envelope.get("kind")
        payload = envelope.get("payload", {})

        if kind == REGISTER_MANIFEST:
            return self._register_manifest(state, payload)
        if kind == ATTEST_RUNTIME:
            return self._attest_runtime(state, payload)
        if kind == RESOLVE_STALENESS:
            return self._resolve_staleness(state, payload)
        raise LeverRegistryError(f"unknown lever-registry envelope kind: {kind!r}")

    # -- REGISTER_MANIFEST (LEV-0032/0040/0043/0048) --------------------------------------------

    def _register_manifest(self, state: State, payload: dict) -> TransitionResult:
        resolution = lever_law.resolve_manifest(payload)
        if not resolution.accepted:
            return TransitionResult(state, (_refusal_event(MANIFEST_REFUSED, resolution),))

        # LEV-0048: exact compare-and-swap — anything but current_revision + 1 is stale, no
        # reordering, no partial commit.
        revision = _require_exact_int(payload.get("revision"), "revision")
        current_revision = state["revision"]
        if revision != current_revision + 1:
            resolution = lever_law.refuse("LEVER_REVISION_STALE")
            return TransitionResult(state, (_refusal_event(MANIFEST_REFUSED, resolution),))

        # LEV-0043: every stored row is digest-bound to the manifest that last set it; a manifest
        # carrying no canonical-safe digest is "not digest-bound" (LEVER_REGISTRY_INCOMPLETE's own
        # declared meaning) and is refused before any row moves.
        manifest_digest = payload.get("manifest_digest_sha256")
        if not isinstance(manifest_digest, str) or not manifest_digest:
            resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
            return TransitionResult(state, (_refusal_event(MANIFEST_REFUSED, resolution),))
        manifest_digest = _require_canonical_text(manifest_digest, "manifest_digest_sha256")

        # LEV-0032/0040: once a baseline key set exists, every subsequent manifest must name that
        # exact set — a missing, dropped, or unknown key rejects the whole manifest, never a
        # partial row update.
        activations = payload.get("activations") or {}
        existing_levers = state["levers"]
        if existing_levers and set(activations) != set(existing_levers):
            resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
            return TransitionResult(state, (_refusal_event(MANIFEST_REFUSED, resolution),))

        new_levers = {
            lever_key: {"value": value, "digest": manifest_digest, "revision": revision}
            for lever_key, value in activations.items()
        }
        new_state = {
            "revision": revision,
            "levers": new_levers,
            "accepted_manifest_digest_sha256": manifest_digest,
            "attestations": dict(state["attestations"]),
        }
        event = {"event_kind": MANIFEST_ACCEPTED, "revision": revision, "levers": new_levers}
        return TransitionResult(new_state, (event,))

    # -- ATTEST_RUNTIME (LEV-0050/0055) ----------------------------------------------------------

    def _attest_runtime(self, state: State, payload: dict) -> TransitionResult:
        engine_id = _require_canonical_text(payload.get("engine_id"), "engine_id")
        accepted_revision = _require_exact_int(payload.get("accepted_revision"), "accepted_revision")
        accepted_digest = payload.get("accepted_manifest_digest_sha256")

        # LEV-0050: a runtime attests the EXACT current revision — digest and revision must both
        # match the registry's own record, or money authority is refused.
        if (
            accepted_digest != state["accepted_manifest_digest_sha256"]
            or accepted_revision != state["revision"]
        ):
            resolution = lever_law.refuse("RUNTIME_LEVER_ATTESTATION_MISMATCH")
            return TransitionResult(state, (_refusal_event(ATTESTATION_REFUSED, resolution),))

        # LEV-0055: a matching digest/revision attested too long ago is still a mismatch — the
        # 15,000 ms reject bound is enforced here, on ingestion, not merely as an emit-cadence hope.
        freshness_age_ms = payload.get("freshness_age_ms")
        if timings.is_stale(freshness_age_ms, _RUNTIME_ATTESTATION_BOUND):
            resolution = lever_law.refuse("RUNTIME_LEVER_ATTESTATION_MISMATCH")
            return TransitionResult(state, (_refusal_event(ATTESTATION_REFUSED, resolution),))

        attestations = dict(state["attestations"])
        attestations[engine_id] = {
            "accepted_revision": accepted_revision, "attested_age_ms": freshness_age_ms,
        }
        new_state = {
            "revision": state["revision"],
            "levers": state["levers"],
            "accepted_manifest_digest_sha256": state["accepted_manifest_digest_sha256"],
            "attestations": attestations,
        }
        event = {"event_kind": ATTESTATION_ACCEPTED, "engine_id": engine_id,
                 "revision": accepted_revision}
        return TransitionResult(new_state, (event,))

    # -- RESOLVE_STALENESS (LEV-0051) ------------------------------------------------------------

    def _resolve_staleness(self, state: State, payload: dict) -> TransitionResult:
        engine_id = _require_canonical_text(payload.get("engine_id"), "engine_id")
        cached_age_ms = payload.get("cached_age_ms")
        if not timings.is_stale(cached_age_ms, _LEVER_CACHE_BOUND):
            return TransitionResult(state)

        # Advisory-only: this transition never mutates the registry's own truth — it reports the
        # minimum containment the stale-cache holder must apply locally, defaulting to the RC4
        # baseline (OFF/OFF/OFF/LIVE) when this engine has never had a row of its own.
        current = dict(lever_law.BASELINE_MANIFEST)
        lever_row = state["levers"].get(engine_id)
        if lever_row is not None:
            current["value"] = lever_row["value"]
            current["digest"] = lever_row["digest"]
            current["revision"] = lever_row["revision"]
        action = lever_law.containment_action("LEVER_REVISION_STALE", current)
        event = {
            "event_kind": STALENESS_FORCED_OFF, "engine_id": engine_id,
            "cached_age_ms": cached_age_ms, "action": action,
        }
        return TransitionResult(state, (event,))

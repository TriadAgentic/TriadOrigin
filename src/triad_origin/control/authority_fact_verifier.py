"""Authority-fact VERIFY-ONLY (B07 — RC3 W09; row A7).

This module verifies two INDEPENDENTLY issued external facts:

  1. ``triad.candidate_authority.v1`` — the governance lease's own assertion of WHICH
     ``engine_cohort`` producer is currently authoritative for an exact scope.
  2. ``triad.producer_lease.v1`` — the technical-writer lease for a topic/partition (a DISTINCT
     concept: who may currently WRITE, not who is economically authoritative).

It NEVER admits a candidate, issues/renews/revokes a lease, or selects money authority — row A7
(``docs/plan/09_OPEN_QUESTIONS.md``) and this repository's ``CLAUDE.md`` ownership law
(``BUILD_DARK_LIBRARY``: "no admission/arbitration"). Every public function either verifies an
already-issued fact or reports a verdict; none constructs a new authoritative fact.

**THE ORDERING LAW** (RC3 W09, verbatim): "Highest valid fencing token wins exact scope;
timestamps cannot override epoch." — comparison is WITHIN one exact scope only (never across
scopes) and is by ``fencing_token`` alone; a later ``issued_at_us`` never overrides a numerically
lower token.

**MANDATORY EDGE BEHAVIOR** (RC3 W09, verbatim): "Stale/duplicate/wildcard token rejects; split
brain stops new entries." Interpreted here (documented — a genuine reading judgment, not RC3
verbatim structure, since ``fencing_token`` is schema-constrained to decimal digits and cannot
itself literally be "*"; see ``docs/plan/09_OPEN_QUESTIONS.md`` row E26):

  * **STALE** — a fact naming a token that does not exceed the currently-accepted highest token
    for its exact scope refuses (it cannot advance authority).
  * **NOT CURRENTLY VALID** — a fact that is well-formed and would otherwise advance the highest
    token, but is not ``state=ACTIVE`` or falls outside its ``[not_before_us, expires_at_us)``
    window at the moment of admission, refuses (``REFUSED_NOT_CURRENTLY_VALID``) BEFORE any
    stale/duplicate/split-brain logic runs — an inactive fact must never become the new
    highest-accepted token for its scope, regardless of how high its token number is.
  * **WILDCARD** — a fact whose ``scope`` is empty, or whose scope carries a literal ``"*"``
    value in any field, claims an unbounded range rather than one exact scope and refuses
    outright — the ordering law only makes sense over an EXACT scope.
  * **DUPLICATE** — a fact naming the EXACT SAME token as one already accepted for that scope: if
    its content is byte-identical to the accepted fact, it is a pure redelivery and is accepted
    idempotently (no state change, no refusal — mirrors this repository's redelivery law
    elsewhere, e.g. ``journal.register_input``); if its content DISAGREES, that is the concrete
    symptom of two issuers believing they hold the same token — refused as a duplicate-token
    conflict AND the scope is latched into **SPLIT BRAIN**.
  * **SPLIT BRAIN** — once latched for a scope, EVERY subsequent admission attempt for that scope
    refuses (``SPLIT_BRAIN_ACTIVE``) — including a fact naming a strictly higher token — until an
    explicit, non-automatic :func:`AuthorityLedger.clear_split_brain` call supplies proof. A
    higher token alone never proves the split is resolved; the rollback law requires "safe state"
    established FIRST.

**READINESS** (RC3 W09, verbatim): "Activation manifest, producer attestation and allocation
current." This module owns only two of those three facts (the authority fact + the technical
writer lease); a "producer attestation" (``triad.engine_attestation.v2``) is E08/E09/venue-truth
territory this repository does not itself hold — :func:`readiness` therefore checks exactly what
it owns and is documented as a NARROWED reading, never silently claiming full RC3 readiness.

**ROLLBACK** (RC3 W09, verbatim): "Revoke scope; prove rejection; issue strictly higher token
only after safe state." This module issues nothing (verify-only); its contribution is
:func:`assert_strictly_higher_token`, a pure comparison an external issuer (out of scope here)
uses to prove a proposed replacement token is lawful BEFORE minting it.

Pure and side-effect-free: no clock, no network, no credential. Every "current" check takes an
explicit ``now_us`` from the caller — nothing here reads a system clock.
"""

from __future__ import annotations

from typing import Callable

from .. import contracts
from ..canonical import canonical_json, sha256_hex

CANDIDATE_AUTHORITY_SCHEMA = "triad.candidate_authority.v1"
PRODUCER_LEASE_SCHEMA = "triad.producer_lease.v1"

ACTIVE_LEASE_STATE = "ACTIVE"
_WILDCARD_MARKER = "*"


class AuthorityFactError(RuntimeError):
    """A fact could not be verified as presented — fail closed, never a guessed verdict."""


def _require_decimal_token(value: object, label: str) -> int:
    if not isinstance(value, str) or not value or not (value == "0" or value.lstrip("0")):
        raise AuthorityFactError(f"{label} must be an exact decimal-string integer: {value!r}")
    try:
        parsed = int(value)
    except ValueError as exc:  # pragma: no cover - schema already constrains this
        raise AuthorityFactError(f"{label} is not an integer: {value!r}") from exc
    if parsed < 0:
        raise AuthorityFactError(f"{label} must be non-negative: {value!r}")
    return parsed


def _is_wildcard_scope(scope: object) -> bool:
    if not isinstance(scope, dict) or not scope:
        return True
    return any(v == _WILDCARD_MARKER for v in scope.values())


def _scope_key(scope: dict) -> str:
    return sha256_hex(canonical_json(scope))


def verify_candidate_authority(
    fact: dict, *, now_us: int, signature_verifier: Callable[[dict], bool] | None = None,
) -> dict:
    """Verify ``fact`` is a well-formed, structurally sound ``candidate_authority.v1`` payload.

    Fails closed (:class:`AuthorityFactError`) on schema violation, a wildcard scope, or (when
    ``signature_verifier`` is supplied) a rejected signature. Does NOT check
    staleness/duplication/split-brain — that is :class:`AuthorityLedger`'s stateful law, since a
    single fact in isolation cannot know about siblings for its scope.

    ``signature_verifier`` is an OPTIONAL caller-injected predicate over the schema-validated
    fact — this module holds no key material (the DARK/no-credential law: row A7,
    ``BUILD_DARK_LIBRARY``) and can never itself cryptographically authenticate a signature.
    Without it, ``signature`` is only checked structurally (a non-empty string, per schema) — a
    caller that needs cryptographic authentication MUST supply the predicate; its absence is
    never silently read as "authenticated".
    """
    if not isinstance(now_us, int) or isinstance(now_us, bool):
        raise AuthorityFactError("now_us must be an int")
    try:
        contracts.validate_payload(CANDIDATE_AUTHORITY_SCHEMA, fact)
    except contracts.ContractError as exc:
        raise AuthorityFactError(f"candidate_authority fact failed schema validation: {exc}") \
            from exc
    if _is_wildcard_scope(fact["scope"]):
        raise AuthorityFactError("candidate_authority fact carries a wildcard scope")
    _require_decimal_token(fact["fencing_token"], "fencing_token")
    verified = dict(fact)
    if signature_verifier is not None and not signature_verifier(verified):
        raise AuthorityFactError("candidate_authority fact failed signature verification")
    return verified


def is_currently_valid_authority(fact: dict, *, now_us: int) -> bool:
    """True iff ``fact`` (already schema-verified) is ``state=ACTIVE`` and within its
    ``[not_before_us, expires_at_us)`` window at ``now_us``.

    ``state`` is the authoritative revocation/currency signal — mirroring
    :func:`is_currently_active_lease`, ``revoked_at_us`` is a REQUIRED integer field on this
    schema (never nullable) whose specific value is only semantically meaningful when
    ``state == "REVOKED"``; a bare "is it set" check would be vacuous (it is always set) and is
    not this schema's revocation signal.
    """
    if fact.get("state") != "ACTIVE":
        return False
    not_before = fact.get("not_before_us")
    expires_at = fact.get("expires_at_us")
    if not isinstance(not_before, int) or isinstance(not_before, bool):
        return False
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        return False
    return not_before <= now_us < expires_at


def verify_producer_lease(
    fact: dict, *, now_us: int, signature_verifier: Callable[[dict], bool] | None = None,
) -> dict:
    """Verify ``fact`` is a well-formed ``producer_lease.v1`` payload. Fails closed on schema
    violation or (when ``signature_verifier`` is supplied) a rejected signature. Does not itself
    judge currency — see :func:`is_currently_active_lease`.

    See :func:`verify_candidate_authority` for the ``signature_verifier`` contract — this module
    holds no key material and never authenticates a signature on its own.
    """
    if not isinstance(now_us, int) or isinstance(now_us, bool):
        raise AuthorityFactError("now_us must be an int")
    try:
        contracts.validate_payload(PRODUCER_LEASE_SCHEMA, fact)
    except contracts.ContractError as exc:
        raise AuthorityFactError(f"producer_lease fact failed schema validation: {exc}") from exc
    verified = dict(fact)
    if signature_verifier is not None and not signature_verifier(verified):
        raise AuthorityFactError("producer_lease fact failed signature verification")
    return verified


def is_currently_active_lease(fact: dict, *, now_us: int) -> bool:
    """True iff ``fact`` (already schema-verified) is ``state=ACTIVE`` and within its
    ``[not_before_us, expires_at_us)`` window at ``now_us``.

    ``state`` is the authoritative revocation/currency signal (``revoked_at_us`` is a REQUIRED
    integer on this schema, never nullable, and only semantically meaningful when
    ``state == "REVOKED"`` — see the golden ``ISSUED`` vector, which carries a real but
    not-yet-meaningful ``revoked_at_us``).
    """
    if fact.get("state") != ACTIVE_LEASE_STATE:
        return False
    not_before = fact.get("not_before_us")
    expires_at = fact.get("expires_at_us")
    if not isinstance(not_before, int) or isinstance(not_before, bool):
        return False
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        return False
    return not_before <= now_us < expires_at


def assert_strictly_higher_token(current_highest_token: int, proposed_token: object) -> int:
    """The rollback law's pure comparison: a replacement token must be STRICTLY higher than the
    currently-accepted one. Raises :class:`AuthorityFactError` otherwise — this module issues
    nothing; an external issuer calls this BEFORE minting a real replacement fact."""
    if (isinstance(current_highest_token, bool) or not isinstance(current_highest_token, int)
            or current_highest_token < 0):
        raise AuthorityFactError("current_highest_token must be a non-negative int")
    if isinstance(proposed_token, str):
        proposed = _require_decimal_token(proposed_token, "proposed_token")
    elif isinstance(proposed_token, int) and not isinstance(proposed_token, bool):
        proposed = proposed_token
    else:
        raise AuthorityFactError(f"proposed_token must be an int or decimal string: "
                                  f"{proposed_token!r}")
    if proposed <= current_highest_token:
        raise AuthorityFactError(
            f"proposed_token {proposed} does not strictly exceed current_highest_token "
            f"{current_highest_token}")
    return proposed


class AdmissionResult:
    """The outcome of one :meth:`AuthorityLedger.admit_fact` call. Never a picked "winner" — a
    named, structural outcome only."""

    __slots__ = ("accepted", "reason", "fact", "split_brain")

    def __init__(self, *, accepted: bool, reason: str, fact: dict | None, split_brain: bool):
        self.accepted = accepted
        self.reason = reason
        self.fact = fact
        self.split_brain = split_brain

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (f"AdmissionResult(accepted={self.accepted!r}, reason={self.reason!r}, "
                f"split_brain={self.split_brain!r})")


ACCEPTED = "ACCEPTED"
ACCEPTED_DUPLICATE_REDELIVERY = "ACCEPTED_DUPLICATE_REDELIVERY"
REFUSED_STALE = "REFUSED_STALE"
REFUSED_NOT_CURRENTLY_VALID = "REFUSED_NOT_CURRENTLY_VALID"
REFUSED_DUPLICATE_TOKEN_CONFLICT = "REFUSED_DUPLICATE_TOKEN_CONFLICT"
REFUSED_SPLIT_BRAIN_ACTIVE = "REFUSED_SPLIT_BRAIN_ACTIVE"


class AuthorityLedger:
    """A per-scope, in-memory, side-effect-free record of the highest accepted token.

    Not itself durable or authoritative — a thin, testable law over a caller-owned in-memory
    dict. Persisting this state (a durable ledger/registry) is the estate's decision, mirroring
    :mod:`triad_origin.bindings`'s read-only-over-a-frozen-file posture; this class exists so the
    stateful STALE/DUPLICATE/SPLIT-BRAIN law has ONE tested implementation rather than being
    re-derived ad hoc by every caller.

    ``signature_verifier`` (optional, constructor-injected) is threaded to every
    :func:`verify_candidate_authority` call this ledger makes — see that function's docstring for
    the contract. Left ``None``, admission checks the fact structurally only, exactly as before
    this parameter existed.
    """

    def __init__(self, *, signature_verifier: Callable[[dict], bool] | None = None) -> None:
        self._by_scope: dict[str, dict] = {}
        self._split_brain: set[str] = set()
        self._signature_verifier = signature_verifier

    def admit_fact(self, fact: dict, *, now_us: int) -> AdmissionResult:
        verified = verify_candidate_authority(
            fact, now_us=now_us, signature_verifier=self._signature_verifier)
        scope = verified["scope"]
        key = _scope_key(scope)
        token = _require_decimal_token(verified["fencing_token"], "fencing_token")

        # The fact's OWN currency is checked BEFORE any stateful ledger logic (split-brain,
        # stale, duplicate) — an inactive fact (not ACTIVE, or outside its validity window) must
        # never advance, or even be latched as, the highest-accepted token for its scope. This
        # is a property of the fact alone, independent of what the ledger currently holds.
        if not is_currently_valid_authority(verified, now_us=now_us):
            return AdmissionResult(
                accepted=False, reason=REFUSED_NOT_CURRENTLY_VALID, fact=None, split_brain=False)

        if key in self._split_brain:
            return AdmissionResult(
                accepted=False, reason=REFUSED_SPLIT_BRAIN_ACTIVE, fact=None, split_brain=True)

        entry = self._by_scope.get(key)
        if entry is None:
            self._by_scope[key] = {"scope": scope, "highest_token": token, "fact": verified}
            return AdmissionResult(
                accepted=True, reason=ACCEPTED, fact=verified, split_brain=False)

        highest_token = entry["highest_token"]
        if token < highest_token:
            return AdmissionResult(
                accepted=False, reason=REFUSED_STALE, fact=None, split_brain=False)
        if token == highest_token:
            if canonical_json(verified) == canonical_json(entry["fact"]):
                return AdmissionResult(
                    accepted=True, reason=ACCEPTED_DUPLICATE_REDELIVERY, fact=verified,
                    split_brain=False)
            # Same token, disagreeing content: the concrete split-brain symptom. Latch and
            # refuse — never silently pick one side.
            self._split_brain.add(key)
            return AdmissionResult(
                accepted=False, reason=REFUSED_DUPLICATE_TOKEN_CONFLICT, fact=None,
                split_brain=True)

        # token > highest_token, no active split-brain latch: accept and advance.
        self._by_scope[key] = {"scope": scope, "highest_token": token, "fact": verified}
        return AdmissionResult(accepted=True, reason=ACCEPTED, fact=verified, split_brain=False)

    def current_for_scope(self, scope: dict) -> dict | None:
        """The verbatim currently-accepted highest-token fact for ``scope`` — a read of record,
        never a consumption. Returns ``None`` if the scope is unknown OR split-brain-latched
        (never a fabricated "current" fact under an active split)."""
        key = _scope_key(scope)
        if key in self._split_brain:
            return None
        entry = self._by_scope.get(key)
        return dict(entry["fact"]) if entry is not None else None

    def is_split_brain(self, scope: dict) -> bool:
        return _scope_key(scope) in self._split_brain

    def clear_split_brain(self, scope: dict, *, proof: str) -> None:
        """Lift the split-brain latch for ``scope``. Never automatic — the caller supplies
        non-empty ``proof`` (the rollback law's "prove rejection" / "safe state" requirement).
        Does NOT re-admit any previously refused fact; the next :meth:`admit_fact` call for this
        scope starts fresh from whatever was accepted before the conflicting token arrived."""
        if not isinstance(proof, str) or not proof:
            raise AuthorityFactError("clearing split-brain requires a non-empty proof string")
        self._split_brain.discard(_scope_key(scope))


def readiness(
    scope: dict, authority_fact: dict | None, lease_fact: dict | None, *, now_us: int,
    authority_signature_verifier: Callable[[dict], bool] | None = None,
    lease_signature_verifier: Callable[[dict], bool] | None = None,
) -> dict:
    """The NARROWED RC3 readiness check this module legitimately owns.

    RC3 W09 names three readiness facts ("activation manifest, producer attestation and
    allocation current"); this module owns exactly two (the authority fact's
    ``activation_manifest_id`` + the technical-writer lease's currency) — a "producer
    attestation" (``triad.engine_attestation.v2``) is out of this repository's ownership
    (E08/E09/venue truth) and is reported as :data:`NOT_OWNED_HERE`, never silently assumed true.

    Both facts, when present, must carry a ``scope`` EXACTLY equal to the requested ``scope`` — a
    fact issued for a DIFFERENT scope (even one that looks "broader", e.g. an empty/wildcard-
    shaped lease scope) is never assumed to cover the requested one; a mismatch is reported and
    folds into ``ready=False`` rather than silently reusing a foreign fact. Mirrors the ordering
    law's own "EXACT scope" discipline (see the module docstring).

    ``authority_signature_verifier``/``lease_signature_verifier`` are threaded verbatim to
    :func:`verify_candidate_authority`/:func:`verify_producer_lease` — see their docstrings.

    Returns a dict naming every conjunct explicitly — never a bare boolean.
    """
    result = {
        "authority_fact_present": authority_fact is not None,
        "authority_fact_valid": False,
        "authority_scope_matches": False,
        "activation_manifest_named": False,
        "lease_present": lease_fact is not None,
        "lease_active": False,
        "lease_scope_matches": False,
        "producer_attestation": "NOT_OWNED_HERE",
        "ready": False,
    }
    if authority_fact is not None:
        try:
            verified_authority = verify_candidate_authority(
                authority_fact, now_us=now_us, signature_verifier=authority_signature_verifier)
        except AuthorityFactError:
            verified_authority = None
        if verified_authority is not None:
            result["authority_fact_valid"] = is_currently_valid_authority(
                verified_authority, now_us=now_us)
            result["authority_scope_matches"] = verified_authority.get("scope") == scope
            manifest_id = verified_authority.get("activation_manifest_id")
            result["activation_manifest_named"] = bool(
                isinstance(manifest_id, str) and manifest_id)
    if lease_fact is not None:
        try:
            verified_lease = verify_producer_lease(
                lease_fact, now_us=now_us, signature_verifier=lease_signature_verifier)
        except AuthorityFactError:
            verified_lease = None
        if verified_lease is not None:
            result["lease_active"] = is_currently_active_lease(verified_lease, now_us=now_us)
            result["lease_scope_matches"] = verified_lease.get("scope") == scope
    result["ready"] = (
        result["authority_fact_valid"]
        and result["authority_scope_matches"]
        and result["activation_manifest_named"]
        and result["lease_active"]
        and result["lease_scope_matches"]
    )
    return result

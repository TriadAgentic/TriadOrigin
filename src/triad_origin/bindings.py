"""binding.v2 registry consumption (B01R).

Loads the structurally migrated binding registry
(``docs/control/binding_registry.v2.json``) and enforces the consumption law:

  * every row re-validates against the pinned ``triad.binding.v2`` payload schema + semantic
    law + digest identity at load time (a tampered or hand-edited registry fails closed);
  * no two non-superseded ACTIVE rows may claim one semantic slot (the overlap law);
  * **a blocked binding is not consumable** — ``resolve`` returns only ACTIVE rows and raises a
    named ``BindingBlockedError`` carrying the source status and disposition for anything else.
    Structural migration never activates a row; ratification is a governance act recorded in the
    control bundle, never a code default.

Deterministic and read-only: no clock, no network, no mutation of the registry.
"""

from __future__ import annotations

import json
import pathlib
import threading
from dataclasses import dataclass, field
from typing import Any

from . import contracts
from . import governance
from .canonical import CanonicalError, canonical_json, is_sha256_hex, loads_canonical, sha256_hex

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# B01C-BIND-03: an installed wheel must not depend on the repository-relative docs/control tree.
# setup.py copies the canonical bundle into the package as _control/binding_registry.v2.json; the
# repository copy is the editable/test fallback (repository-relative paths are test-only).
_PACKAGED_REGISTRY = pathlib.Path(__file__).resolve().parent / "_control" / "binding_registry.v2.json"
_SOURCE_REGISTRY = _ROOT / "docs" / "control" / "binding_registry.v2.json"
DEFAULT_REGISTRY_PATH = _PACKAGED_REGISTRY if _PACKAGED_REGISTRY.is_file() else _SOURCE_REGISTRY

REGISTRY_VERSION = "origin.binding-registry.v2"

# B01C-BIND-02: the bundle is exactly 105 unique binding rows; row_count / unique-id / declared
# status counts must all agree, or the loader refuses before any consumption.
REQUIRED_ROW_COUNT = 105

# B01C-BIND-04: fields that an ACTIVE (non-superseded) binding MUST carry as resolved values — an
# unresolved sentinel here is a blocked binding masquerading as active. ``source_binding_id`` and
# ``rc2_source_digest`` are excluded: an RC3-originated active binding legitimately has neither.
_ACTIVE_RESOLVED_FIELDS = (
    "declared_value", "unit", "unit_contract", "condition", "activation_scope",
    "precedence", "parameter_id", "semantic_slot", "formula_id",
)
_SENTINEL_TOKENS = {"", "TBD", "UNKNOWN", "UNSET", "N/A", "NA", "NONE", "NULL", "PENDING", "*"}


def _is_sentinel(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        v = value.strip()
        return v == "" or v.upper() in _SENTINEL_TOKENS or "*" in v
    return False


class BindingRegistryError(RuntimeError):
    """The registry itself is invalid/tampered — fail closed before any consumption."""


class BindingBlockedError(RuntimeError):
    """A non-ACTIVE binding was asked for a value. Never consumable."""

    def __init__(self, binding_id: str, status: str, disposition: str):
        super().__init__(
            f"BINDING_NOT_CONSUMABLE: {binding_id} status={status} — {disposition or 'blocked'}")
        self.binding_id = binding_id
        self.status = status
        self.disposition = disposition


class BindingUnknownError(KeyError):
    """No binding row exists for the requested slot/ID — fail closed, never a default."""


class BindingRegistry:
    def __init__(self, registry: dict):
        if registry.get("registry_version") != REGISTRY_VERSION:
            raise BindingRegistryError(
                f"unknown binding registry version: {registry.get('registry_version')!r}")
        rows = registry.get("rows")
        if not isinstance(rows, list) or not rows:
            raise BindingRegistryError("binding registry has no rows")
        # B01C-BIND-02: exact inventory. The declared row_count, the actual row count, and the
        # unique binding-id count must all equal REQUIRED_ROW_COUNT; the source-bundle digest must
        # be canonical hex64 (a recomputable row hash is not authenticated identity — the signed
        # bundle-root check lives in build_resolved_bundle, BIND-01/05).
        declared_row_count = registry.get("row_count")
        if declared_row_count != len(rows):
            raise BindingRegistryError(
                f"row_count {declared_row_count!r} disagrees with {len(rows)} rows")
        if len(rows) != REQUIRED_ROW_COUNT:
            raise BindingRegistryError(
                f"binding bundle must carry exactly {REQUIRED_ROW_COUNT} rows, found {len(rows)}")
        try:
            governance.assert_hex64(registry.get("source_bundle_digest"), "source_bundle_digest")
        except governance.GovernanceError as exc:
            raise BindingRegistryError(f"BINDING_BUNDLE_DIGEST_INVALID: {exc}") from exc
        by_id: dict[str, dict] = {}
        by_slot_active: dict[str, dict] = {}
        active_scope_keys: dict[tuple[str, str], str] = {}
        counts: dict[str, int] = {}
        for row in rows:
            try:
                contracts.validate_payload("triad.binding.v2", row)
            except contracts.SchemaValidatorUnavailable:
                # B01C-CON-03: the full validator is absent — fail closed with the precise
                # environment reason, not a "registry invalid" wrap (the bytes may be fine).
                raise
            except contracts.ContractError as exc:
                raise BindingRegistryError(
                    f"registry row {row.get('binding_id') if isinstance(row, dict) else '?'!r} "
                    f"invalid: {exc}") from exc
            unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
            if row.get("binding_digest") != sha256_hex(canonical_json(unsigned)):
                raise BindingRegistryError(
                    f"BINDING_DIGEST_MISMATCH in registry row {row.get('binding_id')!r}")
            binding_id = row["binding_id"]
            if binding_id in by_id:
                raise BindingRegistryError(f"duplicate binding_id {binding_id!r}")
            by_id[binding_id] = row
            counts[row["status"]] = counts.get(row["status"], 0) + 1
            if row["status"] == "ACTIVE" and not row.get("superseded_by"):
                slot = row["semantic_slot"]
                if slot in by_slot_active:
                    raise BindingRegistryError(
                        f"OVERLAP: {by_slot_active[slot]['binding_id']} and {binding_id} both "
                        f"claim active semantic slot {slot!r}")
                by_slot_active[slot] = row
                # B01C-BIND-04: an ACTIVE binding may not carry an unresolved sentinel in a
                # resolved-semantic field (that would be a blocked binding wearing an active label).
                for f in _ACTIVE_RESOLVED_FIELDS:
                    if _is_sentinel(row.get(f)):
                        raise BindingRegistryError(
                            f"ACTIVE_BINDING_UNRESOLVED_FIELD: {binding_id} field {f}="
                            f"{row.get(f)!r}")
                # B01C-BIND-06: no two ACTIVE rows may collide on the same (parameter, activation
                # scope) key — duplicate semantic scope, closed independently of binding-id
                # uniqueness and of the slot overlap above.
                scope_key = (row["parameter_id"], row["activation_scope"])
                if scope_key in active_scope_keys:
                    raise BindingRegistryError(
                        f"SCOPE_COLLISION: {active_scope_keys[scope_key]} and {binding_id} share "
                        f"active scope {scope_key!r}")
                active_scope_keys[scope_key] = binding_id
        if len(by_id) != REQUIRED_ROW_COUNT:
            raise BindingRegistryError(
                f"expected {REQUIRED_ROW_COUNT} unique binding_ids, found {len(by_id)}")
        declared = registry.get("status_counts")
        if declared != dict(sorted(counts.items())):
            raise BindingRegistryError(
                f"registry status_counts {declared} disagree with rows {counts}")
        self._registry_digest = registry.get("source_bundle_digest")
        self._by_id = by_id
        self._by_slot_active = by_slot_active
        self._counts = counts

    # -- read faces ---------------------------------------------------------------------------

    def status_counts(self) -> dict:
        return dict(sorted(self._counts.items()))

    def source_bundle_digest(self) -> str:
        """The declared source-bundle digest (a self-hash of record, not authenticated identity)."""
        return self._registry_digest

    def status_counts_total(self) -> int:
        """The exact total row count (== :data:`REQUIRED_ROW_COUNT`)."""
        return sum(self._counts.values())

    def active_rows(self) -> list[dict]:
        """Copies of every ACTIVE, non-superseded binding row (the consumable inventory)."""
        return [dict(row) for row in self._by_slot_active.values()]

    def rows(self) -> list[dict]:
        """Copies of EVERY registry row (any status), sorted by binding_id.

        The complete binding row set a v2 sealed bundle carries (spec §C.1 ``rows[]`` — "the
        complete binding row set, exact bytes"). A read face of record, not a consumption.
        """
        return [dict(self._by_id[binding_id]) for binding_id in sorted(self._by_id)]

    def formula_is_complete(self, formula_id: str) -> bool:
        """True iff every non-superseded registered row for ``formula_id`` is ACTIVE.

        B01C-BIND-04 formula completeness: one ACTIVE row may never hide a blocked required row.
        A superseded row is a replaced predecessor and does not block; any live non-ACTIVE row
        (BLOCKED/PROPOSED/…) means the formula's set is incomplete and must not be consumable.
        """
        live = [row for row in self._by_id.values()
                if row["formula_id"] == formula_id and not row.get("superseded_by")]
        if not live:
            return False
        return all(row["status"] == "ACTIVE" for row in live)

    def row(self, binding_id: str) -> dict:
        """The verbatim registry row (any status) — a read of record, not a consumption."""
        try:
            return dict(self._by_id[binding_id])
        except KeyError:
            raise BindingUnknownError(f"unknown binding_id {binding_id!r}") from None

    # -- consumption law ----------------------------------------------------------------------

    def resolve(self, semantic_slot: str) -> dict:
        """Return the single ACTIVE binding for ``semantic_slot`` or fail closed.

        A blocked row raises :class:`BindingBlockedError` (named, with the source status and
        disposition); an unknown slot raises :class:`BindingUnknownError`. There is no default
        and no substitute.
        """
        active = self._by_slot_active.get(semantic_slot)
        if active is not None:
            return dict(active)
        blocked = [row for row in self._by_id.values()
                   if row["semantic_slot"] == semantic_slot]
        if blocked:
            row = sorted(blocked, key=lambda r: r["binding_id"])[0]
            raise BindingBlockedError(
                row["binding_id"], row["status"], row.get("disposition_reason", ""))
        raise BindingUnknownError(f"no binding declares semantic slot {semantic_slot!r}")

    def resolve_for_formula(self, formula_id: str) -> list[dict]:
        """All ACTIVE bindings for a formula; blocked rows are named in the error if none."""
        active = sorted(
            (row for row in self._by_slot_active.values() if row["formula_id"] == formula_id),
            key=lambda r: r["binding_id"])
        if active:
            return [dict(row) for row in active]
        blocked = sorted(
            (row for row in self._by_id.values() if row["formula_id"] == formula_id),
            key=lambda r: r["binding_id"])
        if blocked:
            first = blocked[0]
            raise BindingBlockedError(
                first["binding_id"], first["status"], first.get("disposition_reason", ""))
        raise BindingUnknownError(f"no binding declares formula {formula_id!r}")


def load_registry(path: str | pathlib.Path = DEFAULT_REGISTRY_PATH) -> BindingRegistry:
    try:
        registry = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BindingRegistryError(f"binding registry unreadable: {exc}") from exc
    return BindingRegistry(registry)


# =================================================================================================
# C.1 (B02C, spec §C.1) — SealedParameterBundle v2: content-addressed, unforgeable by construction.
#
# A Python object is never a security boundary. ``_CONSTRUCTION_TOKEN`` is DELETED entirely:
# construction of every type here is UNRESTRICTED — acceptance is what is guarded, and trust
# derives exclusively from re-verifiable content. Forging acceptance requires forging Ed25519
# signatures over the pinned trust registry. :func:`triad_origin.transition.require_bundle`
# re-verifies the full content law on EVERY call (memoizable only by digest with a hand-rolled
# constant-time compare against a process-pinned expected digest) and only then returns a
# :class:`VerifiedCapability` handle carrying the digest.
# =================================================================================================

# The bundle-root signature set is owner-anchored: a single AUTHORITY_OWNER signature over the
# exact canonical signed bytes is the minimum, and it must verify cryptographically (absent
# verifier => fail closed, never a silent pass).
_BUNDLE_REQUIRED_ROLES = ("AUTHORITY_OWNER",)
_BUNDLE_THRESHOLD = 1


class BindingBundleUnauthenticated(RuntimeError):
    """The bundle root carried no verifiable owner signature — no capability is constructed."""

    def __init__(self, reason: str):
        super().__init__(f"BINDING_BUNDLE_UNAUTHENTICATED: {reason}")
        self.reason = reason


class CapabilityForgeryError(TypeError):
    """An object without the sealed-bundle shape was presented on the production path."""


class SealedBundleRejected(RuntimeError):
    """A sealed bundle failed the content-law acceptance — typed reason, never a silent pass."""

    def __init__(self, reason: str):
        super().__init__(f"SEALED_BUNDLE_REJECTED: {reason}")
        self.reason = reason


class BlockedBindingIncomplete(SealedBundleRejected):
    """Typed refusal ``BLOCKED_BINDING_INCOMPLETE{formula_id}`` (spec §C.1 step 5).

    The REQUESTING formula's binding set is not complete-and-ACTIVE in the presented bundle.
    """

    def __init__(self, formula_id: str):
        reason = f"BLOCKED_BINDING_INCOMPLETE:{formula_id}"
        RuntimeError.__init__(self, reason)
        self.reason = reason
        self.formula_id = formula_id


class TrustRegistryPinError(RuntimeError):
    """The process trust-registry pin is absent, conflicting, or fails its cross-check."""


# --- constant-time comparison (hand-rolled over bytes — no hmac import on the runtime path) ------
def ct_bytes_equal(a: object, b: object) -> bool:
    """Constant-time byte equality. Non-bytes input compares unequal (fail closed).

    The scan length is ``max(len(a), len(b))`` and every position is visited regardless of where
    the first difference lies; only the (public) lengths shape the timing.
    """
    if not isinstance(a, (bytes, bytearray)) or not isinstance(b, (bytes, bytearray)):
        return False
    la, lb = len(a), len(b)
    diff = la ^ lb
    n = la if la >= lb else lb
    for i in range(n):
        x = a[i] if i < la else 0
        y = b[i] if i < lb else 0
        diff |= x ^ y
    return diff == 0


def ct_hex_equal(a: object, b: object) -> bool:
    """Constant-time equality of two hex-digest strings (non-string input compares unequal)."""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return ct_bytes_equal(a.encode("utf-8"), b.encode("utf-8"))


# --- the process trust-registry pin (spec §C.1 step 2: set-once at startup, cross-checked) --------
_TRUST_PIN_LOCK = threading.Lock()
_TRUST_PIN: list[str] = []  # at most one hex64 entry — the set-once process pin


def pin_trust_registry_digest(digest_hex: str) -> None:
    """Set-once process pin of the expected trust-registry digest (startup act).

    A second call with the identical digest is a no-op; a different digest is a refusal — the pin
    can never be repointed inside a running process.
    """
    try:
        governance.assert_hex64(digest_hex, "trust_registry_digest_pin")
    except governance.GovernanceError as exc:
        raise TrustRegistryPinError(f"TRUST_REGISTRY_PIN_INVALID: {exc}") from exc
    with _TRUST_PIN_LOCK:
        if _TRUST_PIN:
            if ct_hex_equal(_TRUST_PIN[0], digest_hex):
                return
            raise TrustRegistryPinError("TRUST_REGISTRY_PIN_ALREADY_SET")
        _TRUST_PIN.append(digest_hex)


def pinned_trust_registry_digest() -> str | None:
    """The process-pinned expected trust-registry digest, or ``None`` when not yet pinned."""
    with _TRUST_PIN_LOCK:
        return _TRUST_PIN[0] if _TRUST_PIN else None


def cross_check_trust_registry_pin(repository_trust_registry_bytes: bytes) -> None:
    """Cross-check the process pin against the repository trust-file bytes (startup law).

    The caller reads the repository trust-registry file and injects its exact bytes (this module
    performs no file I/O on the semantic path). An absent pin or a digest mismatch raises — the
    pin and the repository file must agree before any acceptance runs.
    """
    if not isinstance(repository_trust_registry_bytes, (bytes, bytearray)):
        raise TrustRegistryPinError("TRUST_REGISTRY_BYTES_INVALID")
    pin = pinned_trust_registry_digest()
    if pin is None:
        raise TrustRegistryPinError("TRUST_REGISTRY_UNPINNED")
    if not ct_hex_equal(sha256_hex(bytes(repository_trust_registry_bytes)), pin):
        raise TrustRegistryPinError("TRUST_REGISTRY_PIN_MISMATCH")


def _reset_trust_registry_pin_for_tests() -> None:
    """TEST-ONLY: clear the set-once pin so isolated tests can pin their own fixture registry."""
    with _TRUST_PIN_LOCK:
        _TRUST_PIN.clear()


def canonical_bundle_root(
    *,
    bundle_id: str,
    bundle_version: str,
    source_bundle_digest: str,
    authority_digest: str,
    engine: str,
    plane: str,
    environment: str,
    scope: str,
    row_count: int,
    status_counts: dict,
) -> bytes:
    """The exact canonical bytes an owner signs to authenticate a binding bundle root.

    Every replay-controlling field is bound: the bundle identity, the source-bundle digest, the
    authority-package digest, the engine/plane/environment/scope the capability is valid for, and
    the inventory (row count + status counts). A one-byte change anywhere yields different bytes
    and therefore a broken signature.
    """
    governance.assert_hex64(source_bundle_digest, "source_bundle_digest")
    governance.assert_hex64(authority_digest, "authority_digest")
    return canonical_json({
        "root_kind": "origin.binding-bundle-root.v1",
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
        "source_bundle_digest": source_bundle_digest,
        "authority_digest": authority_digest,
        "engine": engine,
        "plane": plane,
        "environment": environment,
        "scope": scope,
        "row_count": row_count,
        "status_counts": dict(sorted(status_counts.items())),
    })


class ResolvedParameterBundle:
    """LEGACY (v1) resolved-bundle record — retained ONLY for the C.2 tool's offline selftest.

    Under the §C.1 v2 law this object is NOT a security boundary and is NOT accepted anywhere on
    the production path: :func:`triad_origin.transition.require_bundle` consumes only the
    content-addressed :class:`SealedParameterBundle` shape and re-verifies it on every call.
    Construction is unrestricted (the ``_CONSTRUCTION_TOKEN`` gate is DELETED — spec §C.1);
    :func:`build_resolved_bundle` still authenticates before constructing, so the C.2 tool
    (``tools/verify_binding_bundle.py``) keeps its offline selftest until its own v2 train lands.
    Per the §C.1 rename law the v1 ``bundle_root_digest`` face is GONE: ``source_bundle_digest``
    is the source-inventory self-hash (partial identity) and ``signed_root_digest`` is the
    actually-signed canonical root — a partial digest never presents as full capability identity.
    """

    __slots__ = (
        "_bundle_id", "_bundle_version", "_source_bundle_digest", "_signed_root_digest",
        "_trust_registry_digest", "_authority_digest", "_engine", "_plane", "_environment",
        "_scope", "_signer_key_ids", "_verification_reason", "_row_count", "_status_counts",
        "_by_param", "_by_slot", "_formula_rows",
    )

    def __init__(self, **fields: Any):
        object.__setattr__(self, "_bundle_id", fields["bundle_id"])
        object.__setattr__(self, "_bundle_version", fields["bundle_version"])
        object.__setattr__(self, "_source_bundle_digest", fields["source_bundle_digest"])
        object.__setattr__(self, "_signed_root_digest", fields["signed_root_digest"])
        object.__setattr__(self, "_trust_registry_digest", fields["trust_registry_digest"])
        object.__setattr__(self, "_authority_digest", fields["authority_digest"])
        object.__setattr__(self, "_engine", fields["engine"])
        object.__setattr__(self, "_plane", fields["plane"])
        object.__setattr__(self, "_environment", fields["environment"])
        object.__setattr__(self, "_scope", fields["scope"])
        object.__setattr__(self, "_signer_key_ids", tuple(fields["signer_key_ids"]))
        object.__setattr__(self, "_verification_reason", fields["verification_reason"])
        object.__setattr__(self, "_row_count", fields["row_count"])
        object.__setattr__(self, "_status_counts", dict(sorted(fields["status_counts"].items())))
        # Canonical, frozen byte snapshots — read faces re-hydrate copies, never expose internals.
        object.__setattr__(self, "_by_param", dict(fields["by_param"]))
        object.__setattr__(self, "_by_slot", dict(fields["by_slot"]))
        object.__setattr__(self, "_formula_rows", dict(fields["formula_rows"]))

    def __setattr__(self, name: str, value: Any) -> None:  # immutable after construction
        raise CapabilityForgeryError("ResolvedParameterBundle is immutable")

    def __delattr__(self, name: str) -> None:
        raise CapabilityForgeryError("ResolvedParameterBundle is immutable")

    # -- authenticated identity (read-only marker) --------------------------------------------
    @property
    def bundle_id(self) -> str:
        return self._bundle_id

    @property
    def bundle_version(self) -> str:
        return self._bundle_version

    @property
    def source_bundle_digest(self) -> str:
        """The source-inventory self-hash (partial identity — never full capability identity)."""
        return self._source_bundle_digest

    @property
    def signed_root_digest(self) -> str:
        """SHA-256 of the actually-signed canonical bundle-root bytes (full identity)."""
        return self._signed_root_digest

    def verification(self) -> dict:
        """The verification marker of record — signer ids, digests, and the builder's reason.

        A copy of record. Under the v2 law this marker is NOT trusted by any acceptance path;
        content re-verification in :func:`require_bundle` is the only trust source.
        """
        return {
            "bundle_id": self._bundle_id,
            "bundle_version": self._bundle_version,
            "source_bundle_digest": self._source_bundle_digest,
            "signed_root_digest": self._signed_root_digest,
            "trust_registry_digest": self._trust_registry_digest,
            "authority_digest": self._authority_digest,
            "signer_key_ids": list(self._signer_key_ids),
            "verification_reason": self._verification_reason,
            "engine": self._engine,
            "plane": self._plane,
            "environment": self._environment,
            "scope": self._scope,
            "row_count": self._row_count,
            "status_counts": dict(sorted(self._status_counts.items())),
        }

    # -- consumption faces (narrow, never widen) ----------------------------------------------
    def require(self, parameter_id: str) -> Any:
        """The declared value for an ACTIVE parameter, or fail closed (never a default)."""
        row = self._by_param.get(parameter_id)
        if row is None:
            raise BindingUnknownError(
                f"no ACTIVE binding declares parameter {parameter_id!r} in this capability")
        return row["declared_value"]

    def resolve(self, semantic_slot: str) -> dict:
        """The full ACTIVE binding row for a semantic slot (a copy), or fail closed."""
        row = self._by_slot.get(semantic_slot)
        if row is None:
            raise BindingUnknownError(
                f"no ACTIVE binding declares semantic slot {semantic_slot!r} in this capability")
        return dict(row)

    def for_formula(self, formula_id: str) -> list[dict]:
        """The COMPLETE ACTIVE binding set for a formula, or fail closed.

        B01C-BIND-04 formula completeness: one ACTIVE row can never hide a blocked required row.
        The capability only carries verified ACTIVE rows; a formula whose registered set is not
        wholly ACTIVE was refused at :func:`build_resolved_bundle` and cannot be resolved here.
        """
        rows = self._formula_rows.get(formula_id)
        if not rows:
            raise BindingUnknownError(
                f"no complete ACTIVE binding set for formula {formula_id!r} in this capability")
        return [dict(row) for row in rows]

    def narrow(self, parameter_ids: "set[str] | frozenset[str] | tuple[str, ...]") -> "ResolvedParameterBundle":
        """Return a strictly narrower capability over a subset of ACTIVE parameters.

        Every requested id must already be ACTIVE in this capability (you cannot name a parameter
        the owner did not authenticate), so the result is always a subset — never a widening.
        """
        keep = set(parameter_ids)
        unknown = keep - set(self._by_param)
        if unknown:
            raise CapabilityForgeryError(
                f"narrow() cannot widen a capability; unknown parameters {sorted(unknown)}")
        by_param = {pid: row for pid, row in self._by_param.items() if pid in keep}
        kept_slots = {row["semantic_slot"] for row in by_param.values()}
        by_slot = {slot: row for slot, row in self._by_slot.items() if slot in kept_slots}
        formula_rows = {
            fid: [r for r in rows if r["parameter_id"] in keep]
            for fid, rows in self._formula_rows.items()
        }
        formula_rows = {fid: rows for fid, rows in formula_rows.items() if rows}
        return ResolvedParameterBundle(
            bundle_id=self._bundle_id,
            bundle_version=self._bundle_version,
            source_bundle_digest=self._source_bundle_digest,
            signed_root_digest=self._signed_root_digest,
            trust_registry_digest=self._trust_registry_digest,
            authority_digest=self._authority_digest,
            engine=self._engine, plane=self._plane,
            environment=self._environment, scope=self._scope,
            signer_key_ids=self._signer_key_ids,
            verification_reason=self._verification_reason,
            row_count=self._row_count, status_counts=self._status_counts,
            by_param=by_param, by_slot=by_slot, formula_rows=formula_rows,
        )


def build_resolved_bundle(
    registry: BindingRegistry,
    *,
    bundle_id: str,
    bundle_version: str,
    authority_digest: str,
    engine: str,
    plane: str,
    environment: str,
    scope: str,
    trust: dict[str, dict],
    signatures: list[dict],
    trust_registry_digest: str,
    threshold: int = _BUNDLE_THRESHOLD,
    required_roles: tuple[str, ...] = _BUNDLE_REQUIRED_ROLES,
    now_us: int | None = None,
    verify_fn=None,
) -> ResolvedParameterBundle:
    """LEGACY (v1) builder — authenticate a bundle root, then construct the record object.

    Retained ONLY for the C.2 tool's offline selftest (``tools/verify_binding_bundle.py``); the
    v2 production path is :func:`build_sealed_bundle` + :func:`require_bundle`. Fail-closed law
    unchanged: a threshold of externally pinned owner signatures must verify cryptographically
    over the EXACT :func:`canonical_bundle_root` bytes. An absent verifier, below-threshold,
    wrong-role, revoked, out-of-window, or bad signature yields no record
    (:class:`BindingBundleUnauthenticated`).
    """
    governance.assert_hex64(trust_registry_digest, "trust_registry_digest")
    root_bytes = canonical_bundle_root(
        bundle_id=bundle_id, bundle_version=bundle_version,
        source_bundle_digest=registry.source_bundle_digest(),
        authority_digest=authority_digest,
        engine=engine, plane=plane, environment=environment, scope=scope,
        row_count=registry.status_counts_total(),
        status_counts=registry.status_counts(),
    )
    ok, reason = governance.verify_signatures(
        signed_bytes=root_bytes, signatures=signatures, trust=trust,
        required_roles=required_roles, threshold=threshold, now_us=now_us, verify_fn=verify_fn)
    if not ok:
        raise BindingBundleUnauthenticated(reason)

    # Project the verified ACTIVE inventory into the capability's read maps. Formula completeness
    # (BIND-04): a formula is exposed only when its ENTIRE non-superseded registered set is ACTIVE.
    active_rows = registry.active_rows()
    by_param = {row["parameter_id"]: dict(row) for row in active_rows}
    by_slot = {row["semantic_slot"]: dict(row) for row in active_rows}
    formula_rows: dict[str, list[dict]] = {}
    for formula_id in sorted({row["formula_id"] for row in active_rows}):
        if registry.formula_is_complete(formula_id):
            formula_rows[formula_id] = [
                dict(r) for r in sorted(active_rows, key=lambda r: r["binding_id"])
                if r["formula_id"] == formula_id
            ]
    signer_key_ids = tuple(sig.get("key_id") for sig in signatures)
    return ResolvedParameterBundle(
        bundle_id=bundle_id, bundle_version=bundle_version,
        source_bundle_digest=registry.source_bundle_digest(),
        signed_root_digest=sha256_hex(root_bytes),
        trust_registry_digest=trust_registry_digest,
        authority_digest=authority_digest,
        engine=engine, plane=plane, environment=environment, scope=scope,
        signer_key_ids=signer_key_ids, verification_reason=reason,
        row_count=registry.status_counts_total(), status_counts=registry.status_counts(),
        by_param=by_param, by_slot=by_slot, formula_rows=formula_rows,
    )


# =================================================================================================
# C.1 v2 — the SealedParameterBundle shape, the content-law acceptance engine, and the
# VerifiedCapability handle (TRIAD-ORIGIN-V7-FORMULA-REPAIR spec §C.1, milestone B02C).
# =================================================================================================

SEALED_SCHEMA_VERSION = "origin.sealed-parameter-bundle.v2"

# The closed formula universe: ALL 24 IDs F00..F23 must appear in formula_coverage (spec §C.1).
FORMULA_IDS = tuple(f"F{i:02d}" for i in range(24))
COVERAGE_STATUSES = ("ACTIVE", "BLOCKED", "SUPERSEDED", "REFUSED")

# The exact sealed shape — canonical JSON, sorted keys, no floats. Unknown fields are rejected at
# the wire boundary; the acceptance engine reads EXACTLY these fields, once each.
SEALED_FIELDS = (
    "schema_version",
    "scope",
    "rows",
    "canonical_root_digest",
    "trust_registry_digest",
    "signer_set",
    "signatures",
    "valid_from",
    "valid_to",
    "formula_coverage",
    "row_preimage_digests",
)
SCOPE_FIELDS = ("repository", "environment")

_SEALED_ROOT_KIND = "origin.sealed-bundle-root.v2"


@dataclass(frozen=True)
class VerificationContext:
    """The explicit, injected acceptance context for :func:`require_bundle` (spec §C.1).

    * ``trust`` — the parsed trust registry (``key_id -> entry``) derived from
      ``trust_registry_bytes`` by the caller (:func:`governance.validate_trust_registry`).
    * ``trust_registry_bytes`` — the EXACT pinned trust-registry file bytes; their SHA-256 must
      equal BOTH the bundle's ``trust_registry_digest`` AND the process pin (step 2).
    * ``now_us`` — the injected trusted clock (UTC epoch microseconds); never a wall-clock read.
    * ``process_scope`` — the process's bound ``{repository, environment}``.
    * ``verify_fn`` — the INJECTED Ed25519 verifier (crypto never imports into src/triad_origin);
      ``None`` fails closed at the signature step.
    * ``expected_digest_pin`` — optional process-pinned expected SEALED-bundle digest (the
      ``signed_root_digest`` full identity). Memoization is permitted ONLY when this pin is set
      and constant-time-matches the recomputed digest; ``None`` means full verification on every
      call (the fail-closed default).
    """

    trust: dict
    trust_registry_bytes: bytes
    now_us: int
    process_scope: dict
    verify_fn: Any
    expected_digest_pin: str | None = None


@dataclass(frozen=True)
class SealedParameterBundle:
    """The v2 sealed parameter bundle — a plain content record, NOT a security boundary.

    Construction is UNRESTRICTED (spec §C.1: "Construction of the type is unrestricted —
    acceptance is what is guarded"). Nothing about holding an instance grants consumption:
    :func:`require_bundle` re-verifies the full content law on every call, and forging acceptance
    requires forging Ed25519 signatures over the pinned trust registry.
    """

    schema_version: Any
    scope: Any
    rows: Any
    canonical_root_digest: Any
    trust_registry_digest: Any
    signer_set: Any
    signatures: Any
    valid_from: Any
    valid_to: Any
    formula_coverage: Any
    row_preimage_digests: Any

    @classmethod
    def from_dict(cls, doc: object) -> "SealedParameterBundle":
        """Build from a plain mapping, rejecting unknown and missing fields (typed refusals)."""
        if not isinstance(doc, dict):
            raise SealedBundleRejected("SEALED_SHAPE_INVALID:not-an-object")
        unknown = sorted(set(doc) - set(SEALED_FIELDS))
        if unknown:
            raise SealedBundleRejected(f"UNKNOWN_FIELD:{unknown[0]}")
        missing = sorted(set(SEALED_FIELDS) - set(doc))
        if missing:
            raise SealedBundleRejected(f"MISSING_FIELD:{missing[0]}")
        return cls(**{name: doc[name] for name in SEALED_FIELDS})

    @classmethod
    def from_json(cls, text: bytes | str) -> "SealedParameterBundle":
        """Decode a JSON document, rejecting duplicate object keys and every float (fail closed).

        A duplicated key anywhere in the document (e.g. a duplicated scope key) is a typed
        refusal — ``json.loads`` would otherwise silently keep the last duplicate.
        """
        if isinstance(text, (bytes, bytearray)):
            try:
                text = bytes(text).decode("utf-8")
            except UnicodeError as exc:
                raise SealedBundleRejected("SEALED_SHAPE_INVALID:not-utf8") from exc
        if not isinstance(text, str):
            raise SealedBundleRejected("SEALED_SHAPE_INVALID:not-text")

        def _no_duplicates(pairs: list) -> dict:
            out: dict = {}
            for key, value in pairs:
                if key in out:
                    raise SealedBundleRejected(f"DUPLICATE_OBJECT_KEY:{key}")
                out[key] = value
            return out

        def _no_float(token: str) -> Any:
            raise SealedBundleRejected(f"SEALED_SHAPE_INVALID:float:{token}")

        try:
            doc = json.loads(
                text,
                object_pairs_hook=_no_duplicates,
                parse_float=_no_float,
                parse_constant=_no_float,
            )
        except SealedBundleRejected:
            raise
        except (ValueError, RecursionError) as exc:
            raise SealedBundleRejected("SEALED_SHAPE_INVALID:not-json") from exc
        return cls.from_dict(doc)


@dataclass(frozen=True)
class VerifiedCapability:
    """The handle :func:`require_bundle` returns AFTER the full content law passed (step 6).

    * ``source_bundle_digest`` — the recomputed canonical rows digest (a content self-hash;
      partial identity — it may NEVER present as full capability identity).
    * ``signed_root_digest`` — SHA-256 of the actually-signed canonical root bytes (the full,
      signature-bound identity: rows digest + scope + validity).
    """

    parameter_id: str
    formula_id: str
    value: Any
    source_bundle_digest: str
    signed_root_digest: str
    repository: str
    environment: str
    valid_from: int
    valid_to: int
    signer_key_ids: tuple
    _row_canonical: bytes = field(repr=False)

    @property
    def row(self) -> dict:
        """A fresh copy of the verified ACTIVE binding row this capability resolves."""
        return loads_canonical(self._row_canonical)


def canonical_rows_digest(rows: list) -> str:
    """SHA-256 over the canonical JSON of ``rows[]`` with row ORDER canonicalized away.

    Rows are ordered by their canonical byte encoding before the array is encoded, so any
    reordering of the same row set yields the same digest while a one-byte row change yields a
    different one (spec §C.1: "canonicalization must make order irrelevant").
    """
    if not isinstance(rows, (list, tuple)):
        raise SealedBundleRejected("SEALED_SHAPE_INVALID:rows-not-an-array")
    try:
        encoded = sorted(canonical_json(row) for row in rows)
    except CanonicalError as exc:
        raise SealedBundleRejected(f"SEALED_SHAPE_INVALID:rows:{exc}") from exc
    # Each element is already exact canonical JSON, so joining them IS the canonical encoding of
    # the sorted array (canonical_json uses separators("," , ":") with no whitespace).
    return sha256_hex(b"[" + b",".join(encoded) + b"]")


def sealed_bundle_signing_bytes(
    *,
    canonical_root_digest: str,
    scope: dict,
    valid_from: int,
    valid_to: int,
) -> bytes:
    """The exact canonical bytes the signer set signs: canonical root || scope || validity.

    Raw concatenation is forbidden by the canonical law (length/field framing), so the three
    components are bound as one canonical JSON object under a fixed ``root_kind`` domain.
    """
    return canonical_json({
        "root_kind": _SEALED_ROOT_KIND,
        "canonical_root_digest": canonical_root_digest,
        "scope": {
            "repository": scope["repository"],
            "environment": scope["environment"],
        },
        "valid_from": valid_from,
        "valid_to": valid_to,
    })


# --- acceptance memo: ONLY by digest, constant-time, against the process-pinned expected digest --
_MEMO_LOCK = threading.Lock()
_ACCEPTANCE_MEMO: list[str] = []  # full-snapshot digests whose signature set fully verified
_ACCEPTANCE_MEMO_CAP = 8


def _memo_contains(digest_hex: str) -> bool:
    with _MEMO_LOCK:
        entries = list(_ACCEPTANCE_MEMO)
    hit = False
    for entry in entries:  # scan every entry — no early exit
        if ct_hex_equal(entry, digest_hex):
            hit = True
    return hit


def _memo_record(digest_hex: str) -> None:
    with _MEMO_LOCK:
        for entry in _ACCEPTANCE_MEMO:
            if entry == digest_hex:
                return
        if len(_ACCEPTANCE_MEMO) < _ACCEPTANCE_MEMO_CAP:
            _ACCEPTANCE_MEMO.append(digest_hex)


def _reset_acceptance_memo_for_tests() -> None:
    """TEST-ONLY: clear the acceptance memo."""
    with _MEMO_LOCK:
        _ACCEPTANCE_MEMO.clear()


def _sealed_snapshot(bundle: object) -> dict:
    """Read the sealed fields EXACTLY ONCE each and freeze them into plain canonical data.

    Single-read + canonical round-trip kills TOCTOU property games and non-JSON payloads; every
    later step operates on this snapshot only, never on the presented object again.
    """
    try:
        raw = {
            "schema_version": bundle.schema_version,
            "scope": bundle.scope,
            "rows": bundle.rows,
            "canonical_root_digest": bundle.canonical_root_digest,
            "trust_registry_digest": bundle.trust_registry_digest,
            "signer_set": bundle.signer_set,
            "signatures": bundle.signatures,
            "valid_from": bundle.valid_from,
            "valid_to": bundle.valid_to,
            "formula_coverage": bundle.formula_coverage,
            "row_preimage_digests": bundle.row_preimage_digests,
        }
    except AttributeError as exc:
        raise CapabilityForgeryError(
            f"production parameters require a sealed bundle shape; {exc}") from None
    try:
        return loads_canonical(canonical_json(raw))
    except CanonicalError as exc:
        raise SealedBundleRejected(f"SEALED_SHAPE_INVALID:{exc}") from exc


def _check_sealed_shape(snap: dict) -> None:
    """Structural law over the snapshot — every refusal typed, before any crypto."""
    if snap["schema_version"] != SEALED_SCHEMA_VERSION:
        raise SealedBundleRejected(
            f"SEALED_SCHEMA_UNSUPPORTED:{snap['schema_version']!r}")
    scope = snap["scope"]
    if not isinstance(scope, dict) or sorted(scope) != sorted(SCOPE_FIELDS):
        raise SealedBundleRejected("SEALED_SHAPE_INVALID:scope")
    for name in SCOPE_FIELDS:
        if not isinstance(scope[name], str) or not scope[name]:
            raise SealedBundleRejected(f"SEALED_SHAPE_INVALID:scope.{name}")
    rows = snap["rows"]
    if not isinstance(rows, list):
        raise SealedBundleRejected("SEALED_SHAPE_INVALID:rows-not-an-array")
    if len(rows) != REQUIRED_ROW_COUNT:
        raise SealedBundleRejected(f"ROW_COUNT_INVALID:{len(rows)}")
    seen_ids: set = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SealedBundleRejected("SEALED_SHAPE_INVALID:row-not-an-object")
        binding_id = row.get("binding_id")
        if not isinstance(binding_id, str) or not binding_id:
            raise SealedBundleRejected("SEALED_SHAPE_INVALID:row.binding_id")
        if binding_id in seen_ids:
            raise SealedBundleRejected(f"DUPLICATE_BINDING_ID:{binding_id}")
        seen_ids.add(binding_id)
        for name in ("status", "formula_id", "parameter_id", "semantic_slot"):
            if not isinstance(row.get(name), str) or not row.get(name):
                raise SealedBundleRejected(f"SEALED_SHAPE_INVALID:row.{name}:{binding_id}")
        unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
        if not ct_hex_equal(row.get("binding_digest"), sha256_hex(canonical_json(unsigned))):
            raise SealedBundleRejected(f"BINDING_DIGEST_MISMATCH:{binding_id}")
    if not is_sha256_hex(snap["canonical_root_digest"]):
        raise SealedBundleRejected("SEALED_SHAPE_INVALID:canonical_root_digest")
    if not is_sha256_hex(snap["trust_registry_digest"]):
        raise SealedBundleRejected("SEALED_SHAPE_INVALID:trust_registry_digest")
    signer_set = snap["signer_set"]
    if (not isinstance(signer_set, list)
            or any(not isinstance(k, str) or not k for k in signer_set)
            or len(set(signer_set)) != len(signer_set)):
        raise SealedBundleRejected("SEALED_SHAPE_INVALID:signer_set")
    if not isinstance(snap["signatures"], list):
        raise SealedBundleRejected("SEALED_SHAPE_INVALID:signatures")
    for name in ("valid_from", "valid_to"):
        value = snap[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SealedBundleRejected(f"VALIDITY_WINDOW_INVALID:{name}")
    if snap["valid_from"] > snap["valid_to"]:
        raise SealedBundleRejected("VALIDITY_WINDOW_INVALID:valid_from>valid_to")
    coverage = snap["formula_coverage"]
    if not isinstance(coverage, dict):
        raise SealedBundleRejected("COVERAGE_INVALID:not-an-object")
    if sorted(coverage) != sorted(FORMULA_IDS):
        raise SealedBundleRejected("COVERAGE_INVALID:formula-id-set")
    for fid in FORMULA_IDS:
        if coverage[fid] not in COVERAGE_STATUSES:
            raise SealedBundleRejected(f"COVERAGE_INVALID:{fid}:{coverage[fid]!r}")
    preimages = snap["row_preimage_digests"]
    if not isinstance(preimages, list) or any(not is_sha256_hex(p) for p in preimages):
        raise SealedBundleRejected("SEALED_SHAPE_INVALID:row_preimage_digests")
    computed = sorted(sha256_hex(canonical_json(row)) for row in rows)
    if sorted(preimages) != computed:
        raise SealedBundleRejected("ROW_PREIMAGE_MISMATCH")


def _check_context(ctx: object) -> None:
    """The acceptance context must be an explicit, well-formed VerificationContext."""
    if not isinstance(ctx, VerificationContext):
        raise SealedBundleRejected("VERIFICATION_CONTEXT_INVALID:not-a-VerificationContext")
    if not isinstance(ctx.trust, dict):
        raise SealedBundleRejected("VERIFICATION_CONTEXT_INVALID:trust")
    if not isinstance(ctx.trust_registry_bytes, (bytes, bytearray)):
        raise SealedBundleRejected("VERIFICATION_CONTEXT_INVALID:trust_registry_bytes")
    if (not isinstance(ctx.now_us, int) or isinstance(ctx.now_us, bool) or ctx.now_us <= 0):
        raise SealedBundleRejected("VERIFICATION_CONTEXT_INVALID:now_us")
    scope = ctx.process_scope
    if (not isinstance(scope, dict) or sorted(scope) != sorted(SCOPE_FIELDS)
            or any(not isinstance(scope[k], str) or not scope[k] for k in SCOPE_FIELDS)):
        raise SealedBundleRejected("VERIFICATION_CONTEXT_INVALID:process_scope")
    pin = ctx.expected_digest_pin
    if pin is not None and not is_sha256_hex(pin):
        raise SealedBundleRejected("VERIFICATION_CONTEXT_INVALID:expected_digest_pin")


def accept_sealed_bundle(
    bundle: object,
    parameter_id: str,
    *,
    formula_id: str,
    ctx: VerificationContext,
) -> VerifiedCapability:
    """The §C.1 six-step content-law acceptance — run in full on EVERY call.

    1. Recompute ``canonical_root_digest`` from the rows; constant-time compare to the carried
       digest (row-preimage digests re-verified alongside).
    2. Hash the supplied trust-registry bytes; the hash must constant-time-equal BOTH the
       bundle's ``trust_registry_digest`` AND the process-pinned expected trust digest.
    3. Verify every signature via the injected Ed25519 seam (role, revocation, threshold —
       :func:`governance.verify_signatures`); memoizable ONLY by digest with a constant-time
       compare against ``ctx.expected_digest_pin`` (the structural signer pass still runs).
    4. ``valid_from <= now_us <= valid_to``; the bundle scope must equal the process's bound
       ``{repository, environment}`` exactly.
    5. The REQUESTING formula's set must be complete-and-ACTIVE (coverage AND rows), else the
       typed refusal ``BLOCKED_BINDING_INCOMPLETE{formula_id}``.
    6. Only then return a :class:`VerifiedCapability` handle carrying the digests.
    """
    _check_context(ctx)
    snap = _sealed_snapshot(bundle)
    _check_sealed_shape(snap)

    # Step 1 — content identity: the rows are the truth; the carried digest must match them.
    recomputed_root = canonical_rows_digest(snap["rows"])
    if not ct_hex_equal(recomputed_root, snap["canonical_root_digest"]):
        raise SealedBundleRejected("ROOT_DIGEST_MISMATCH")
    signing_bytes = sealed_bundle_signing_bytes(
        canonical_root_digest=recomputed_root, scope=snap["scope"],
        valid_from=snap["valid_from"], valid_to=snap["valid_to"])
    signed_root_digest = sha256_hex(signing_bytes)

    # Step 2 — the pinned trust registry: supplied bytes hash equals the bundle digest AND the
    # process pin (set-once at startup, cross-checked against the repository trust file).
    trust_bytes_digest = sha256_hex(bytes(ctx.trust_registry_bytes))
    process_pin = pinned_trust_registry_digest()
    if process_pin is None:
        raise SealedBundleRejected("TRUST_REGISTRY_UNPINNED")
    if not ct_hex_equal(trust_bytes_digest, snap["trust_registry_digest"]):
        raise SealedBundleRejected("TRUST_REGISTRY_DIGEST_MISMATCH")
    if not ct_hex_equal(trust_bytes_digest, process_pin):
        raise SealedBundleRejected("TRUST_REGISTRY_PIN_MISMATCH")

    # Step 3 — signatures. Every declared signature's key must be in the declared signer set.
    for sig in snap["signatures"]:
        if not isinstance(sig, dict):
            raise SealedBundleRejected("SEALED_SHAPE_INVALID:signature-record")
        if sig.get("key_id") not in snap["signer_set"]:
            raise SealedBundleRejected(f"SIGNER_NOT_IN_SET:{sig.get('key_id')}")
    memo_digest = sha256_hex(canonical_json(snap))
    memo_hit = (
        ctx.expected_digest_pin is not None
        and ct_hex_equal(signed_root_digest, ctx.expected_digest_pin)
        and _memo_contains(memo_digest)
    )
    if memo_hit:
        # Crypto already proven for these EXACT bytes; the structural signer pass (role,
        # revocation, window, threshold vs the CURRENT now_us) still runs on every call.
        ok, reason = governance.verify_signatures(
            signed_bytes=signing_bytes, signatures=snap["signatures"], trust=ctx.trust,
            required_roles=_BUNDLE_REQUIRED_ROLES, threshold=_BUNDLE_THRESHOLD,
            now_us=ctx.now_us, verify_fn=None)
        if ok or reason != "VERIFY_UNAVAILABLE":
            raise SealedBundleRejected(f"SIGNATURE_INVALID:{reason}")
    else:
        ok, reason = governance.verify_signatures(
            signed_bytes=signing_bytes, signatures=snap["signatures"], trust=ctx.trust,
            required_roles=_BUNDLE_REQUIRED_ROLES, threshold=_BUNDLE_THRESHOLD,
            now_us=ctx.now_us, verify_fn=ctx.verify_fn)
        if not ok:
            raise SealedBundleRejected(f"SIGNATURE_INVALID:{reason}")
        if (ctx.expected_digest_pin is not None
                and ct_hex_equal(signed_root_digest, ctx.expected_digest_pin)):
            _memo_record(memo_digest)

    # Step 4 — validity window against the injected trusted clock; exact scope binding.
    if ctx.now_us < snap["valid_from"]:
        raise SealedBundleRejected("NOT_YET_VALID")
    if ctx.now_us > snap["valid_to"]:
        raise SealedBundleRejected("EXPIRED")
    if (snap["scope"]["repository"] != ctx.process_scope["repository"]
            or snap["scope"]["environment"] != ctx.process_scope["environment"]):
        raise SealedBundleRejected("SCOPE_MISMATCH")

    # Step 5 — the REQUESTING formula's set must be complete-and-ACTIVE.
    if formula_id not in FORMULA_IDS:
        raise SealedBundleRejected(f"UNKNOWN_FORMULA:{formula_id!r}")
    if snap["formula_coverage"][formula_id] != "ACTIVE":
        raise BlockedBindingIncomplete(formula_id)
    live = [row for row in snap["rows"]
            if row["formula_id"] == formula_id and not row.get("superseded_by")]
    if not live or any(row["status"] != "ACTIVE" for row in live):
        raise BlockedBindingIncomplete(formula_id)
    for row in live:
        for name in _ACTIVE_RESOLVED_FIELDS:
            if _is_sentinel(row.get(name)):
                raise BlockedBindingIncomplete(formula_id)

    # Step 6 — resolve the parameter WITHIN the requesting formula's verified ACTIVE set.
    matches = [row for row in live if row["parameter_id"] == parameter_id]
    if not matches:
        raise BindingUnknownError(
            f"no ACTIVE binding declares parameter {parameter_id!r} for formula "
            f"{formula_id!r} in this sealed bundle")
    if len(matches) > 1:
        raise SealedBundleRejected(f"AMBIGUOUS_PARAMETER:{parameter_id}")
    row = matches[0]
    return VerifiedCapability(
        parameter_id=parameter_id,
        formula_id=formula_id,
        value=row["declared_value"],
        source_bundle_digest=recomputed_root,
        signed_root_digest=signed_root_digest,
        repository=snap["scope"]["repository"],
        environment=snap["scope"]["environment"],
        valid_from=snap["valid_from"],
        valid_to=snap["valid_to"],
        signer_key_ids=tuple(
            sig.get("key_id") for sig in snap["signatures"] if isinstance(sig, dict)),
        _row_canonical=canonical_json(row),
    )


def derive_formula_coverage(registry: BindingRegistry) -> dict:
    """Derive the closed 24-ID coverage map from a loaded registry (fail-closed rules).

    ACTIVE     — live (non-superseded) rows exist and every one is ACTIVE.
    SUPERSEDED — rows exist for the formula but every one is superseded.
    REFUSED    — the registry carries no row at all for the formula.
    BLOCKED    — everything else (any live non-ACTIVE row).
    """
    rows = registry.rows()
    coverage: dict = {}
    for fid in FORMULA_IDS:
        formula_rows = [row for row in rows if row["formula_id"] == fid]
        if not formula_rows:
            coverage[fid] = "REFUSED"
            continue
        live = [row for row in formula_rows if not row.get("superseded_by")]
        if not live:
            coverage[fid] = "SUPERSEDED"
        elif all(row["status"] == "ACTIVE" for row in live):
            coverage[fid] = "ACTIVE"
        else:
            coverage[fid] = "BLOCKED"
    return coverage


def build_sealed_bundle(
    registry: BindingRegistry,
    *,
    repository: str,
    environment: str,
    valid_from: int,
    valid_to: int,
    trust_registry_digest: str,
    signer_set: tuple | list | None = None,
    signatures: list | None = None,
) -> SealedParameterBundle:
    """Assemble a v2 sealed bundle over a loaded registry so fixtures can construct + sign.

    This BUILDS; it does not accept. The digests are computed from the registry's complete row
    set; ``signatures`` (Ed25519 over :func:`sealed_bundle_signing_bytes`) are supplied by the
    caller — an unsigned bundle is constructible and simply never reaches acceptance.
    """
    rows = registry.rows()
    root = canonical_rows_digest(rows)
    sigs = list(signatures) if signatures is not None else []
    if signer_set is None:
        declared: list = []
        for sig in sigs:
            kid = sig.get("key_id") if isinstance(sig, dict) else None
            if isinstance(kid, str) and kid not in declared:
                declared.append(kid)
        signer_set = declared
    return SealedParameterBundle(
        schema_version=SEALED_SCHEMA_VERSION,
        scope={"repository": repository, "environment": environment},
        rows=rows,
        canonical_root_digest=root,
        trust_registry_digest=trust_registry_digest,
        signer_set=list(signer_set),
        signatures=sigs,
        valid_from=valid_from,
        valid_to=valid_to,
        formula_coverage=derive_formula_coverage(registry),
        row_preimage_digests=sorted(sha256_hex(canonical_json(row)) for row in rows),
    )

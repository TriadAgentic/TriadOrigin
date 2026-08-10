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
from dataclasses import dataclass, field
from typing import Any

from . import contracts
from . import governance
from .canonical import canonical_json, sha256_hex

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_REGISTRY_PATH = _ROOT / "docs" / "control" / "binding_registry.v2.json"

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
# B01C-BIND-01 / BIND-05 — the authenticated, sealed, immutable parameter capability.
#
# A recomputable per-row hash is integrity, not authenticated identity. Before any production
# transition may consume a parameter, an externally pinned owner signature must verify over the
# EXACT bundle root, and the result must be an unforgeable, immutable capability that no raw
# dictionary, copied dataclass, subclass, or reloaded marker can impersonate.
# =================================================================================================

# A module-private sentinel no external caller can name. The capability constructor refuses unless
# it is handed this exact object, so ``ResolvedParameterBundle(...)`` from outside always fails.
_CONSTRUCTION_TOKEN = object()

# The bundle-root signature is owner-anchored: a single AUTHORITY_OWNER signature over the exact
# canonical bundle root is the minimum, and it must verify cryptographically (absent verifier =>
# fail closed, never a silent pass).
_BUNDLE_REQUIRED_ROLES = ("AUTHORITY_OWNER",)
_BUNDLE_THRESHOLD = 1


class BindingBundleUnauthenticated(RuntimeError):
    """The bundle root carried no verifiable owner signature — no capability is constructed."""

    def __init__(self, reason: str):
        super().__init__(f"BINDING_BUNDLE_UNAUTHENTICATED: {reason}")
        self.reason = reason


class CapabilityForgeryError(TypeError):
    """A non-capability object was presented where a sealed capability is required."""


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
    """The sealed, unforgeable, immutable parameter capability (B01C-BIND-05, plan §4.3).

    Only :func:`build_resolved_bundle` may construct one (a module-private construction token
    gates ``__init__``). It is immutable (``__slots__`` + a blocking ``__setattr__``), it may be
    NARROWED but never widened, and it carries an internal verification marker that ordinary
    callers cannot forge. :func:`triad_origin.transition.require_bundle` accepts ONLY an exact
    instance of this type — a dict, a copied dataclass, a subclass, or a reloaded marker refuses.
    """

    __slots__ = (
        "_bundle_id", "_bundle_version", "_bundle_root_digest", "_trust_registry_digest",
        "_authority_digest", "_engine", "_plane", "_environment", "_scope",
        "_signer_key_ids", "_verification_reason", "_row_count", "_status_counts",
        "_by_param", "_by_slot", "_formula_rows",
    )

    def __init__(self, token: object, **fields: Any):
        if token is not _CONSTRUCTION_TOKEN:
            raise CapabilityForgeryError(
                "ResolvedParameterBundle is sealed; construct it via build_resolved_bundle")
        object.__setattr__(self, "_bundle_id", fields["bundle_id"])
        object.__setattr__(self, "_bundle_version", fields["bundle_version"])
        object.__setattr__(self, "_bundle_root_digest", fields["bundle_root_digest"])
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
    def bundle_root_digest(self) -> str:
        return self._bundle_root_digest

    def verification(self) -> dict:
        """The immutable verification marker — signer ids, trust digest, and the OK reason.

        A copy of record; there is no setter and no way to fabricate the ``OK`` reason without a
        real threshold verification inside :func:`build_resolved_bundle`.
        """
        return {
            "bundle_id": self._bundle_id,
            "bundle_version": self._bundle_version,
            "bundle_root_digest": self._bundle_root_digest,
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
            _CONSTRUCTION_TOKEN,
            bundle_id=self._bundle_id,
            bundle_version=self._bundle_version,
            bundle_root_digest=self._bundle_root_digest,
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
    """Authenticate a binding bundle root and construct the sealed capability (BIND-01/BIND-05).

    Fail-closed law: a threshold of externally pinned owner signatures must verify
    cryptographically over the EXACT :func:`canonical_bundle_root` bytes. An absent verifier,
    below-threshold, wrong-role, revoked, out-of-window, or bad signature yields no capability
    (:class:`BindingBundleUnauthenticated`). The registry has already proven its 105-row
    inventory and per-row digests at load; this step adds authenticated bundle identity on top.
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
        _CONSTRUCTION_TOKEN,
        bundle_id=bundle_id, bundle_version=bundle_version,
        bundle_root_digest=registry.source_bundle_digest(),
        trust_registry_digest=trust_registry_digest,
        authority_digest=authority_digest,
        engine=engine, plane=plane, environment=environment, scope=scope,
        signer_key_ids=signer_key_ids, verification_reason=reason,
        row_count=registry.status_counts_total(), status_counts=registry.status_counts(),
        by_param=by_param, by_slot=by_slot, formula_rows=formula_rows,
    )

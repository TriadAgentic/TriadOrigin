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

from . import contracts
from .canonical import canonical_json, sha256_hex

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_REGISTRY_PATH = _ROOT / "docs" / "control" / "binding_registry.v2.json"

REGISTRY_VERSION = "origin.binding-registry.v2"


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
        by_id: dict[str, dict] = {}
        by_slot_active: dict[str, dict] = {}
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
        declared = registry.get("status_counts")
        if declared != dict(sorted(counts.items())):
            raise BindingRegistryError(
                f"registry status_counts {declared} disagree with rows {counts}")
        self._by_id = by_id
        self._by_slot_active = by_slot_active
        self._counts = counts

    # -- read faces ---------------------------------------------------------------------------

    def status_counts(self) -> dict:
        return dict(sorted(self._counts.items()))

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

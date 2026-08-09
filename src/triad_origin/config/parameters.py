"""Signed parameter configuration (B07 — the 192-row RC3 parameter materialization gate).

Loads the RC3 effective-control-bundle ``parameters`` table
(``docs/control/rc3_effective_control_bundle.json``) into a frozen, digest-identified registry and
enforces ONE consumption law at :meth:`ParameterRegistry.require`:

  * every row's ``status`` is checked against a closed **allowlist**
    (:data:`MATERIALIZABLE_STATUSES`) — an unrecognized status (neither materializable nor
    refused) is a load-time defect, never a silent admit. A denylist would silently admit a
    future/unrecognized status; this repository's determinism law forbids exactly that silent
    fallback (``CLAUDE.md``: "no ... silent fallback is permitted");
  * ``PROPOSED_RC2_MUST_RATIFY`` (not yet ratified), ``BLOCKING_OWNER_DECISION`` and
    ``BLOCKING_RESEARCH_DECISION`` (each row's own ``declared_value`` is literally the
    :data:`triad_origin.structures.common.NOT_RATIFIED` sentinel), ``SUPERSEDED`` (a newer
    authoritative row exists — reading the superseded value would materialize stale governance
    truth) and ``TARGET_NOT_PROVISIONED`` (the infrastructure target this row would bind to does
    not exist) all refuse — :class:`ParameterRefusedError` names the exact source status and the
    control bundle's own ``failure_behavior`` text, never a fabricated value and never a silent
    downgrade;
  * a caller-pinned ``expected_digest`` that disagrees with the loaded bundle's
    :attr:`ParameterRegistry.parameter_digest` refuses as stale (:class:`ParameterDigestMismatchError`)
    — mirrors the digest-bound consumption law already used by
    :mod:`triad_origin.control.lever_registry` (LEV-0043/LEV-0050);
  * a caller-declared ``scope`` the row's own ``scope`` text does not cover refuses
    (:class:`ParameterScopeMismatchError`) rather than being silently narrowed or widened.

This is a **separate, stricter, activation-facing** gate from the code-level ``DECLARED_*`` rule
strings in :mod:`triad_origin.structures.common` that B03–B06 already consume directly as
executable constants (writing offline code against a declared-rule string is always permitted —
``AUTHORIZED_OFFLINE_IMPLEMENTATION_ONLY``). It does not retroactively tighten any already-shipped
B03–B06 code; it is a new law for anything that reads this table as *live configuration* going
forward (comparator axes, transport bindings, treatment/rollback, the exact four-plane manifest,
and every other B07-owned signed-config domain).

Deterministic and read-only: no clock, no network, no mutation of the registry once loaded.
"""

from __future__ import annotations

import json
import pathlib

from ..canonical import canonical_json, sha256_hex
from ..structures import common

_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_BUNDLE_PATH = _ROOT / "docs" / "control" / "rc3_effective_control_bundle.json"

# The exact row shape every parameter row must carry (docs/control/rc3_effective_control_bundle.json
# "parameters"). A row missing any of these is a load-time defect.
REQUIRED_ROW_FIELDS = (
    "accountable_owner", "boundary_rule", "category", "declared_value", "exact_rule",
    "failure_behavior", "formula_refs", "gate", "id", "name", "phase", "review_trigger",
    "scope", "source_basis", "status", "symbol", "unit", "value_type",
)

# Fail-closed ALLOWLIST: only these statuses may ever materialize as a current, active
# configuration value. Verified (2026-08-09) against every non-common status's own
# ``declared_value``/``failure_behavior`` text in the 192-row bundle — each row below carries a
# real, current, ratified-or-equivalent value with no unresolved blocking decision:
#   RATIFIED_RC1 (21), DECLARED_RC2 (8) — e.g. rounding/overflow/threshold-equality policy;
#   TARGET_FROM_TOPOLOGY (8) — SLO targets (latency/coverage/availability ceilings), not
#     unresolved decisions; CURRENT_VENDOR_REQUIRED (4) — vendor-mandated exact values (Binance
#     WS paths, sequence-gap tolerance); DECLARED_RC3 (3) — incl. the ENGINE_COHORT_ENUM /
#     INTELLIGENCE_ARM_ENUM comparator axes; VENUE_DERIVED (2) and FORMULA_DERIVED (1) — the
#     config materializes the DERIVATION RULE, never a live venue read; RATIFIED_RC3_OVERRIDE (1),
#     RATIFIED_MAKER_LAW (1), DECLARED_RC3_FROM_UNION (1), VERIFIED_AS_BUILT_2026_08_07 (1).
# 51 rows total. See docs/plan/09_OPEN_QUESTIONS.md row E25 for the full disposition record.
MATERIALIZABLE_STATUSES = frozenset({
    "RATIFIED_RC1",
    "DECLARED_RC2",
    "DECLARED_RC3",
    "DECLARED_RC3_FROM_UNION",
    "RATIFIED_RC3_OVERRIDE",
    "RATIFIED_MAKER_LAW",
    "TARGET_FROM_TOPOLOGY",
    "CURRENT_VENDOR_REQUIRED",
    "VENUE_DERIVED",
    "FORMULA_DERIVED",
    "VERIFIED_AS_BUILT_2026_08_07",
})

# Every row whose status is here stays fail-closed SAFE_HOLD data — ``row()`` returns it verbatim
# (a read of record, never a consumption) but ``require()`` always refuses it. 141 rows total.
REFUSED_STATUSES = frozenset({
    "PROPOSED_RC2_MUST_RATIFY",     # not yet ratified — an offline draft, never an active value
    "BLOCKING_OWNER_DECISION",      # declared_value == NOT_RATIFIED; G7/G9 cannot pass on it
    "BLOCKING_RESEARCH_DECISION",   # declared_value == NOT_RATIFIED; the dependent formula stays
                                     # UNAVAILABLE
    "SUPERSEDED",                   # a newer authoritative row exists; this one is stale by law
    "TARGET_NOT_PROVISIONED",       # the infrastructure target does not exist to bind to
})


class ParameterRegistryError(RuntimeError):
    """The control-bundle parameters table itself is invalid — fail closed before consumption."""


class ParameterUnknownError(KeyError):
    """No parameter row exists for the requested id. Never a default."""


class ParameterRefusedError(RuntimeError):
    """A parameter row exists but its governance status is not materializable. Never consumed."""

    def __init__(self, parameter_id: str, status: str, failure_behavior: str):
        super().__init__(
            f"PARAMETER_NOT_MATERIALIZED: {parameter_id} status={status} — {failure_behavior}")
        self.parameter_id = parameter_id
        self.status = status
        self.failure_behavior = failure_behavior


class ParameterDigestMismatchError(RuntimeError):
    """A caller's pinned ``parameter_digest`` disagrees with the currently loaded bundle (stale)."""


class ParameterScopeMismatchError(RuntimeError):
    """A caller-declared scope is not covered by the row's own declared scope text."""


class ParameterRegistry:
    """A frozen, digest-identified view of the 192-row RC3 parameter table."""

    def __init__(self, rows: list):
        if not isinstance(rows, list) or not rows:
            raise ParameterRegistryError("parameter table has no rows")
        by_id: dict[str, dict] = {}
        counts: dict[str, int] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ParameterRegistryError("parameter row is not an object")
            missing = sorted(f for f in REQUIRED_ROW_FIELDS if f not in row)
            if missing:
                raise ParameterRegistryError(
                    f"parameter row {row.get('id')!r} missing fields: {missing}")
            param_id = row["id"]
            if not isinstance(param_id, str) or not param_id:
                raise ParameterRegistryError("parameter row id must be a non-empty string")
            if param_id in by_id:
                raise ParameterRegistryError(f"duplicate parameter id {param_id!r}")
            status = row["status"]
            if status not in MATERIALIZABLE_STATUSES and status not in REFUSED_STATUSES:
                raise ParameterRegistryError(
                    f"unrecognized parameter status {status!r} for {param_id!r}: neither "
                    f"materializable nor refused — a load-time defect, never a silent admit")
            # Defense in depth: NOT_RATIFIED must never appear on a materializable row — that
            # would be a bundle inconsistency (a status claiming ratified truth while its own
            # declared_value says otherwise), and is never silently downgraded to refused.
            if status in MATERIALIZABLE_STATUSES and row["declared_value"] == common.NOT_RATIFIED:
                raise ParameterRegistryError(
                    f"parameter {param_id!r} declares status {status!r} (materializable) but "
                    f"declared_value is {common.NOT_RATIFIED!r}")
            by_id[param_id] = dict(row)
            counts[status] = counts.get(status, 0) + 1
        self._by_id = by_id
        self._counts = counts
        ordered_rows = [dict(by_id[pid]) for pid in sorted(by_id)]
        self._digest = sha256_hex(canonical_json({"rows": ordered_rows}))

    # -- identity ---------------------------------------------------------------------------------

    @property
    def parameter_digest(self) -> str:
        """SHA-256 over every row (materializable and refused alike), sorted by id.

        The source-status identity of this exact parameter bundle — a caller pins this value
        (``require(..., expected_digest=...)``) to refuse a silently swapped-in different bundle.
        """
        return self._digest

    def status_counts(self) -> dict:
        """Row count per governance status — a read of record over the whole table."""
        return dict(sorted(self._counts.items()))

    def row(self, parameter_id: str) -> dict:
        """The verbatim row (any status) — a read of record, never a consumption."""
        try:
            return dict(self._by_id[parameter_id])
        except KeyError:
            raise ParameterUnknownError(f"unknown parameter id {parameter_id!r}") from None

    def materialized_ids(self) -> tuple:
        """Every parameter id whose status is currently materializable, sorted."""
        return tuple(sorted(pid for pid, row in self._by_id.items()
                             if row["status"] in MATERIALIZABLE_STATUSES))

    def refused_ids(self) -> tuple:
        """Every parameter id currently held SAFE_HOLD, sorted."""
        return tuple(sorted(pid for pid, row in self._by_id.items()
                             if row["status"] in REFUSED_STATUSES))

    # -- consumption law ----------------------------------------------------------------------------

    def require(self, parameter_id: str, *, expected_digest: str | None = None,
                scope: str | None = None) -> dict:
        """The single ORIGIN entry point for reading an active configuration value.

        Refuses — never defaults, never substitutes — on:
          * an unknown id (:class:`ParameterUnknownError`);
          * a caller-pinned ``expected_digest`` that disagrees with the loaded bundle
            (:class:`ParameterDigestMismatchError` — a stale attestation), checked before the
            status law so a stale caller never even learns whether the row it asked for would
            have materialized;
          * a status outside :data:`MATERIALIZABLE_STATUSES` (:class:`ParameterRefusedError`,
            naming the source status and the control bundle's own ``failure_behavior`` text);
          * a caller-declared ``scope`` the row's own ``scope`` text does not cover
            (:class:`ParameterScopeMismatchError`).
        """
        row = self.row(parameter_id)  # raises ParameterUnknownError
        if expected_digest is not None and expected_digest != self._digest:
            raise ParameterDigestMismatchError(
                f"parameter_digest mismatch for {parameter_id!r}: "
                f"expected {expected_digest!r}, loaded {self._digest!r}")
        if row["status"] not in MATERIALIZABLE_STATUSES:
            raise ParameterRefusedError(parameter_id, row["status"], row["failure_behavior"])
        if scope is not None:
            declared_scope = row["scope"]
            if (not isinstance(declared_scope, str) or not declared_scope
                    or scope.strip().lower() not in declared_scope.strip().lower()):
                raise ParameterScopeMismatchError(
                    f"scope {scope!r} is not covered by {parameter_id!r}'s declared scope: "
                    f"{declared_scope!r}")
        return row


def load_registry(path: str | pathlib.Path = DEFAULT_BUNDLE_PATH) -> ParameterRegistry:
    """Load and validate the 192-row parameter table. Fails closed on any structural defect."""
    try:
        bundle = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ParameterRegistryError(f"control bundle unreadable: {exc}") from exc
    rows = bundle.get("parameters") if isinstance(bundle, dict) else None
    if not isinstance(rows, list):
        raise ParameterRegistryError("control bundle has no 'parameters' array")
    return ParameterRegistry(rows)

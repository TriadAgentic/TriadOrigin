"""Shared read-face evidence envelope (B08 — RC3 W25 ``evidence_view.v2``; RC4 §L6 read-face laws).

The ONE shape every B08 read face (``get_engine_lever_registry``, ``get_engine_lever_attestation``,
``get_engine_lever_history``, ``get_shadow_health``, ``get_four_plane_status``,
``get_engine_inventory_reconciliation``) returns. It is a pure projection WRAPPER — it holds no data
of its own beyond what a face projects into it, and it enforces the cross-face honesty laws so no
face can accidentally break them.

**Not a vendored contract** (documented reading judgment — ``docs/plan/09_OPEN_QUESTIONS.md`` row
E37): RC3 wiring W25's ``contract: "evidence_view.v2"`` is a *logical binding* ("MCP read faces /
approved databases"), not a ``contracts/`` JSON schema — no ``triad.evidence_view`` schema is
vendored anywhere, and the RC4 addendum's ``contracts`` array names only the per-face BACKING
contracts (``runtime_lever_registry.v1``, ``runtime_lever_attestation.v1``, ``shadow_health.v1`` —
all already vendored). The read-face envelope is therefore an INTERNAL projection shape; this
module's :func:`validate` IS its contract, versioned by :data:`EVIDENCE_VIEW_VERSION`. Adding a
vendored ``contracts/`` schema would re-pin the estate manifest for a seam that never crosses the
wire — reported upstream as a request, not taken here.

**THE W25 FAILURE LAW** (``docs/control/rc3_effective_control_bundle.json`` W25 ``failure_behavior``,
verbatim): "Unavailable dependency returns unavailable; no empty green and no control side effect."
and (``ordering_idempotency``, verbatim) "Projection rebuilds from ledgers; response names plane,
source, freshness and completeness." Every envelope therefore NAMES its :attr:`source`, its freshness
(:attr:`as_of_us` snapshot instant + honest-null :attr:`watermark_us` source watermark — carried
SEPARATELY, never conflated into one liveness claim, RC4 ``LEV-V-0124`` "Return both timestamps and
mismatch; no single green liveness claim"), its :attr:`completeness`, and its :attr:`plane`.

**THE HONEST STATUS VOCABULARY** (:data:`STATUSES`): ``AVAILABLE`` (source present and the fact was
computed — the value may be a measured zero, which is honest, distinct from a fabricated one),
``UNAVAILABLE`` (source absent or unreachable — RC4 ``LEV-V-0122`` "Return unavailable proof; do not
infer TESTNET OFF or LIVE"), and ``NOT_MEASURABLE`` (source present but the specific fact cannot be
computed — RC3 ``RC3-AC-WIRE-W08A-05`` / ``WIRE-W20-05`` "Missing lineage produces NOT_MEASURABLE,
never estimated win/loss"). ``UNAVAILABLE`` and ``NOT_MEASURABLE`` are deliberately distinct — the
first says the dependency is gone, the second says it is present but silent on this fact. A
non-``AVAILABLE`` envelope carries **no** :attr:`value` (never a fabricated zero / empty green) and
MUST name a :attr:`reason`.

**BOUNDED / SNAPSHOT** (RC4 ``LEV-0122`` "Make every read bounded, paginated, and
snapshot-timestamped; named unavailable is preferable to timeout or empty arrays"): an ``AVAILABLE``
envelope carries :attr:`returned`, the applied :attr:`limit`, and — when more rows remain — a
:attr:`cursor`, with :attr:`truncated`/:attr:`completeness` DERIVED from whether a cursor exists (one
source of truth, so a face cannot claim COMPLETE while handing back a next page). This module owns no
page-size number: PAR-132..138 are ``PROPOSED_RC2_MUST_RATIFY`` fail-closed parameters, so the bound
is a caller-supplied fact the envelope only records, never a default it invents.

**READ OF RECORD, NEVER A CONSUMPTION**: :meth:`ReadFaceEnvelope.to_dict` and :func:`from_dict`
detach through :func:`copy.deepcopy`, so a caller mutation of a returned view can never corrupt an
envelope's projected value.

Pure and side-effect-free: no clock, no network, no I/O, no randomness, no float, no control verb,
no credential. Every 'current' fact (``as_of_us``, ``watermark_us``, the projected value) is
caller-supplied; the envelope arms, activates, and switches nothing — it only projects.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

# The internal contract version. NOT a vendored ``contracts/`` schema id (see the module docstring):
# W25's ``evidence_view.v2`` is a logical binding, so this names the in-repo projection shape whose
# authority is :func:`validate`, versioned for the same reason every ORIGIN identity is (a byte
# change to the shape is a new version, never a silent in-place edit).
EVIDENCE_VIEW_VERSION = "origin.evidence_view.v2"

# ---------------------------------------------------------------------------------------------
# The closed vocabularies
# ---------------------------------------------------------------------------------------------
STATUS_AVAILABLE = "AVAILABLE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_NOT_MEASURABLE = "NOT_MEASURABLE"
STATUSES = (STATUS_AVAILABLE, STATUS_UNAVAILABLE, STATUS_NOT_MEASURABLE)

COMPLETENESS_COMPLETE = "COMPLETE"
COMPLETENESS_TRUNCATED = "TRUNCATED"
COMPLETENESS_NOT_APPLICABLE = "NOT_APPLICABLE"
COMPLETENESS_VOCAB = (
    COMPLETENESS_COMPLETE,
    COMPLETENESS_TRUNCATED,
    COMPLETENESS_NOT_APPLICABLE,
)

# The four market populations, in the RC4 ``four_plane_law`` order, plus the non-market control
# plane token (the lever/registry/attestation/reconciliation faces are not scoped to a market
# population). ``None`` names a face that is not plane-scoped at all.
PLANE_SHADOW = "SHADOW"
PLANE_PAPER = "PAPER"
PLANE_TESTNET = "TESTNET"
PLANE_LIVE = "LIVE"
PLANES = (PLANE_SHADOW, PLANE_PAPER, PLANE_TESTNET, PLANE_LIVE)
CONTROL_PLANE = "CONTROL"
PLANES_ALL = PLANES + (CONTROL_PLANE,)

# The canonical, exact key set of a serialized envelope (additionalProperties:false discipline).
_CANONICAL_KEYS = frozenset(
    {
        "evidence_view_version",
        "face",
        "status",
        "plane",
        "source",
        "as_of_us",
        "watermark_us",
        "completeness",
        "returned",
        "limit",
        "cursor",
        "truncated",
        "reason",
        "value",
    }
)


class ReadFaceEnvelopeError(ValueError):
    """A read-face envelope law violation — fail closed, never a guessed or half-built view."""


# ---------------------------------------------------------------------------------------------
# Small fail-closed type guards (no float, no bool-as-int, no silent coercion)
# ---------------------------------------------------------------------------------------------
def _is_plain_int(value: object) -> bool:
    # ``bool`` is an ``int`` subclass; the four-plane law refuses booleans-as-values, and so do we.
    return isinstance(value, int) and not isinstance(value, bool)


def _require_nonempty_str(name: str, value: object) -> None:
    if not isinstance(value, str) or value == "":
        raise ReadFaceEnvelopeError(f"{name} must be a non-empty string; got {value!r}")


def _require_epoch_us(name: str, value: object) -> None:
    if not _is_plain_int(value) or value < 0:
        raise ReadFaceEnvelopeError(
            f"{name} must be a non-negative UTC epoch-microsecond integer; got {value!r}")


def _require_nonneg_int(name: str, value: object) -> None:
    if not _is_plain_int(value) or value < 0:
        raise ReadFaceEnvelopeError(f"{name} must be a non-negative integer; got {value!r}")


# ---------------------------------------------------------------------------------------------
# The envelope
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ReadFaceEnvelope:
    """One read face's honest, source-named, freshness-stamped, completeness-declared projection.

    Construct through :func:`available` / :func:`unavailable` / :func:`not_measurable` (each
    fail-closed at build time via :func:`validate`); direct construction is permitted but the
    caller must still pass :func:`validate` before trusting the result.
    """

    face: str
    status: str
    source: str
    as_of_us: int
    plane: str | None = None
    watermark_us: int | None = None
    completeness: str = COMPLETENESS_NOT_APPLICABLE
    returned: int = 0
    limit: int | None = None
    cursor: str | None = None
    truncated: bool = False
    reason: str | None = None
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        """The verbatim serialized view — a read of record (a detached deep copy), never a
        consumption; every field is named, never a bare value."""
        return copy.deepcopy(
            {
                "evidence_view_version": EVIDENCE_VIEW_VERSION,
                "face": self.face,
                "status": self.status,
                "plane": self.plane,
                "source": self.source,
                "as_of_us": self.as_of_us,
                "watermark_us": self.watermark_us,
                "completeness": self.completeness,
                "returned": self.returned,
                "limit": self.limit,
                "cursor": self.cursor,
                "truncated": self.truncated,
                "reason": self.reason,
                "value": self.value,
            }
        )


def validate(view: ReadFaceEnvelope | dict) -> None:
    """The envelope contract — raises :class:`ReadFaceEnvelopeError` on any law violation.

    Names the exact failing conjunct so a caller sees which field is wrong rather than a single
    opaque error. Accepts either a :class:`ReadFaceEnvelope` or its serialized dict.
    """
    if isinstance(view, ReadFaceEnvelope):
        view = view.to_dict()
    if not isinstance(view, dict):
        raise ReadFaceEnvelopeError(
            f"a read-face envelope must be a ReadFaceEnvelope or a dict; got {type(view).__name__}")

    keys = frozenset(view)
    if keys != _CANONICAL_KEYS:
        missing = sorted(_CANONICAL_KEYS - keys)
        extra = sorted(keys - _CANONICAL_KEYS)
        raise ReadFaceEnvelopeError(
            f"envelope keys must be exactly the canonical set; missing={missing} extra={extra}")

    if view["evidence_view_version"] != EVIDENCE_VIEW_VERSION:
        raise ReadFaceEnvelopeError(
            f"evidence_view_version must be {EVIDENCE_VIEW_VERSION!r}; "
            f"got {view['evidence_view_version']!r}")

    _require_nonempty_str("face", view["face"])
    _require_nonempty_str("source", view["source"])

    status = view["status"]
    if status not in STATUSES:
        raise ReadFaceEnvelopeError(f"status must be one of {STATUSES}; got {status!r}")

    plane = view["plane"]
    if plane is not None and plane not in PLANES_ALL:
        raise ReadFaceEnvelopeError(
            f"plane must be one of {PLANES_ALL} or None; got {plane!r}")

    _require_epoch_us("as_of_us", view["as_of_us"])
    watermark_us = view["watermark_us"]
    if watermark_us is not None:
        _require_epoch_us("watermark_us", watermark_us)

    completeness = view["completeness"]
    if completeness not in COMPLETENESS_VOCAB:
        raise ReadFaceEnvelopeError(
            f"completeness must be one of {COMPLETENESS_VOCAB}; got {completeness!r}")

    returned = view["returned"]
    _require_nonneg_int("returned", returned)
    limit = view["limit"]
    if limit is not None:
        _require_nonneg_int("limit", limit)
    cursor = view["cursor"]
    if cursor is not None:
        _require_nonempty_str("cursor", cursor)
    truncated = view["truncated"]
    if not isinstance(truncated, bool):
        raise ReadFaceEnvelopeError(f"truncated must be a bool; got {truncated!r}")

    reason = view["reason"]
    value = view["value"]

    if status == STATUS_AVAILABLE:
        # An available projection carries a real (possibly measured-empty) value and names no
        # absence reason. "no empty green": a source that was actually absent must NOT arrive here.
        if value is None:
            raise ReadFaceEnvelopeError(
                "an AVAILABLE envelope must carry a projected value (a measured zero is honest; "
                "an absent source is UNAVAILABLE, never AVAILABLE with None)")
        if reason is not None:
            raise ReadFaceEnvelopeError(
                f"an AVAILABLE envelope must not name a reason; got {reason!r}")
        if completeness == COMPLETENESS_NOT_APPLICABLE:
            raise ReadFaceEnvelopeError(
                "an AVAILABLE envelope must declare COMPLETE or TRUNCATED completeness")
        if limit is not None and returned > limit:
            raise ReadFaceEnvelopeError(
                f"returned ({returned}) exceeds the applied bound limit ({limit})")
        if truncated != (completeness == COMPLETENESS_TRUNCATED):
            raise ReadFaceEnvelopeError(
                "truncated must agree with completeness (TRUNCATED <=> truncated is True)")
        if truncated and cursor is None:
            raise ReadFaceEnvelopeError("a truncated page must name a next-page cursor")
        if not truncated and cursor is not None:
            raise ReadFaceEnvelopeError("a complete page must not carry a cursor")
    else:
        # UNAVAILABLE / NOT_MEASURABLE: no value (never a fabricated zero), a named reason, and no
        # bounded-query fields (there is no result set to bound).
        if value is not None:
            raise ReadFaceEnvelopeError(
                f"a {status} envelope must carry no value (no fabricated zero); got {value!r}")
        _require_nonempty_str("reason", reason)
        if completeness != COMPLETENESS_NOT_APPLICABLE:
            raise ReadFaceEnvelopeError(
                f"a {status} envelope must declare NOT_APPLICABLE completeness; got {completeness!r}")
        if returned != 0:
            raise ReadFaceEnvelopeError(f"a {status} envelope must have returned == 0; got {returned}")
        if limit is not None:
            raise ReadFaceEnvelopeError(f"a {status} envelope must have limit None; got {limit!r}")
        if cursor is not None:
            raise ReadFaceEnvelopeError(f"a {status} envelope must have cursor None; got {cursor!r}")
        if truncated:
            raise ReadFaceEnvelopeError(f"a {status} envelope must have truncated False")


# ---------------------------------------------------------------------------------------------
# The three builders — the only correct way to mint an envelope (each fail-closed at build time)
# ---------------------------------------------------------------------------------------------
def available(
    *,
    face: str,
    source: str,
    as_of_us: int,
    value: Any,
    plane: str | None = None,
    watermark_us: int | None = None,
    returned: int = 0,
    limit: int | None = None,
    cursor: str | None = None,
) -> ReadFaceEnvelope:
    """A projection the face could compute. ``value`` is required (a measured zero is a real
    value; ``None`` is not — an absent source is :func:`unavailable`). ``truncated``/``completeness``
    are DERIVED from whether a ``cursor`` remains, so a face cannot claim COMPLETE while paging."""
    truncated = cursor is not None
    completeness = COMPLETENESS_TRUNCATED if truncated else COMPLETENESS_COMPLETE
    env = ReadFaceEnvelope(
        face=face,
        status=STATUS_AVAILABLE,
        source=source,
        as_of_us=as_of_us,
        plane=plane,
        watermark_us=watermark_us,
        completeness=completeness,
        returned=returned,
        limit=limit,
        cursor=cursor,
        truncated=truncated,
        reason=None,
        value=copy.deepcopy(value),
    )
    validate(env)
    return env


def unavailable(
    *,
    face: str,
    source: str,
    as_of_us: int,
    reason: str,
    plane: str | None = None,
    watermark_us: int | None = None,
) -> ReadFaceEnvelope:
    """The dependency is absent or unreachable — a named absence, never a fabricated zero."""
    env = ReadFaceEnvelope(
        face=face,
        status=STATUS_UNAVAILABLE,
        source=source,
        as_of_us=as_of_us,
        plane=plane,
        watermark_us=watermark_us,
        completeness=COMPLETENESS_NOT_APPLICABLE,
        returned=0,
        limit=None,
        cursor=None,
        truncated=False,
        reason=reason,
        value=None,
    )
    validate(env)
    return env


def not_measurable(
    *,
    face: str,
    source: str,
    as_of_us: int,
    reason: str,
    plane: str | None = None,
    watermark_us: int | None = None,
) -> ReadFaceEnvelope:
    """The source is present but the specific fact cannot be computed (e.g. missing lineage) —
    NOT_MEASURABLE, distinct from UNAVAILABLE, never an estimated or defaulted value."""
    env = ReadFaceEnvelope(
        face=face,
        status=STATUS_NOT_MEASURABLE,
        source=source,
        as_of_us=as_of_us,
        plane=plane,
        watermark_us=watermark_us,
        completeness=COMPLETENESS_NOT_APPLICABLE,
        returned=0,
        limit=None,
        cursor=None,
        truncated=False,
        reason=reason,
        value=None,
    )
    validate(env)
    return env


def from_dict(view: dict) -> ReadFaceEnvelope:
    """Rehydrate a validated serialized view into an envelope (deep-copying the value in)."""
    validate(view)
    return ReadFaceEnvelope(
        face=view["face"],
        status=view["status"],
        source=view["source"],
        as_of_us=view["as_of_us"],
        plane=view["plane"],
        watermark_us=view["watermark_us"],
        completeness=view["completeness"],
        returned=view["returned"],
        limit=view["limit"],
        cursor=view["cursor"],
        truncated=view["truncated"],
        reason=view["reason"],
        value=copy.deepcopy(view["value"]),
    )

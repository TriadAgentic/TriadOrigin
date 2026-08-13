"""``ob.displacement_bos.v2`` — F12 causal order block, one-BOS-one-lineage (R-F12).

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §R-F12 (milestone B04C). Supersedes
``ob.displacement_bos.v1`` (:mod:`triad_origin.structures.order_block_registry`, retired with the
§1.5 withdrawal banner; its bytes are preserved and its rows keep their version tag forever —
never-blend across formula versions). The four confirmed v1 defects this module repairs:

1. **Superseded origin tie-break** — v1 broke equal-offset ties by the larger body (mislabelled
   as a "quote" body-size term without any quantity). The RC3-effective rule is
   ``OB_ORIGIN_TIE = LATEST_THEN_MIN_SOURCE_ID`` (RATIFY_WITH_THIS_REPAIR): primary key = the
   LATEST bar index (max ``w``); residual tie at an identical index (multi-source ingestion
   only) = the MINIMUM immutable ``source_id``. The larger-body rule is DELETED — body size
   never participates, and no body-size output field exists anywhere in this module.
2. **One accepted BOS could confirm every same-direction pending block** — v2 enforces
   ONE-BOS-ONE-LINEAGE (RATIFY_WITH_THIS_REPAIR): the consumption map
   ``bos_occurrence_id -> ob_id`` is UNIQUE (1:1); when multiple pending same-direction
   candidates are eligible for one accepted break ``k``, the candidate with the EARLIEST
   displacement trigger ``g`` claims it (residual tie on identical ``g``: the smallest
   ``ob_id`` — the repo's deterministic residual rule, since no formula may leave a same-event
   tie undefined after this repair set); the others remain pending for their own later BOS or
   expire at their own ``H_bos``.
3. **TTL, mitigation, first-touch and lineage were absent** — v2 carries the full lifecycle::

       ORIGIN_CANDIDATE -> DISPLACED -> CONFIRMED_BY_BOS -> FRESH -> TOUCHED -> PARTIAL
         -> MITIGATED (touch depth >= OB_MITIGATION_FRACTION of zone height)
         -> terminal: BROKEN (accepted opposing F09 break through the zone far edge with
            OB_BREAK_BUFFER_TICKS) | EXPIRED (OB_TTL) | INVALIDATED (gap/revision)

   with the first touch consumed atomically (feeds F14 v2; ONE consumption per zone) and the
   confirmed identity = origin bar + displacement occurrence + BOS occurrence + formula/params.
4. **OHLC validity unenforced** — every bar enters ONLY as an E01
   :class:`~triad_origin.e01_interface.ValidatedBar` (the §1.1 VALID_BAR predicate), so an
   invalid-OHLC bar can never be recorded as an origin candidate nor test a zone; a quarantined
   bar invalidates the window/lifecycles that require it exactly as a GAP does (§1.1 —
   :func:`note_gap`).

CORRECTED LAW (R-F12, the pseudocode is normative)::

    Trigger: a qualified F11 displacement occurrence d (direction dir, trigger bar g).
    ORIGIN SELECTION (searching w in [g-W, g-1], most-recent first):
      candidate iff VALID_BAR(w) AND opposing(w):  bull OB needs bearish origin C_w < O_w;
                                                   bear OB needs bullish origin C_w > O_w.
      primary key  = LATEST bar index (max w)
      residual tie = MINIMUM immutable source_id (multi-source ingestion only)
    Zones (frozen): bull = [L_o, O_o]; bear = [O_o, H_o].
    CONFIRMATION: candidate -> CONFIRMED_BY_BOS only by a same-direction accepted F09 break
      occurrence k with first-breach source within H_bos bars after g (j - g in [1, H_bos]),
      AND k not already consumed.
    Same-event precedence: INVALIDATED > BROKEN > EXPIRED > MITIGATED > touch progressions
      (R-F12's OWN declared order — it deliberately ranks BROKEN above EXPIRED, overriding the
      §1.4 generic order for this formula; the §1.4 note blesses the per-formula line).
    Availability: max(displacement availability, linked BOS availability).

**Stream/intake law (declared; replay and live drive the SAME faces in recorded order).** For
one bar index ``j`` the causal order is: gap/revision facts -> the accepted F09 occurrences
derived from bar ``j`` (:func:`register_break` requires ``break_bar_index == last_bar_index + 1``,
i.e. the occurrence registers BEFORE its own bar evaluates — this is what makes the T6 same-bar
tie land BROKEN with no MITIGATED progression, per the R-F12 order) -> the bar itself
(:func:`evaluate`). A displacement occurrence registers at its trigger bar
(``trigger_bar_index == last_bar_index``) — anything else is out-of-order intake and refuses
loudly. The machine keeps its own bounded origin window (indexes ``[last-W, last]``, every entry
E01-validated at ingestion); an index skip (``i > last+1``) is a data-continuity break: every
non-terminal lifecycle is ``INVALIDATED{SEQUENCE_GAP}`` and the window restarts at ``i``.

**Bindings.** ``W`` = PAR-047 (FPB-0022) and ``H_bos`` = PAR-160 (FPB-0068) — existing rows;
``PAR-161`` (FPB-0069) is the opposing predicate, admitted ONLY as the exact declared
byte-string (strict inequality — a doji never opposes). The three NEW values are
``PROPOSED_MUST_RATIFY`` — this module implements each MECHANISM and wires the NAMED refusal;
no proposed value is hardcoded active (spec §0 rule 1):

* ``OB_MITIGATION_FRACTION`` (PAR-162 / FPB-0070, proposed 1/2 exact rational): consumed as an
  exact reduced rational ``num/den`` with ``0 < f <= 1``; the repository's unratified rule
  string refuses by name (``F12_BINDING_VALUE_NOT_RATIONAL``) — never evaluated, never
  defaulted.
* ``OB_BREAK_BUFFER_TICKS`` (PAR-163 / FPB-0071, proposed = the F09 ``b`` of the same
  partition): consumed as an exact integer ``>= 1`` (mirroring R-F09's ``b >= 1`` REQUIRED /
  ``b = 0`` REFUSE_CONFIG law); the repository's unratified rule prose AND the v1 ATR
  byte-string both refuse by name (``F12_BINDING_VALUE_NOT_INTEGER``). The v1 always-active
  byte-string break path is deliberately NOT carried into v2 — the v2 break check refuses until
  ratified (the strict §0-rule-1 reading; recorded, not smuggled).
* ``OB_TTL_BARS`` (proposed 192): the registry carries NO row for this parameter yet, so no
  capability can be minted for it today — evaluation without an authenticated ``OB_TTL_BARS``
  capability raises the named refusal ``BLOCKED_ON_RATIFY(OB_TTL_BARS)``
  (:class:`BlockedOnRatify`). The mechanism (implemented, capability-fed, never defaulted):
  a confirmed zone EXPIREs with reason ``OB_TTL`` on the first bar with
  ``bar_index - confirmed_bar_index >= OB_TTL_BARS`` (inclusive at TTL — the F10 sibling
  boundary convention, declared here pending the binding row's own boundary text; the registry
  row + its boundary rule are the owner's ratification follow-on). Registering the row is a
  ``docs/control`` change this module never makes.

The five registered F12 rows are ``BLOCKED_BINDING_V2_MIGRATION`` today, so a production sealed
bundle refuses F12 with the typed ``BLOCKED_BINDING_INCOMPLETE{F12}`` before any capability
exists (proven by test on the unmodified repository registry).

**Entrypoint (spec §C.3).** :func:`evaluate` ``(caps, env, state, *, source_id, bar_index,
bucket_start_us)`` where ``caps`` maps ``parameter_id ->
triad_origin.bindings.VerifiedCapability`` (exact type per entry; ``formula_id`` must equal
``F12`` and ``parameter_id`` must equal its key — a hand-built dict/int/str raises a typed
boundary rejection BEFORE any state transition) and ``env`` is exactly an E01
:class:`~triad_origin.e01_interface.ValidatedBar` (produced ONLY by ``require_valid_bar``).
Displacement / accepted-break / gap / revision facts are F11/F09/E01-owned intake consumed
through the pure faces :func:`register_displacement` / :func:`register_break` /
:func:`note_gap` / :func:`revise_bar` — the same capability boundary guards the
capability-consuming faces. Internals are a pure deterministic machine: no clock, no I/O, no
environment read, no randomness, no float. Every persisted/emitted integer is re-checked signed
int64 (§1.2 ``QUARANTINE_OVERFLOW``); stored penetration depths are reduced rationals
``[num, den]`` compared by cross-multiplication (§1.3); zone testing is availability-gated
(§1.4 :func:`triad_origin.exact.availability_allows`, so a zone confirmed at bar ``j`` is never
tested by bar ``j`` itself — the same-bar-retest ban). GV-F12-01 (§D.6) is the golden this
module owns; its registry row is an orchestrator follow-on (``docs/control`` is never edited
here).
"""

from __future__ import annotations

import re

from ..bindings import CapabilityForgeryError, VerifiedCapability
from ..canonical import canonical_json, sha256_hex
from ..e01_interface import ValidatedBar
from ..exact import (
    QuarantineOverflow,
    availability_allows,
    guard_int64,
    rational,
    rational_ge,
    rational_gt,
)
from ..transition import TransitionResult
from .common import LONG, SHORT, StructureLawError, abstention, require_direction, require_int

FORMULA_ID = "F12"
VERSION = "ob.displacement_bos.v2"
RETIRED_PREDECESSOR = "ob.displacement_bos.v1"

# --- parameter bindings (the caps map keys) -------------------------------------------------------
PARAM_LOOKBACK = "PAR-047"        # W, bars              (FPB-0022 ORDER_BLOCK_LOOKBACK)
PARAM_BOS_HORIZON = "PAR-160"     # H_bos, bars          (FPB-0068 ORDER_BLOCK_BOS_HORIZON)
PARAM_OPPOSING = "PAR-161"        # opposing predicate   (FPB-0069, declared byte-string only)
PARAM_MITIGATION = "PAR-162"      # OB_MITIGATION_FRACTION (FPB-0070, PROPOSED_MUST_RATIFY 1/2)
PARAM_BREAK_BUFFER = "PAR-163"    # OB_BREAK_BUFFER_TICKS  (FPB-0071, PROPOSED_MUST_RATIFY = F09 b)
PARAM_TTL = "OB_TTL_BARS"         # PROPOSED_MUST_RATIFY 192 — NO registry row exists yet
REQUIRED_PARAMETER_IDS = (
    PARAM_LOOKBACK,
    PARAM_BOS_HORIZON,
    PARAM_OPPOSING,
    PARAM_MITIGATION,
    PARAM_BREAK_BUFFER,
    PARAM_TTL,
)

# The exact declared PAR-161 predicate byte-string — the ONLY admissible value (strict
# inequality; a doji close == open never opposes). Any other byte refuses by name.
DECLARED_OPPOSING_PREDICATE = "bull:close<open; bear:close>open"

# --- ratified law rows (RATIFY_WITH_THIS_REPAIR — owner signature on the repair PR) ---------------
OB_ORIGIN_TIE = "LATEST_THEN_MIN_SOURCE_ID"
ONE_BOS_ONE_LINEAGE = True

# --- the closed phase vocabulary (the R-F12 lifecycle ladder, verbatim names) ---------------------
ORIGIN_CANDIDATE = "ORIGIN_CANDIDATE"    # the birth checkpoint (event trail only, never stored)
DISPLACED = "DISPLACED"                  # a pending candidate awaiting its confirming BOS
CONFIRMED_BY_BOS = "CONFIRMED_BY_BOS"    # the confirmation checkpoint (event trail only)
FRESH = "FRESH"
TOUCHED = "TOUCHED"
PARTIAL = "PARTIAL"
MITIGATED = "MITIGATED"
BROKEN = "BROKEN"
EXPIRED = "EXPIRED"
INVALIDATED = "INVALIDATED"
PHASES = (DISPLACED, FRESH, TOUCHED, PARTIAL, MITIGATED, BROKEN, EXPIRED, INVALIDATED)
TERMINAL_PHASES = (BROKEN, EXPIRED, INVALIDATED)
ACTIVE_ZONE_PHASES = (FRESH, TOUCHED, PARTIAL, MITIGATED)
_PROGRESS_RANK = {FRESH: 0, TOUCHED: 1, PARTIAL: 2, MITIGATED: 3}
_PROGRESS_LADDER = (FRESH, TOUCHED, PARTIAL, MITIGATED)

# R-F12's OWN same-event precedence, verbatim (dominant first). NOTE: BROKEN outranks EXPIRED —
# the per-formula declared rule, deliberately different from the §1.4 generic order (which puts
# EXPIRED above terminal); R-F12's own line wins for F12. Cross-face collisions are resolved by
# the declared intake order (module docstring); within one evaluate the only reachable collision
# is EXPIRED vs the touch progressions, resolved by this order.
SAME_EVENT_PRECEDENCE = (INVALIDATED, BROKEN, EXPIRED, MITIGATED, PARTIAL, TOUCHED)


def dominant_f12(candidates: object) -> str:
    """The winning transition under R-F12's declared same-event order; fail-closed inputs."""
    members = list(candidates)  # type: ignore[call-overload]
    if not members:
        raise StructureLawError("dominant_f12 requires at least one candidate transition")
    for name in members:
        if name not in SAME_EVENT_PRECEDENCE:
            raise StructureLawError(f"dominant_f12: {name!r} is not an F12 transition name")
    for name in SAME_EVENT_PRECEDENCE:
        if name in members:
            return name
    raise StructureLawError("unreachable: precedence order exhausted")  # pragma: no cover


# --- event kinds / reason codes -------------------------------------------------------------------
STATE_KIND = "ORDER_BLOCK_STATE"
FIRST_TOUCH_KIND = "ORDER_BLOCK_FIRST_TOUCH"

NO_OPPOSING_ORIGIN = "F12_NO_OPPOSING_ORIGIN_IN_LOOKBACK"
BOS_HORIZON_ELAPSED = "BOS_HORIZON_ELAPSED"
OB_TTL = "OB_TTL"
OPPOSING_BOS_BREAK = "OPPOSING_BOS_BREAK"
SEQUENCE_GAP = "SEQUENCE_GAP"
GAP_BAR = "GAP_BAR"
DEFINING_REVISION = "DEFINING_REVISION"
QUARANTINE_OVERFLOW_REASON = "QUARANTINE_OVERFLOW"

# Named refusals (PROPOSED_MUST_RATIFY law: the mechanism consumes exact conforming values;
# anything else refuses by name — never evaluated, never defaulted).
BINDING_VALUE_NOT_INTEGER = "F12_BINDING_VALUE_NOT_INTEGER"
BINDING_VALUE_NOT_RATIONAL = "F12_BINDING_VALUE_NOT_RATIONAL"
BINDING_VALUE_NOT_DECLARED = "F12_BINDING_VALUE_NOT_DECLARED"
STATE_VERSION_MISMATCH = "F12_STATE_VERSION_MISMATCH"
TRIGGER_OUT_OF_ORDER = "F12_TRIGGER_OUT_OF_ORDER"
BREAK_OUT_OF_ORDER = "F12_BREAK_OUT_OF_ORDER"
BAR_OUT_OF_ORDER = "F12_BAR_OUT_OF_ORDER"
INPUT_IDENTITY_CONFLICT = "F12_INPUT_IDENTITY_CONFLICT"

_NONNEG_INT_STR = r"0|[1-9][0-9]*"
_RATIONAL_STR = r"(0|[1-9][0-9]*)/([1-9][0-9]*)"
_UPPER_SNAKE = r"[A-Z][A-Z0-9_]*"


class BlockedOnRatify(RuntimeError):
    """The named refusal ``BLOCKED_ON_RATIFY(OB_TTL_BARS)`` (R-F12 BINDINGS).

    Raised when evaluation is attempted without an authenticated ``VerifiedCapability`` for a
    required parameter that has no ratified registry row. The mechanism exists; activation is
    ONLY via an authenticated binding — the proposed value (192) is never hardcoded active.
    """

    def __init__(self, parameter_id: str) -> None:
        super().__init__(f"BLOCKED_ON_RATIFY({parameter_id})")
        self.parameter_id = parameter_id


class EnvelopeContractError(TypeError):
    """A non-E01 envelope was presented at the F12 v2 boundary (typed, fail-closed).

    Raised BEFORE any state transition: a raw dict, a duck-typed stand-in, or a subclass in the
    ``env`` seat never reaches the machine (§C.3 — ``ValidatedInput`` exact type only).
    """


# ==================================================================================================
# capability + envelope + coordinate boundaries (all BEFORE any state transition)
# ==================================================================================================


def _capability_int(cap: VerifiedCapability, *, minimum: int, name: str) -> int:
    """An exact integer declared value, else the named ``F12_BINDING_VALUE_NOT_INTEGER`` refusal.

    Admits an exact int (bool excluded) or a canonical non-negative decimal string (the registry
    wire carries declared values as strings). The unratified rule prose / v1 ATR byte-strings
    are NOT ratified v2 values — they refuse here by name, never evaluated, never defaulted.
    ``minimum`` is the mechanism's structural domain floor (never a proposed value): W/H_bos/TTL
    are bar counts >= 1, and the break buffer mirrors R-F09's ``b >= 1`` REQUIRED law.
    """
    value = cap.value
    if isinstance(value, bool):
        result = None
    elif isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(_NONNEG_INT_STR, value):
        result = int(value)
    else:
        result = None
    if result is None:
        raise StructureLawError(
            f"{BINDING_VALUE_NOT_INTEGER}: {cap.parameter_id} declared value {value!r} is not "
            f"an exact non-negative integer (PROPOSED_MUST_RATIFY — an unratified rule string "
            f"is refused, never evaluated)")
    guarded = guard_int64(result, formula_id=FORMULA_ID, field=cap.parameter_id)
    if guarded < minimum:
        raise StructureLawError(
            f"{BINDING_VALUE_NOT_INTEGER}: {cap.parameter_id}={guarded} violates the structural "
            f"domain floor {name} >= {minimum}")
    return guarded


def _capability_fraction(cap: VerifiedCapability) -> tuple:
    """An exact reduced rational in ``(0, 1]``, else ``F12_BINDING_VALUE_NOT_RATIONAL``.

    Admits ``"num/den"`` (canonical non-negative decimals) or an exact int / canonical int
    string. The repository's unratified ``penetration>=...`` rule string refuses by name —
    never evaluated, never defaulted. Components are int64-guarded (§1.2).
    """
    value = cap.value
    num = den = None
    if isinstance(value, bool):
        pass
    elif isinstance(value, int):
        num, den = value, 1
    elif isinstance(value, str):
        match = re.fullmatch(_RATIONAL_STR, value)
        if match:
            num, den = int(match.group(1)), int(match.group(2))
        elif re.fullmatch(_NONNEG_INT_STR, value):
            num, den = int(value), 1
    if num is None or den is None:
        raise StructureLawError(
            f"{BINDING_VALUE_NOT_RATIONAL}: {cap.parameter_id} declared value {value!r} is not "
            f"an exact rational num/den (PROPOSED_MUST_RATIFY — an unratified rule string is "
            f"refused, never evaluated)")
    guard_int64(num, formula_id=FORMULA_ID, field=f"{cap.parameter_id}.num")
    guard_int64(den, formula_id=FORMULA_ID, field=f"{cap.parameter_id}.den")
    fraction = rational(num, den)
    if not (rational_gt(fraction, (0, 1)) and rational_ge((1, 1), fraction)):
        raise StructureLawError(
            f"{BINDING_VALUE_NOT_RATIONAL}: {cap.parameter_id}={value!r} violates the "
            f"structural domain 0 < fraction <= 1 of the zone height")
    return fraction


def _resolved_parameters(caps: object) -> tuple:
    """Validate the capability map; resolve ``(W, H_bos, fraction, buffer, ttl, digest_source)``.

    Exact-type check per entry (``type(entry) is VerifiedCapability`` — a subclass, duck-typed
    stand-in, dict, or int is a typed :class:`~triad_origin.bindings.CapabilityForgeryError`
    BEFORE any state transition); every entry must be minted for THIS formula and keyed by its
    own ``parameter_id``; the key set is exactly :data:`REQUIRED_PARAMETER_IDS`. A missing
    ``OB_TTL_BARS`` entry is the named :class:`BlockedOnRatify` refusal — the registry carries
    no row for it, so no capability can exist until the owner ratifies one.
    """
    if not isinstance(caps, dict):
        raise CapabilityForgeryError(
            f"F12 v2 requires a parameter_id -> VerifiedCapability map, got "
            f"{type(caps).__name__}")
    unknown = sorted(set(caps) - set(REQUIRED_PARAMETER_IDS))
    if unknown:
        raise CapabilityForgeryError(f"unexpected capability for F12 v2: {unknown[0]!r}")
    if PARAM_TTL not in caps:
        raise BlockedOnRatify(PARAM_TTL)
    missing = [pid for pid in REQUIRED_PARAMETER_IDS if pid not in caps]
    if missing:
        raise CapabilityForgeryError(f"missing capability for F12 v2: {missing[0]!r}")
    for pid in REQUIRED_PARAMETER_IDS:
        entry = caps[pid]
        if type(entry) is not VerifiedCapability:
            raise CapabilityForgeryError(
                f"F12 v2 parameter {pid!r} requires a VerifiedCapability, got "
                f"{type(entry).__name__}")
        if entry.formula_id != FORMULA_ID:
            raise CapabilityForgeryError(
                f"capability for {pid!r} was minted for formula {entry.formula_id!r}, "
                f"not {FORMULA_ID}")
        if entry.parameter_id != pid:
            raise CapabilityForgeryError(
                f"capability keyed {pid!r} carries parameter_id {entry.parameter_id!r}")
    predicate = caps[PARAM_OPPOSING].value
    if predicate != DECLARED_OPPOSING_PREDICATE:
        raise StructureLawError(
            f"{BINDING_VALUE_NOT_DECLARED}: {PARAM_OPPOSING} admits only the declared "
            f"predicate {DECLARED_OPPOSING_PREDICATE!r}, got {predicate!r}")
    lookback = _capability_int(caps[PARAM_LOOKBACK], minimum=1, name="W")
    horizon = _capability_int(caps[PARAM_BOS_HORIZON], minimum=1, name="H_bos")
    fraction = _capability_fraction(caps[PARAM_MITIGATION])
    buffer_ticks = _capability_int(caps[PARAM_BREAK_BUFFER], minimum=1, name="b")
    ttl = _capability_int(caps[PARAM_TTL], minimum=1, name="OB_TTL_BARS")
    digest_source = tuple(
        (pid, caps[pid].value, caps[pid].signed_root_digest) for pid in REQUIRED_PARAMETER_IDS)
    return lookback, horizon, fraction, buffer_ticks, ttl, digest_source


def _parameter_digest(digest_source: tuple) -> str:
    """The identity parameter digest: resolved ids/values bound to the signed bundle root."""
    return sha256_hex(canonical_json({
        "formula": FORMULA_ID,
        "formula_version": VERSION,
        "parameters": [
            {"parameter_id": pid, "declared_value": value, "signed_root_digest": root}
            for pid, value, root in digest_source
        ],
    }))


def _require_validated_bar(env: object) -> ValidatedBar:
    """§C.3 envelope law: the exact E01 ``ValidatedBar`` type, nothing else, ever."""
    if type(env) is not ValidatedBar:
        raise EnvelopeContractError(
            f"F12 v2 consumes a triad_origin.e01_interface.ValidatedBar produced by "
            f"require_valid_bar; got {type(env).__name__}")
    return env


def _coordinate(value: object, name: str, *, minimum: int | None = None) -> int:
    """An injected stream coordinate: exact int, int64-guarded, optionally floored."""
    exact = require_int(value, name)
    guarded = guard_int64(exact, formula_id=FORMULA_ID, field=name)
    if minimum is not None and guarded < minimum:
        raise StructureLawError(f"{name} must be >= {minimum}, got {guarded}")
    return guarded


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise StructureLawError(f"{name} must be a non-empty str")
    return value


# ==================================================================================================
# state shape (version-stamped; a v1 state can never blend into v2 — §1.5)
# ==================================================================================================

_BLOCK_KEYS = (
    "ob_id", "direction", "displacement_id", "trigger_bar_index", "claim_deadline_bar_index",
    "displacement_availability_us", "origin_bar_index", "origin_source_id",
    "origin_bar_identity", "zone_low_ticks", "zone_high_ticks", "far_edge_ticks",
    "proximal_edge_ticks", "phase", "bos_occurrence_id", "confirmed_bar_index",
    "availability_time_us", "ttl_deadline_bar_index", "first_touch_consumed",
    "first_touch_bar_identity", "max_depth", "terminal_reason",
)
_BLOCK_INT_KEYS = (
    "trigger_bar_index", "claim_deadline_bar_index", "displacement_availability_us",
    "origin_bar_index", "zone_low_ticks", "zone_high_ticks", "far_edge_ticks",
    "proximal_edge_ticks",
)
_BLOCK_OPTIONAL_INT_KEYS = (
    "confirmed_bar_index", "availability_time_us", "ttl_deadline_bar_index",
)
_BAR_FIELD_KEYS = (
    "bar_identity", "open_ticks", "high_ticks", "low_ticks", "close_ticks", "bucket_start_us",
)


def initial_state() -> dict:
    """The cold state: empty window, no blocks, empty consumption map."""
    return {
        "formula_version": VERSION,
        "last_bar_index": None,
        "bars": {},
        "blocks": {},
        "bos_consumed": {},
        "bos_seen": {},
    }


def _require_state(state: object) -> dict:
    if not isinstance(state, dict):
        raise StructureLawError("F12 v2 state must be an object")
    if state.get("formula_version") != VERSION:
        raise StructureLawError(
            f"{STATE_VERSION_MISMATCH}: state carries {state.get('formula_version')!r}, "
            f"this machine is {VERSION!r} (never-blend across formula versions)")
    for name in ("bars", "blocks", "bos_consumed", "bos_seen"):
        if not isinstance(state.get(name), dict):
            raise StructureLawError(f"F12 v2 state.{name} must be an object")
    last = state.get("last_bar_index")
    if last is not None:
        guard_int64(require_int(last, "last_bar_index"),
                    formula_id=FORMULA_ID, field="last_bar_index")
    return state


def _checked_block(row: object, ob_id: str) -> dict:
    """A block row re-validated on READ (no junk on a semantic compare after a checkpoint)."""
    if not isinstance(row, dict) or sorted(row) != sorted(_BLOCK_KEYS):
        raise StructureLawError(
            f"F12 v2 block row {ob_id!r} must carry exactly the keys {sorted(_BLOCK_KEYS)}")
    if row["ob_id"] != ob_id:
        raise StructureLawError(
            f"F12 v2 block row keyed {ob_id!r} carries ob_id {row['ob_id']!r}")
    require_direction(row["direction"])
    if row["phase"] not in PHASES:
        raise StructureLawError(f"F12 v2 block phase {row['phase']!r} is not in {PHASES}")
    for name in _BLOCK_INT_KEYS:
        guard_int64(require_int(row[name], name), formula_id=FORMULA_ID, field=name)
    for name in _BLOCK_OPTIONAL_INT_KEYS:
        if row[name] is not None:
            guard_int64(require_int(row[name], name), formula_id=FORMULA_ID, field=name)
    if not isinstance(row["first_touch_consumed"], bool):
        raise StructureLawError("F12 v2 block first_touch_consumed must be an exact bool")
    depth = row["max_depth"]
    if depth is not None:
        if not isinstance(depth, (list, tuple)) or len(depth) != 2:
            raise StructureLawError("F12 v2 block max_depth must be None or a [num, den] pair")
        num = guard_int64(require_int(depth[0], "max_depth.num"),
                          formula_id=FORMULA_ID, field="max_depth.num")
        den = guard_int64(require_int(depth[1], "max_depth.den"),
                          formula_id=FORMULA_ID, field="max_depth.den")
        if den <= 0 or num < 0:
            raise StructureLawError("F12 v2 block max_depth must satisfy num >= 0, den > 0")
    return row


def _checked_bar_fields(fields: object, key: str) -> dict:
    if not isinstance(fields, dict) or sorted(fields) != sorted(_BAR_FIELD_KEYS):
        raise StructureLawError(
            f"F12 v2 recorded bar {key!r} must carry exactly the keys {sorted(_BAR_FIELD_KEYS)}")
    for name in ("open_ticks", "high_ticks", "low_ticks", "close_ticks", "bucket_start_us"):
        guard_int64(require_int(fields[name], name), formula_id=FORMULA_ID, field=name)
    _nonempty_str(fields["bar_identity"], "bar_identity")
    return fields


# ==================================================================================================
# geometry (zones frozen at origin selection — R-F12 verbatim)
# ==================================================================================================


def _opposes(direction: str, open_ticks: int, close_ticks: int) -> bool:
    """The declared PAR-161 predicate, strict: bull needs C < O; bear needs C > O."""
    if direction == LONG:
        return close_ticks < open_ticks
    return close_ticks > open_ticks


def _zone_from_origin(direction: str, origin: dict) -> tuple:
    """``(zone_low, zone_high, far_edge, proximal_edge)`` — bull [L_o, O_o]; bear [O_o, H_o]."""
    if direction == LONG:
        z0, z1 = origin["low_ticks"], origin["open_ticks"]
        far, proximal = z0, z1
    else:
        z0, z1 = origin["open_ticks"], origin["high_ticks"]
        far, proximal = z1, z0
    if not z0 < z1:
        # Structurally unreachable: a strict opposing body forces a positive zone height
        # (bull: O > C >= L; bear: H >= C > O). Asserted anyway — fail closed, never a
        # zero-height zone.
        raise StructureLawError(f"F12 v2 zone must have positive height, got [{z0}, {z1}]")
    return z0, z1, far, proximal


def _touch_probe(direction: str, bar_fields: dict) -> int:
    return bar_fields["low_ticks"] if direction == LONG else bar_fields["high_ticks"]


def _contact(direction: str, row: dict, probe: int) -> bool:
    """Zone contact, inclusive at the proximal edge (T5)."""
    if direction == LONG:
        return probe <= row["proximal_edge_ticks"]
    return probe >= row["proximal_edge_ticks"]


def _depth_pair(direction: str, row: dict, probe: int) -> tuple:
    """Touch depth as a reduced rational of the zone height, clamped to [0, 1] (§1.3)."""
    z0, z1 = row["zone_low_ticks"], row["zone_high_ticks"]
    height = z1 - z0
    raw = (z1 - probe) if direction == LONG else (probe - z0)
    if raw < 0:
        raw = 0
    if raw > height:
        raw = height
    return rational(raw, height)


def _break_through_far_edge(direction: str, row: dict, close_ticks: int, buffer_ticks: int
                            ) -> bool:
    """Accepted opposing break through the far edge with the buffer (equality breaks)."""
    if direction == LONG:
        return close_ticks <= row["far_edge_ticks"] - buffer_ticks
    return close_ticks >= row["far_edge_ticks"] + buffer_ticks


# ==================================================================================================
# events
# ==================================================================================================


def _state_event(row: dict, *, from_phase: str, to_phase: str, bar_index: object,
                 reason: object, extra: dict | None = None) -> dict:
    event = {
        "event_kind": STATE_KIND,
        "formula": FORMULA_ID,
        "formula_version": VERSION,
        "ob_id": row["ob_id"],
        "direction": row["direction"],
        "from_phase": from_phase,
        "to_phase": to_phase,
        "bar_index": bar_index,
        "reason": reason,
    }
    if extra:
        event.update(extra)
    return event


def _terminal(row: dict, *, phase: str, reason: str, bar_index: object,
              extra: dict | None = None) -> tuple:
    new_row = dict(row)
    new_row["phase"] = phase
    new_row["terminal_reason"] = reason
    return new_row, (_state_event(
        row, from_phase=row["phase"], to_phase=phase, bar_index=bar_index, reason=reason,
        extra=extra),)


# ==================================================================================================
# the pure faces (replay and live drive the SAME functions in recorded order)
# ==================================================================================================


def register_displacement(
    caps: dict,
    state: dict,
    *,
    displacement_id: str,
    direction: str,
    trigger_bar_index: int,
    availability_time_us: int,
    source_event_id: str,
) -> TransitionResult:
    """A qualified F11 displacement occurrence ``d``: origin selection + a DISPLACED candidate.

    Pure; the capability boundary law applies exactly as at :func:`evaluate`. The trigger must
    reference the machine's CURRENT bar (``trigger_bar_index == last_bar_index`` — the F11->F12
    causal pipeline delivers the occurrence at its trigger bar; anything else, including a
    post-gap stale trigger, is out-of-order intake and refuses loudly, never a silent partial
    search). Origin selection runs over the machine's own E01-validated window: candidates are
    the recorded bars ``w in [g-W, g-1]`` whose body opposes; primary key = LATEST index;
    residual tie = MINIMUM ``source_id`` (``OB_ORIGIN_TIE``). Body size never participates. No
    qualifying candidate -> the named abstention ``F12_NO_OPPOSING_ORIGIN_IN_LOOKBACK`` and no
    block. Duplicate registration with byte-identical facts is an idempotent no-op; different
    facts under one ``displacement_id`` refuse (``F12_INPUT_IDENTITY_CONFLICT``).
    """
    lookback, horizon, _fraction, _buffer, _ttl, _digest = _resolved_parameters(caps)
    st = _require_state(state)
    d_id = _nonempty_str(displacement_id, "displacement_id")
    side = require_direction(direction)
    _nonempty_str(source_event_id, "source_event_id")
    g = _coordinate(trigger_bar_index, "trigger_bar_index", minimum=0)
    avail = _coordinate(availability_time_us, "availability_time_us")
    ob_id = f"ob:{d_id}"

    prior = st["blocks"].get(ob_id)
    if prior is not None:
        prior = _checked_block(prior, ob_id)
        if (prior["displacement_id"] == d_id and prior["direction"] == side
                and prior["trigger_bar_index"] == g
                and prior["displacement_availability_us"] == avail):
            return TransitionResult(state=st)  # idempotent duplicate registration
        raise StructureLawError(
            f"{INPUT_IDENTITY_CONFLICT}: displacement {d_id!r} is already registered with "
            f"different defining facts")

    last = st["last_bar_index"]
    if last is None or g != last:
        raise StructureLawError(
            f"{TRIGGER_OUT_OF_ORDER}: trigger_bar_index {g} must equal the machine's current "
            f"bar index {last!r} (the displacement registers at its trigger bar; the origin "
            f"window is otherwise unavailable)")

    # ORIGIN SELECTION over the recorded window — LATEST index, then MIN source_id. The window
    # holds only E01-validated bars, so VALID_BAR(w) holds by construction (§1.1).
    origin = None
    origin_index = None
    origin_source = None
    for index in range(g - 1, g - lookback - 1, -1):
        sources = st["bars"].get(str(index))
        if not sources:
            continue
        for source_id in sorted(sources):
            fields = _checked_bar_fields(sources[source_id], f"{index}/{source_id}")
            if _opposes(side, fields["open_ticks"], fields["close_ticks"]):
                origin, origin_index, origin_source = fields, index, source_id
                break
        if origin is not None:
            break
    if origin is None:
        return TransitionResult(state=st, events=(abstention(
            NO_OPPOSING_ORIGIN, formula=FORMULA_ID,
            detail="no opposing origin candidate in [g-W, g-1]; no order block is created",
            refs={"displacement_id": d_id, "trigger_bar_index": g, "lookback_bars": lookback,
                  "semantic_version": VERSION, "source_event_id": source_event_id}),))

    z0, z1, far, proximal = _zone_from_origin(side, origin)
    deadline = guard_int64(g + horizon, formula_id=FORMULA_ID, field="claim_deadline_bar_index")
    row = {
        "ob_id": ob_id,
        "direction": side,
        "displacement_id": d_id,
        "trigger_bar_index": g,
        "claim_deadline_bar_index": deadline,
        "displacement_availability_us": avail,
        "origin_bar_index": origin_index,
        "origin_source_id": origin_source,
        "origin_bar_identity": origin["bar_identity"],
        "zone_low_ticks": z0,
        "zone_high_ticks": z1,
        "far_edge_ticks": far,
        "proximal_edge_ticks": proximal,
        "phase": DISPLACED,
        "bos_occurrence_id": None,
        "confirmed_bar_index": None,
        "availability_time_us": None,
        "ttl_deadline_bar_index": None,
        "first_touch_consumed": False,
        "first_touch_bar_identity": None,
        "max_depth": None,
        "terminal_reason": None,
    }
    new_blocks = dict(st["blocks"])
    new_blocks[ob_id] = row
    event = _state_event(
        row, from_phase=ORIGIN_CANDIDATE, to_phase=DISPLACED, bar_index=g, reason=None,
        extra={
            "origin": {"bar_index": origin_index, "source_id": origin_source,
                       "bar_identity": origin["bar_identity"]},
            "zone": [z0, z1],
            "tie_rule": OB_ORIGIN_TIE,
            "source_event_id": source_event_id,
        })
    return TransitionResult(
        state={**st, "blocks": new_blocks}, events=(event,))


def register_break(
    caps: dict,
    state: dict,
    *,
    bos_occurrence_id: str,
    direction: str,
    break_bar_index: int,
    close_ticks: int,
    availability_time_us: int,
    source_event_id: str,
) -> TransitionResult:
    """An accepted F09 break occurrence ``k``: one-BOS-one-lineage confirmation + zone breaking.

    Intake-order law (module docstring): the occurrence derived from bar ``j`` registers BEFORE
    bar ``j`` evaluates — ``break_bar_index == last_bar_index + 1`` is enforced structurally, so
    a same-bar mitigation can never precede the break (T6: BROKEN wins). Duplicate registration
    with byte-identical facts is an idempotent no-op; different facts under one id refuse.

    CONFIRMATION (RATIFY_WITH_THIS_REPAIR): eligible pendings are same-direction DISPLACED
    candidates with ``j - g in [1, H_bos]`` and ``k`` not already consumed; the EARLIEST ``g``
    claims (residual tie: smallest ``ob_id``); the consumption map is UNIQUE 1:1. BREAKING: every
    active zone of the OPPOSING direction whose availability admits the occurrence and whose far
    edge is crossed by ``close_ticks`` with ``OB_BREAK_BUFFER_TICKS`` (equality breaks) goes
    BROKEN — terminal, R-F12 precedence ``BROKEN > EXPIRED > MITIGATED``.
    """
    _lookback, _horizon, _fraction, buffer_ticks, ttl, digest_source = _resolved_parameters(caps)
    st = _require_state(state)
    k_id = _nonempty_str(bos_occurrence_id, "bos_occurrence_id")
    side = require_direction(direction)
    _nonempty_str(source_event_id, "source_event_id")
    j = _coordinate(break_bar_index, "break_bar_index", minimum=0)
    close = _coordinate(close_ticks, "close_ticks")
    avail = _coordinate(availability_time_us, "availability_time_us")

    facts_digest = sha256_hex(canonical_json({
        "bos_occurrence_id": k_id, "direction": side, "break_bar_index": j,
        "close_ticks": close, "availability_time_us": avail,
    }))
    seen = st["bos_seen"].get(k_id)
    if seen is not None:
        if seen == facts_digest:
            return TransitionResult(state=st)  # idempotent duplicate registration
        raise StructureLawError(
            f"{INPUT_IDENTITY_CONFLICT}: break occurrence {k_id!r} was already registered "
            f"with different facts")

    last = st["last_bar_index"]
    if last is None or j != last + 1:
        raise StructureLawError(
            f"{BREAK_OUT_OF_ORDER}: break_bar_index {j} must equal last_bar_index+1 "
            f"({None if last is None else last + 1!r}) — an accepted occurrence registers "
            f"BEFORE its own bar evaluates (the T6 intake-order law)")

    new_blocks = dict(st["blocks"])
    new_consumed = dict(st["bos_consumed"])
    events: list = []

    # --- CONFIRMATION: one BOS, one lineage -------------------------------------------------------
    if k_id not in new_consumed:
        eligible: list = []
        for ob_id in sorted(new_blocks):
            row = _checked_block(new_blocks[ob_id], ob_id)
            if row["phase"] != DISPLACED or row["direction"] != side:
                continue
            offset = j - row["trigger_bar_index"]
            if 1 <= offset and j <= row["claim_deadline_bar_index"]:
                eligible.append(row)
        if eligible:
            claimant = min(eligible, key=lambda row: (row["trigger_bar_index"], row["ob_id"]))
            zone_avail = max(claimant["displacement_availability_us"], avail)
            new_row = dict(claimant)
            try:
                new_row["availability_time_us"] = guard_int64(
                    zone_avail, formula_id=FORMULA_ID, field="availability_time_us")
                new_row["ttl_deadline_bar_index"] = guard_int64(
                    j + ttl, formula_id=FORMULA_ID, field="ttl_deadline_bar_index")
            except QuarantineOverflow as exc:
                # §1.2: never wrap, never saturate, never emit. The claim happened — k is
                # consumed (an overflow may never WIDEN downstream confirmations) and the
                # lifecycle fails closed to INVALIDATED with the quarantine record journaled.
                new_consumed[k_id] = claimant["ob_id"]
                poisoned, poison_events = _terminal(
                    claimant, phase=INVALIDATED, reason=QUARANTINE_OVERFLOW_REASON,
                    bar_index=j, extra={"bos_occurrence_id": k_id})
                new_blocks[claimant["ob_id"]] = poisoned
                events.append(exc.record())
                events.extend(poison_events)
            else:
                new_consumed[k_id] = claimant["ob_id"]
                new_row["phase"] = FRESH
                new_row["bos_occurrence_id"] = k_id
                new_row["confirmed_bar_index"] = j
                new_blocks[claimant["ob_id"]] = new_row
                events.append(_state_event(
                    claimant, from_phase=DISPLACED, to_phase=CONFIRMED_BY_BOS, bar_index=j,
                    reason=None,
                    extra={
                        "lineage": {
                            "displacement_id": claimant["displacement_id"],
                            "bos_occurrence_id": k_id,
                            "origin_bar_index": claimant["origin_bar_index"],
                            "origin_source_id": claimant["origin_source_id"],
                            "origin_bar_identity": claimant["origin_bar_identity"],
                        },
                        "zone": [claimant["zone_low_ticks"], claimant["zone_high_ticks"]],
                        "availability_time_us": new_row["availability_time_us"],
                        "parameter_digest": _parameter_digest(digest_source),
                        "source_event_id": source_event_id,
                    }))
                events.append(_state_event(
                    new_row, from_phase=CONFIRMED_BY_BOS, to_phase=FRESH, bar_index=j,
                    reason=None))

    # --- BREAKING: accepted opposing break through the far edge with the buffer -------------------
    for ob_id in sorted(new_blocks):
        row = _checked_block(new_blocks[ob_id], ob_id)
        if row["phase"] not in ACTIVE_ZONE_PHASES or row["direction"] == side:
            continue
        if not availability_allows(row["availability_time_us"], avail):
            continue
        if _break_through_far_edge(row["direction"], row, close, buffer_ticks):
            broken, broke_events = _terminal(
                row, phase=BROKEN, reason=OPPOSING_BOS_BREAK, bar_index=j,
                extra={"bos_occurrence_id": k_id, "close_ticks": close,
                       "buffer_ticks": buffer_ticks})
            new_blocks[ob_id] = broken
            events.extend(broke_events)

    new_seen = dict(st["bos_seen"])
    new_seen[k_id] = facts_digest
    return TransitionResult(
        state={**st, "blocks": new_blocks, "bos_consumed": new_consumed, "bos_seen": new_seen},
        events=tuple(events))


def note_gap(state: dict, *, bar_index: object = None, reason: str = GAP_BAR
             ) -> TransitionResult:
    """A declared GAP bar / §1.1 quarantined bar: window down, non-terminal lifecycles down.

    A quarantined VALID_BAR failure invalidates any path/window that requires the bar exactly
    as a GAP does — the caller passes the quarantine's ``reason_code`` (e.g.
    ``QUARANTINE_INVALID_BAR``) as ``reason``. Every non-terminal block -> INVALIDATED; the
    recorded origin window is cleared and ``last_bar_index`` resets (a window crossing a gap is
    unsound — the next bar reseeds it). ``bar_index`` is the gapped index when known, else
    ``None`` (never fabricated).
    """
    st = _require_state(state)
    if not isinstance(reason, str) or not re.fullmatch(_UPPER_SNAKE, reason):
        raise StructureLawError(f"gap reason must be UPPER_SNAKE, got {reason!r}")
    at = None if bar_index is None else _coordinate(bar_index, "bar_index", minimum=0)
    new_blocks = dict(st["blocks"])
    events: list = []
    for ob_id in sorted(new_blocks):
        row = _checked_block(new_blocks[ob_id], ob_id)
        if row["phase"] in TERMINAL_PHASES:
            continue
        invalidated, inv_events = _terminal(
            row, phase=INVALIDATED, reason=reason, bar_index=at)
        new_blocks[ob_id] = invalidated
        events.extend(inv_events)
    if not events and not st["bars"] and st["last_bar_index"] is None:
        return TransitionResult(state=st)  # nothing to do — idempotent
    return TransitionResult(
        state={**st, "bars": {}, "last_bar_index": None, "blocks": new_blocks},
        events=tuple(events))


def revise_bar(state: dict, *, bar_index: int, source_event_id: str) -> TransitionResult:
    """A defining revision of bar ``bar_index`` -> INVALIDATED for every lifecycle it defines.

    T9: a block whose DEFINING facts reference the revised bar (origin bar, displacement
    trigger, or confirming BOS bar) is INVALIDATED (terminal absorbs). If the revised index
    intersects the recorded origin window, the window is cleared and reseeds (a selection over
    a revised range is unsound — fail closed, never a silent re-selection).
    """
    st = _require_state(state)
    _nonempty_str(source_event_id, "source_event_id")
    at = _coordinate(bar_index, "bar_index", minimum=0)
    new_blocks = dict(st["blocks"])
    events: list = []
    for ob_id in sorted(new_blocks):
        row = _checked_block(new_blocks[ob_id], ob_id)
        if row["phase"] in TERMINAL_PHASES:
            continue
        defining = (
            row["origin_bar_index"] == at
            or row["trigger_bar_index"] == at
            or row["confirmed_bar_index"] == at
        )
        if not defining:
            continue
        invalidated, inv_events = _terminal(
            row, phase=INVALIDATED, reason=DEFINING_REVISION, bar_index=at,
            extra={"source_event_id": source_event_id})
        new_blocks[ob_id] = invalidated
        events.extend(inv_events)
    window_hit = str(at) in st["bars"]
    if not events and not window_hit:
        return TransitionResult(state=st)
    new_state = {**st, "blocks": new_blocks}
    if window_hit:
        new_state["bars"] = {}
        new_state["last_bar_index"] = None
    return TransitionResult(state=new_state, events=tuple(events))


def evaluate(
    caps: dict, env: ValidatedBar, state: dict, *, source_id: str, bar_index: int,
    bucket_start_us: int,
) -> TransitionResult:
    """The §C.3 production entrypoint: one E01-validated finalized bar.

    * ``caps`` — ``parameter_id -> VerifiedCapability`` (exact type, formula F12, key ==
      ``parameter_id``); anything else is a typed rejection BEFORE any state transition; a
      missing ``OB_TTL_BARS`` capability is ``BLOCKED_ON_RATIFY(OB_TTL_BARS)``.
    * ``env`` — the E01 :class:`~triad_origin.e01_interface.ValidatedBar` (exact type; a raw
      dict raises :class:`EnvelopeContractError`).
    * ``source_id`` / ``bar_index`` / ``bucket_start_us`` — injected stream coordinates (the
      immutable source id, the finalized-bar index, and the bar's bucket start for the §1.4
      availability law); exact ints/str, never read from a clock.

    One call = (1) window ingestion (multi-source at one index lawful; identical duplicate =
    idempotent no-op; conflicting bytes under one ``(index, source)`` identity refuse; an index
    skip is ``INVALIDATED{SEQUENCE_GAP}`` for every non-terminal lifecycle + a window restart) ->
    (2) pending expiry (``bar_index > claim_deadline`` -> ``EXPIRED{BOS_HORIZON_ELAPSED}``) ->
    (3) per-zone lifecycle under R-F12's same-event order: ``EXPIRED{OB_TTL}`` dominates the
    touch progressions; a touching bar advances every stage it reaches (TOUCHED/PARTIAL/
    MITIGATED — a single bar may advance multiple stages); the FIRST touch is consumed
    atomically, exactly once per zone. Pure and deterministic — replay and live call THIS
    function; a checkpoint of the returned state resumes to a byte-identical stream (T12).
    """
    lookback, _horizon, fraction, _buffer, _ttl, _digest = _resolved_parameters(caps)
    bar = _require_validated_bar(env)
    src = _nonempty_str(source_id, "source_id")
    i = _coordinate(bar_index, "bar_index", minimum=0)
    bucket = _coordinate(bucket_start_us, "bucket_start_us")
    st = _require_state(state)

    fields = {
        "bar_identity": bar.bar_identity,
        "open_ticks": bar.open_ticks,
        "high_ticks": bar.high_ticks,
        "low_ticks": bar.low_ticks,
        "close_ticks": bar.close_ticks,
        "bucket_start_us": bucket,
    }

    last = st["last_bar_index"]
    events: list = []
    new_blocks = dict(st["blocks"])

    if last is not None and i < last:
        # A late re-delivery inside the retained window with byte-identical content is an
        # idempotent no-op; anything else is out-of-order ingestion (fail closed).
        sources = st["bars"].get(str(i))
        if sources is not None and src in sources and sources[src] == fields:
            return TransitionResult(state=st)
        raise StructureLawError(
            f"{BAR_OUT_OF_ORDER}: bar_index {i} arrived after last_bar_index {last} and is not "
            f"a byte-identical recorded duplicate")

    if last is not None and i == last:
        sources = st["bars"].get(str(i), {})
        if src in sources:
            if sources[src] == fields:
                return TransitionResult(state=st)  # exact duplicate: idempotent no-op
            raise StructureLawError(
                f"{INPUT_IDENTITY_CONFLICT}: bar ({i}, {src!r}) was already recorded with "
                f"different bytes")
        new_bars = {key: dict(value) for key, value in st["bars"].items()}
        new_bars.setdefault(str(i), {})[src] = fields
    elif last is None or i == last + 1:
        new_bars = {key: dict(value) for key, value in st["bars"].items()}
        new_bars.setdefault(str(i), {})[src] = fields
        floor = i - lookback
        for key in list(new_bars):
            if int(key) < floor:
                del new_bars[key]
    else:
        # i > last + 1: a skipped finalized index is a data-continuity break (§1.1: exactly as
        # a GAP). Every non-terminal lifecycle invalidates; the window restarts at this bar.
        for ob_id in sorted(new_blocks):
            row = _checked_block(new_blocks[ob_id], ob_id)
            if row["phase"] in TERMINAL_PHASES:
                continue
            invalidated, inv_events = _terminal(
                row, phase=INVALIDATED, reason=SEQUENCE_GAP, bar_index=i)
            new_blocks[ob_id] = invalidated
            events.extend(inv_events)
        new_bars = {str(i): {src: fields}}
        return TransitionResult(
            state={**st, "bars": new_bars, "last_bar_index": i, "blocks": new_blocks},
            events=tuple(events))

    # --- (2) pending expiry at the candidate's OWN H_bos ------------------------------------------
    for ob_id in sorted(new_blocks):
        row = _checked_block(new_blocks[ob_id], ob_id)
        if row["phase"] == DISPLACED and i > row["claim_deadline_bar_index"]:
            expired, exp_events = _terminal(
                row, phase=EXPIRED, reason=BOS_HORIZON_ELAPSED, bar_index=i)
            new_blocks[ob_id] = expired
            events.extend(exp_events)

    # --- (3) zone lifecycle under R-F12's declared same-event order -------------------------------
    for ob_id in sorted(new_blocks):
        row = _checked_block(new_blocks[ob_id], ob_id)
        if row["phase"] not in ACTIVE_ZONE_PHASES:
            continue
        new_row, row_events = _zone_on_bar(row, fields, i, src, fraction)
        if row_events or new_row != row:
            new_blocks[ob_id] = new_row
            events.extend(row_events)

    return TransitionResult(
        state={**st, "bars": new_bars, "last_bar_index": i, "blocks": new_blocks},
        events=tuple(events))


def _zone_on_bar(row: dict, fields: dict, i: int, source_id: str, fraction: tuple) -> tuple:
    """One active zone against one recorded bar: TTL expiry vs touch progressions."""
    candidates: list = []
    ttl_hit = i >= row["ttl_deadline_bar_index"]
    if ttl_hit:
        candidates.append(EXPIRED)
    # §1.4 availability: the zone may be tested only by bars whose bucket start is not before
    # its availability time (a zone confirmed at bar j is never tested by bar j itself).
    testable = availability_allows(row["availability_time_us"], fields["bucket_start_us"])
    probe = _touch_probe(row["direction"], fields)
    touching = testable and _contact(row["direction"], row, probe)
    if touching:
        candidates.append(TOUCHED)
    if not candidates:
        return row, ()
    if ttl_hit:
        # R-F12 order: EXPIRED > MITIGATED > touch progressions — the expiring bar does no
        # touch work (dominance asserted through the declared order, not assumed).
        assert dominant_f12(candidates) == EXPIRED
        return _terminal(row, phase=EXPIRED, reason=OB_TTL, bar_index=i)

    depth = _depth_pair(row["direction"], row, probe)
    prior_depth = row["max_depth"]
    if prior_depth is None or rational_gt(depth, (prior_depth[0], prior_depth[1])):
        new_depth = depth
    else:
        new_depth = (prior_depth[0], prior_depth[1])
    try:
        depth_pair = [
            guard_int64(new_depth[0], formula_id=FORMULA_ID, field="max_depth.num"),
            guard_int64(new_depth[1], formula_id=FORMULA_ID, field="max_depth.den"),
        ]
    except QuarantineOverflow as exc:
        # §1.2: an unpersistable depth is never emitted; the lifecycle fails closed.
        poisoned, poison_events = _terminal(
            row, phase=INVALIDATED, reason=QUARANTINE_OVERFLOW_REASON, bar_index=i)
        return poisoned, (exc.record(),) + poison_events

    if rational_ge((depth_pair[0], depth_pair[1]), fraction):
        target = MITIGATED
    elif depth_pair[0] > 0:
        target = PARTIAL
    else:
        target = TOUCHED

    new_row = dict(row)
    new_row["max_depth"] = depth_pair
    events: list = []
    from_phase = row["phase"]
    for stage in _PROGRESS_LADDER[_PROGRESS_RANK[row["phase"]] + 1:_PROGRESS_RANK[target] + 1]:
        events.append(_state_event(
            row, from_phase=from_phase, to_phase=stage, bar_index=i, reason=None,
            extra={"depth": list(depth_pair), "source_id": source_id}))
        from_phase = stage
        new_row["phase"] = stage
        if stage == TOUCHED and not new_row["first_touch_consumed"]:
            new_row["first_touch_consumed"] = True
            new_row["first_touch_bar_identity"] = fields["bar_identity"]
            events.append({
                "event_kind": FIRST_TOUCH_KIND,
                "formula": FORMULA_ID,
                "formula_version": VERSION,
                "ob_id": row["ob_id"],
                "direction": row["direction"],
                "bar_index": i,
                "source_id": source_id,
                "bar_identity": fields["bar_identity"],
                "depth": list(depth_pair),
                "consumed_once": True,
            })
    if not events and new_row["max_depth"] == row["max_depth"]:
        return row, ()
    return new_row, tuple(events)

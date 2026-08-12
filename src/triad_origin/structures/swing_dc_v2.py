"""``swing.dc.bar_extrema.v2`` — F03 directional-change swing with the ambiguous-bar law
(TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F03).

Repairs the retired ``swing.dc.bar_extrema.v1``
(:class:`triad_origin.structures.typed_level_registry.DirectionalChangeSwing`, banner
``RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F03}``): v1 evaluated
the reversal against the POST-extension extreme, so a wide-range extending bar confirmed a swing
at its own bar (``confirm_bar == extreme_bar``) — the intrabar path is unknowable from OHLC, so
that outcome was implementation-defined.

**THE AMBIGUOUS-BAR LAW (PAR-036b ``DC_AMBIGUOUS_BAR_RULE = ABSTAIN_EXTEND_WINS`` —
RATIFY_WITH_THIS_REPAIR).** A bar that establishes or extends the current provisional extreme
CANNOT be the confirmation bar for the reversal of that same extreme. Confirmation requires
``j > x`` strictly, where ``x`` is the bar of the frozen provisional extreme AFTER processing bar
``j-1``. Within one bar, extreme extension is evaluated FIRST; reversal evaluation against that
bar uses the extreme as it stood BEFORE the bar. If the pre-bar extreme's reversal threshold is
met by bar ``j`` AND bar ``j`` also extends the extreme in the leg direction, the extension wins
and no reversal is confirmed by bar ``j`` (the ``F03_AMBIGUOUS_BAR_ABSTENTION`` audit fact —
the spec's ``AMBIGUOUS_BAR_ABSTENTION{j}``, repo-prefixed). delta is frozen at each new
provisional extreme (unchanged v1 law); an equal extreme keeps the earliest bar (unchanged).

**Delta mechanism (R-F03 CORRECTED LAW, general form)::**

    delta_x = max( min_reversal_ticks,
                   ceil_div(abs(price_ticks_x) * reversal_bps, 10000),
                   ceil_div(k_vol_num * ATR_ticks_before_x, k_vol_den) )

The ONLY executable instantiation is the declared PAR-036 byte-string
``max(5,ceil(ATR14_ticks*1/4))`` — ``min_reversal_ticks=5``, ``reversal_bps=0`` (the declared
rule carries no price term; zero is the exact identity of ``max``), ``k_vol=(1,4)`` — proven
equal to :func:`triad_origin.structures.common.evaluate_declared_rational` by test. No other
``reversal_bps``/``k_vol`` value is reachable (GV-005: "no reversal_bps or k_vol term exists").

**Bindings.** PAR-036 stays ``PROPOSED_RC2_MUST_RATIFY`` (registry row FPB-0011 BLOCKED): this
module implements the mechanism and the named refusal ``BLOCKED_ON_RATIFY(PAR-036)`` —
activation ONLY via an authenticated binding capability
(:func:`triad_origin.transition.require_bundle` refuses ``BLOCKED_BINDING_INCOMPLETE:F03`` on
the repository registry, so no capability can be minted until the owner ratifies the row).
KNOWN TRANSPORT INTERLOCK (pinned by test): the declared byte-string contains ``*``, which the
B01C-BIND-04 wildcard-sentinel law refuses inside an ACTIVE row's resolved fields — so the
ratification train must additionally land a loader-acceptable declared-value transport; if that
transport re-encodes the expression, the admission gate here moves in the SAME train. PAR-036b
(``ABSTAIN_EXTEND_WINS``) is ``RATIFY_WITH_THIS_REPAIR`` — the owner's signature on the repair
PR ratifies it; its registry row is an orchestrator follow-on (this module never edits
``docs/control``).

**Entrypoint (spec §C.3).** ``evaluate(caps, env, state, *, atr14_ticks)`` where ``caps`` is a
mapping ``parameter_id -> triad_origin.bindings.VerifiedCapability`` (each entry exact-type
checked; ``formula_id`` must equal ``F03`` and ``parameter_id`` must equal its key — a
hand-built dict/int/str raises a typed boundary rejection BEFORE any state transition) and
``env`` is exactly an :class:`triad_origin.e01_interface.ValidatedBar` (produced ONLY by
``require_valid_bar`` — a raw mapping raises the §1.1 quarantine). ``atr14_ticks`` is the
injected causal F02 dependency for this bar (``None`` = warm-up/gap → the named abstention
``F03_NO_ATR``, no shortened fallback). Replay and live consumption call this ONE transition
implementation; internals are a pure deterministic machine (no clock, no I/O, no float).

Every persisted/emitted integer is re-checked signed int64 (§1.2 ``QUARANTINE_OVERFLOW``).
Emitted swing atoms carry ``semantic_version = swing.dc.bar_extrema.v2`` — never-blend across
formula versions applies exactly as across cohorts (§1.5).
"""

from __future__ import annotations

from .. import bindings
from ..e01_interface import QuarantineInvalidBar, ValidatedBar
from ..exact import guard_int64
from ..transition import TransitionResult
from . import common
from .typed_level_registry import SWING_HIGH, SWING_LOW, TYPED_LEVEL

FORMULA_ID = "F03"
SEMANTIC_VERSION = "swing.dc.bar_extrema.v2"
RETIRED_PREDECESSOR = "swing.dc.bar_extrema.v1"

# The authenticated-capability surface: F03 consumes exactly ONE bound parameter.
PARAMETER_DC_REVERSAL = "PAR-036"          # registry row FPB-0011 (BLOCKED until ratified)
REQUIRED_PARAMETERS = (PARAMETER_DC_REVERSAL,)

# PAR-036b — RATIFY_WITH_THIS_REPAIR: the ambiguous-bar rule this machine hardwires as law.
DC_AMBIGUOUS_BAR_RULE = "ABSTAIN_EXTEND_WINS"

# Named event vocabulary (UPPER_SNAKE per common.abstention law).
AMBIGUOUS_BAR_ABSTENTION = "F03_AMBIGUOUS_BAR_ABSTENTION"   # spec: AMBIGUOUS_BAR_ABSTENTION{j}
AMBIGUOUS_SEED_REVERSAL = "F03_AMBIGUOUS_SEED_REVERSAL"     # seed two-sided confirm tie (repo law)
NO_ATR = "F03_NO_ATR"

_SEED = "SEED"
_UP = "UP"
_DOWN = "DOWN"
_MODES = (_SEED, _UP, _DOWN)
_STATE_KEYS = ("last_bar_identity", "mode", "prov_high", "prov_low")
_FROZEN_KEYS = ("extreme_ticks", "delta_ticks", "origin_bar_identity")


class BlockedOnRatify(RuntimeError):
    """The named refusal ``BLOCKED_ON_RATIFY(PAR-036)`` (R-F03 BINDINGS).

    Raised when evaluation is attempted without an authenticated ``VerifiedCapability`` for the
    required parameter. The mechanism exists; activation is ONLY via authenticated binding — the
    proposed value is never hardcoded as active (spec §0 rule 1).
    """

    def __init__(self, parameter_id: str) -> None:
        super().__init__(f"BLOCKED_ON_RATIFY({parameter_id})")
        self.parameter_id = parameter_id


# ---------------------------------------------------------------------------------------------
# The delta mechanism (R-F03 CORRECTED LAW) — exact integers only
# ---------------------------------------------------------------------------------------------

def delta_ticks_general(
    *,
    price_ticks_x: int,
    atr_ticks_before_x: int,
    min_reversal_ticks: int,
    reversal_bps: int,
    k_vol_num: int,
    k_vol_den: int,
) -> int:
    """The R-F03 general delta mechanism, verbatim (transient products may exceed int64)::

        delta_x = max( min_reversal_ticks,
                       ceil_div(abs(price_ticks_x) * reversal_bps, 10000),
                       ceil_div(k_vol_num * ATR_ticks_before_x, k_vol_den) )

    Domain: every input an exact int; ``min_reversal_ticks >= 0``, ``reversal_bps >= 0``,
    ``k_vol_num >= 0``, ``k_vol_den > 0``, ``atr_ticks_before_x > 0`` (a null/absent ATR is the
    caller's warm-up abstention, never a zero here). The result is re-checked signed int64 at
    the boundary (§1.2).
    """
    price = common.require_int(price_ticks_x, "price_ticks_x")
    atr = common.require_int(atr_ticks_before_x, "atr_ticks_before_x")
    floor_ticks = common.require_int(min_reversal_ticks, "min_reversal_ticks")
    bps = common.require_int(reversal_bps, "reversal_bps")
    k_num = common.require_int(k_vol_num, "k_vol_num")
    k_den = common.require_int(k_vol_den, "k_vol_den")
    if floor_ticks < 0 or bps < 0 or k_num < 0 or k_den <= 0:
        raise common.StructureLawError(
            "delta domain: min_reversal_ticks >= 0, reversal_bps >= 0, k_vol_num >= 0, "
            "k_vol_den > 0")
    if atr <= 0:
        raise common.StructureLawError(
            "ATR_ticks_before_x must be a positive integer (warm-up abstains upstream)")
    term_bps = common.ceil_div(abs(price) * bps, 10000)
    term_vol = common.ceil_div(k_num * atr, k_den)
    return guard_int64(
        max(floor_ticks, term_bps, term_vol), formula_id=FORMULA_ID, field="delta_ticks")


# The declared PAR-036 byte-string is the ONLY executable instantiation of the general form.
# reversal_bps=0 is the exact algebraic identity for the absent price term (max(a, 0, b) ==
# max(a, b)); the two-term equality with common.evaluate_declared_rational is pinned by test.
_DECLARED_RULE_TERMS = {
    common.DECLARED_DC_REVERSAL: {
        "min_reversal_ticks": 5, "reversal_bps": 0, "k_vol_num": 1, "k_vol_den": 4,
    },
}


def declared_delta_ticks(declared_rule: str, price_ticks_x: int, atr_ticks_before_x: int) -> int:
    """Evaluate the general mechanism under a DECLARED rule byte-string, or fail closed."""
    terms = _DECLARED_RULE_TERMS.get(declared_rule)
    if terms is None:
        raise common.StructureLawError(
            f"undeclared DC reversal rule: {declared_rule!r} — only the exact declared "
            "value strings are executable")
    return delta_ticks_general(
        price_ticks_x=price_ticks_x, atr_ticks_before_x=atr_ticks_before_x, **terms)


# ---------------------------------------------------------------------------------------------
# Boundary law (spec §C.3): authenticated capability + E01-validated bar, nothing else
# ---------------------------------------------------------------------------------------------

def _require_caps(caps: object) -> str:
    """Admit the capability mapping; return the declared rule string, else typed refusal."""
    if not isinstance(caps, dict):
        raise bindings.CapabilityForgeryError(
            "F03 caps must be a mapping parameter_id -> VerifiedCapability; "
            f"got {type(caps).__name__}")
    unknown = [key for key in caps if key not in REQUIRED_PARAMETERS]
    if unknown:
        raise bindings.CapabilityForgeryError(
            f"F03 admits only the parameters {REQUIRED_PARAMETERS}; unknown key {unknown[0]!r}")
    if PARAMETER_DC_REVERSAL not in caps:
        # The R-F03 named refusal: no authenticated PAR-036 binding, no machine.
        raise BlockedOnRatify(PARAMETER_DC_REVERSAL)
    cap = caps[PARAMETER_DC_REVERSAL]
    if type(cap) is not bindings.VerifiedCapability:
        raise bindings.CapabilityForgeryError(
            "F03 parameters require a VerifiedCapability produced by require_bundle; "
            f"got {type(cap).__name__}")
    if cap.formula_id != FORMULA_ID:
        raise bindings.CapabilityForgeryError(
            f"capability formula_id {cap.formula_id!r} is not {FORMULA_ID!r}")
    if cap.parameter_id != PARAMETER_DC_REVERSAL:
        raise bindings.CapabilityForgeryError(
            f"capability parameter_id {cap.parameter_id!r} does not equal its mapping key "
            f"{PARAMETER_DC_REVERSAL!r}")
    rule = cap.value
    if rule != common.DECLARED_DC_REVERSAL:
        raise common.StructureLawError(
            f"F03 admits only the declared PAR-036 rule {common.DECLARED_DC_REVERSAL!r}, "
            f"got {rule!r}")
    return rule


def _require_env(env: object) -> ValidatedBar:
    """Exactly an e01 ValidatedBar — a raw mapping/subclass never crosses the boundary (§1.1)."""
    if type(env) is not ValidatedBar:
        raise QuarantineInvalidBar(
            bar_identity=None,
            reason="F03 env must be an e01_interface.ValidatedBar produced by "
                   f"require_valid_bar; got {type(env).__name__}")
    return env


def _require_frozen(record: object, name: str) -> dict:
    if not isinstance(record, dict) or sorted(record) != sorted(_FROZEN_KEYS):
        raise common.StructureLawError(f"state {name} must carry exactly {_FROZEN_KEYS}")
    extreme = guard_int64(record["extreme_ticks"], formula_id=FORMULA_ID, field="extreme_ticks")
    delta = guard_int64(record["delta_ticks"], formula_id=FORMULA_ID, field="delta_ticks")
    if delta <= 0:
        raise common.StructureLawError(f"state {name} delta_ticks must be positive")
    origin = record["origin_bar_identity"]
    if not isinstance(origin, str) or not origin:
        raise common.StructureLawError(f"state {name} origin_bar_identity must be non-empty str")
    return {"extreme_ticks": extreme, "delta_ticks": delta, "origin_bar_identity": origin}


def _require_state(state: object) -> dict:
    if not isinstance(state, dict) or sorted(state) != sorted(_STATE_KEYS):
        raise common.StructureLawError(f"F03 state must carry exactly the keys {_STATE_KEYS}")
    mode = state["mode"]
    if mode not in _MODES:
        raise common.StructureLawError(f"F03 state mode must be one of {_MODES}, got {mode!r}")
    last = state["last_bar_identity"]
    if last is not None and (not isinstance(last, str) or not last):
        raise common.StructureLawError("F03 state last_bar_identity must be None or non-empty str")
    prov_high, prov_low = state["prov_high"], state["prov_low"]
    if mode == _SEED:
        if (prov_high is None) != (prov_low is None):
            raise common.StructureLawError("F03 SEED state freezes both extremes or neither")
        if prov_high is not None:
            prov_high = _require_frozen(prov_high, "prov_high")
            prov_low = _require_frozen(prov_low, "prov_low")
    elif mode == _UP:
        if prov_low is not None:
            raise common.StructureLawError("F03 UP leg carries no prov_low")
        prov_high = _require_frozen(prov_high, "prov_high")
    else:
        if prov_high is not None:
            raise common.StructureLawError("F03 DOWN leg carries no prov_high")
        prov_low = _require_frozen(prov_low, "prov_low")
    return {"last_bar_identity": last, "mode": mode,
            "prov_high": prov_high, "prov_low": prov_low}


# ---------------------------------------------------------------------------------------------
# The pure machine
# ---------------------------------------------------------------------------------------------

def initial_state() -> dict:
    """The cold state: two-sided SEED with no frozen extreme yet."""
    return {"last_bar_identity": None, "mode": _SEED, "prov_high": None, "prov_low": None}


def evaluate(caps: dict, env: ValidatedBar, state: dict, *, atr14_ticks: int | None
             ) -> TransitionResult:
    """The ONE ``swing.dc.bar_extrema.v2`` transition — identical for live and replay.

    Boundary order (all BEFORE any state transition): capability law -> E01 envelope law ->
    state-shape law. ``atr14_ticks`` is the injected causal F02 ATR for this bar; ``None`` is
    the warm-up/gap abstention (``F03_NO_ATR``, zero mutation, no shortened fallback).
    """
    rule = _require_caps(caps)
    bar = _require_env(env)
    st = _require_state(state)
    if bar.bar_identity == st["last_bar_identity"]:
        return TransitionResult(state=st)  # exact retransmission: idempotent no-op
    if atr14_ticks is None:
        return TransitionResult(state=st, events=(common.abstention(
            NO_ATR, formula=FORMULA_ID,
            detail="causal ATR14 is null (warm-up/gap); no swing evaluation, "
                   "no shortened fallback",
            refs={"bar_identity": bar.bar_identity, "semantic_version": SEMANTIC_VERSION}),))
    atr = guard_int64(atr14_ticks, formula_id=FORMULA_ID, field="atr14_ticks")

    def freeze(extreme_ticks: int, bar_identity: str) -> dict:
        """Freeze a provisional extreme + its delta (delta frozen at each new extreme)."""
        return {
            "extreme_ticks": guard_int64(
                extreme_ticks, formula_id=FORMULA_ID, field="extreme_ticks"),
            "delta_ticks": declared_delta_ticks(rule, extreme_ticks, atr),
            "origin_bar_identity": bar_identity,
        }

    high, low = bar.high_ticks, bar.low_ticks
    if st["mode"] == _SEED:
        return _seed(st, bar.bar_identity, high, low, freeze)
    return _leg(st, bar.bar_identity, high, low, freeze)


def _ambiguous_fact(bar_identity: str) -> dict:
    """The PAR-036b audit fact — spec ``AMBIGUOUS_BAR_ABSTENTION{j}`` (ONE fact per bar j)."""
    return common.abstention(
        AMBIGUOUS_BAR_ABSTENTION, formula=FORMULA_ID,
        detail="extension wins: the bar extends the provisional extreme AND meets the "
               "pre-bar reversal threshold; no reversal is confirmed by this bar",
        refs={"bar_identity": bar_identity, "rule": DC_AMBIGUOUS_BAR_RULE,
              "semantic_version": SEMANTIC_VERSION})


def _seed(st: dict, bar_id: str, high: int, low: int, freeze) -> TransitionResult:
    """Two-sided SEED under the v2 pre-bar law, applied independently per side.

    Extension is evaluated FIRST; each side's reversal is evaluated against that side's PRE-BAR
    extreme; a side that extends AND reverses abstains (extension wins — PAR-036b). Both sides
    confirming with NEITHER extended is the genuinely two-sided seed tie: the named abstention
    ``F03_AMBIGUOUS_SEED_REVERSAL`` re-seeds from this bar (a side-preferring guess would break
    the LONG/SHORT mirror law — PAR-036b decides extend-vs-reverse, never confirm-vs-confirm).
    """
    pre_high, pre_low = st["prov_high"], st["prov_low"]
    if pre_high is None:
        return TransitionResult(state={
            "last_bar_identity": bar_id, "mode": _SEED,
            "prov_high": freeze(high, bar_id), "prov_low": freeze(low, bar_id)})
    extends_high = high > pre_high["extreme_ticks"]
    extends_low = low < pre_low["extreme_ticks"]
    reverses_high = pre_high["extreme_ticks"] - low >= pre_high["delta_ticks"]
    reverses_low = high - pre_low["extreme_ticks"] >= pre_low["delta_ticks"]
    ambiguous = (extends_high and reverses_high) or (extends_low and reverses_low)
    confirm_high = reverses_high and not extends_high
    confirm_low = reverses_low and not extends_low
    preceding: tuple = (_ambiguous_fact(bar_id),) if ambiguous else ()
    if confirm_high and confirm_low:
        return TransitionResult(
            state={"last_bar_identity": bar_id, "mode": _SEED,
                   "prov_high": freeze(high, bar_id), "prov_low": freeze(low, bar_id)},
            events=preceding + (common.abstention(
                AMBIGUOUS_SEED_REVERSAL, formula=FORMULA_ID,
                detail="both pre-bar seed reversals confirm on one bar without extending "
                       "either extreme; direction is unknowable from OHLC — re-seeding "
                       "from this bar",
                refs={"bar_identity": bar_id, "semantic_version": SEMANTIC_VERSION}),))
    if confirm_high:
        return _confirm(SWING_HIGH, pre_high, bar_id, low, freeze, preceding)
    if confirm_low:
        return _confirm(SWING_LOW, pre_low, bar_id, high, freeze, preceding)
    prov_high = freeze(high, bar_id) if extends_high else pre_high
    prov_low = freeze(low, bar_id) if extends_low else pre_low
    return TransitionResult(
        state={"last_bar_identity": bar_id, "mode": _SEED,
               "prov_high": prov_high, "prov_low": prov_low},
        events=preceding)


def _leg(st: dict, bar_id: str, high: int, low: int, freeze) -> TransitionResult:
    """One-sided leg under the v2 pre-bar law (R-F03 ALGORITHM steps 1-5, mirrored for DOWN)."""
    if st["mode"] == _UP:
        prov = st["prov_high"]
        extends = high > prov["extreme_ticks"]                          # step 1 (strict)
        reverses = prov["extreme_ticks"] - low >= prov["delta_ticks"]   # step 2 (PRE-BAR extreme)
        if extends and reverses:                                        # step 3: extension wins
            return TransitionResult(
                state={"last_bar_identity": bar_id, "mode": _UP,
                       "prov_high": freeze(high, bar_id), "prov_low": None},
                events=(_ambiguous_fact(bar_id),))
        if extends:                                                     # step 4
            return TransitionResult(state={
                "last_bar_identity": bar_id, "mode": _UP,
                "prov_high": freeze(high, bar_id), "prov_low": None})
        if reverses:                                                    # step 5
            return _confirm(SWING_HIGH, prov, bar_id, low, freeze, ())
        return TransitionResult(state={
            "last_bar_identity": bar_id, "mode": _UP,
            "prov_high": prov, "prov_low": None})
    prov = st["prov_low"]
    extends = low < prov["extreme_ticks"]
    reverses = high - prov["extreme_ticks"] >= prov["delta_ticks"]
    if extends and reverses:
        return TransitionResult(
            state={"last_bar_identity": bar_id, "mode": _DOWN,
                   "prov_high": None, "prov_low": freeze(low, bar_id)},
            events=(_ambiguous_fact(bar_id),))
    if extends:
        return TransitionResult(state={
            "last_bar_identity": bar_id, "mode": _DOWN,
            "prov_high": None, "prov_low": freeze(low, bar_id)})
    if reverses:
        return _confirm(SWING_LOW, prov, bar_id, high, freeze, ())
    return TransitionResult(state={
        "last_bar_identity": bar_id, "mode": _DOWN,
        "prov_high": None, "prov_low": prov})


def _confirm(kind: str, prov: dict, bar_id: str, opposite_extreme: int, freeze,
             preceding: tuple) -> TransitionResult:
    """Emit the confirmed swing at the PRE-BAR extreme; flip the leg from this bar's opposite.

    R-F03 ACCEPTANCE invariant, asserted structurally: no confirmation ever carries
    ``confirm_bar == extreme_bar`` (the pre-bar extreme was frozen after bar j-1).
    """
    if prov["origin_bar_identity"] == bar_id:
        raise common.StructureLawError(
            "F03 invariant violated: a confirmation may never carry "
            "confirm_bar == extreme_bar")
    event = {
        "event_kind": TYPED_LEVEL,
        "formula": FORMULA_ID,
        "semantic_version": SEMANTIC_VERSION,
        "kind": kind,
        "direction": common.LONG if kind == SWING_HIGH else common.SHORT,
        "level_ticks": guard_int64(
            prov["extreme_ticks"], formula_id=FORMULA_ID, field="level_ticks"),
        "delta_ticks": guard_int64(
            prov["delta_ticks"], formula_id=FORMULA_ID, field="delta_ticks"),
        "origin_bar_identity": prov["origin_bar_identity"],
        "confirmed_by_bar_identity": bar_id,
    }
    next_leg = freeze(opposite_extreme, bar_id)
    if kind == SWING_HIGH:
        state = {"last_bar_identity": bar_id, "mode": _DOWN,
                 "prov_high": None, "prov_low": next_leg}
    else:
        state = {"last_bar_identity": bar_id, "mode": _UP,
                 "prov_high": next_leg, "prov_low": None}
    return TransitionResult(state=state, events=preceding + (event,))

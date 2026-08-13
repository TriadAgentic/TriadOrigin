"""``displacement.closed_path.v1`` — F11 earliest-bar displacement search, RETAINED with full
VALID_BAR hardening + the §C.3 capability/envelope conversion
(TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F11; golden vector GV-010).

**Version discipline (§1.5): v1 RETAINED — the ONLY in-place repair in the set.** The semantic
law (four qualification conjuncts, earliest-wins, inclusive thresholds, exact cross-multiplied
rationals) is unchanged; this repair lands only the normative guards + the boundary law:

* **R-F11 DEFECT closed.** The old ``_bar_geometry`` checked only ``low <= high`` (Phase-0 added
  close-in-range but deliberately carved out open-in-range); a close above high or an open
  outside range could qualify ratios from invalid market data. Now the FULL §1.1 VALID_BAR
  predicate binds — for the origin bar ``o`` AND every candidate bar ``j`` in ``[o+1, o+H]`` —
  structurally at the E01 envelope (:func:`triad_origin.e01_interface.require_valid_bar` is the
  only lawful constructor of the consumed bar type) AND asserted locally (defense in depth,
  every arm: ``low <= min(open, close)``, ``max(open, close) <= high``, ``low <= high``, the
  three volume/count fields present and non-negative, every field an exact signed int64).
* **Failure behavior (§1.1, corrected from the Phase-0 raise).** An invalid bar emits NO atom;
  the machine records ``QUARANTINE_INVALID_BAR{bar_identity, reason}`` (the
  :meth:`~triad_origin.e01_interface.QuarantineInvalidBar.record` quarantine shape, augmented
  with F11 context) and the entire path is invalid: the search closes and the origin expires
  unqualified — the same class as a GAP, and the same precedence posture (§1.4: INVALIDATED
  beats every progression — validity is decided before ordering/qualification). A bar the E01
  boundary already refused never reaches :func:`evaluate`; the caller hands its typed
  :class:`~triad_origin.e01_interface.QuarantineInvalidBar` to :func:`evaluate_quarantined_bar`
  so the open F11 path is invalidated exactly as a gap would (the record is emitted only when a
  path is actually invalidated — otherwise the boundary refusal already told the caller).
* **§1.2 wire width (PAR-INT-01, RATIFY_WITH_THIS_REPAIR).** Every persisted/emitted integer
  (state ints, ``move_ticks``, ``d_ticks``, the ratio pairs, indices) is re-checked signed int64
  via :func:`triad_origin.exact.guard_int64` at the boundary; an overflow raises the typed
  ``QUARANTINE_OVERFLOW`` (never wrap, never saturate, never emit). Transient cross-multiplied
  comparison products stay lawfully unbounded.
* **§1.3 exact-rational storage.** The emitted ``body_ratio`` / ``close_loc`` pairs — both named
  verbatim in §1.3's stored-ratio list — are REDUCED fractions via
  :func:`triad_origin.exact.rational` (``den > 0``, ``gcd(|num|, den) = 1``); every ratio
  COMPARISON stays exact-integer cross-multiplication (never a float, never a division — the
  AST test proves no division operator exists in this module).

**Entrypoint (spec §C.3).** ``evaluate(caps, env, state, *, role, bar_index,
atr14_before_origin_ticks=None)`` where ``caps`` is a mapping ``parameter_id ->
triad_origin.bindings.VerifiedCapability`` covering EXACTLY the four F11 parameters (each entry
exact-type checked; ``formula_id`` must equal ``F11`` and ``parameter_id`` must equal its key —
a hand-built mapping/int/str raises a typed boundary rejection BEFORE any state transition) and
``env`` is exactly an :class:`triad_origin.e01_interface.ValidatedBar` (produced ONLY by
``require_valid_bar``; a raw mapping raises the §1.1 quarantine). The raw-parameter surface and
the old raw ORIGIN/BAR envelope machine are DELETED (§C.3). Replay and live consumption call
this ONE transition implementation; internals are a pure deterministic machine (no clock, no
I/O, no float).

* ``role = "ORIGIN"`` opens a fresh search: ``env`` IS the origin bar ``o`` (so VALID_BAR binds
  on the origin exactly as the corrected law requires), ``bar_index`` is its index, and
  ``atr14_before_origin_ticks`` is the injected causal F02 dependency (``None`` = warm-up/gap →
  the named abstention ``F11_NO_ATR``, no search opens, no shortened fallback).
  ``D_ticks = max(5, ceil(3*ATR/2))`` (PAR-158) is computed ONCE at origin time. A later ORIGIN
  always supersedes a still-open search (a new origin is new information).
* ``role = "BAR"`` walks candidate bar ``j`` (``env``) at ``bar_index``, strictly in order:
  an index behind the expected one raises (the F04-mirror ordering law); an index ahead of it is
  a GAP — named abstention ``F11_GAP_IN_SEARCH_WINDOW``, the search closes and never crosses the
  gap. A ``BAR`` while no search is open is a structurally harmless no-op.

The four bound parameters (BINDINGS: no new rows — the existing declared expressions):

* ``PAR-046`` body fraction ``beta`` — declared byte-string ``13/20``;
* ``PAR-157`` horizon ``H`` — declared byte-string ``3`` (finalized bars after origin; the
  ``H``-th later bar is included, the ``(H+1)``-th excluded);
* ``PAR-158`` minimum move — declared byte-string ``max(5,ceil(ATR14_before_origin*3/2))``;
* ``PAR-159`` close location ``lambda`` — declared byte-string ``4/5``.

Each capability's ``value`` must be the EXACT declared byte-string (any other value is a hidden
experiment and fails closed). All four registry rows (FPB-0021/0065/0066/0067) are BLOCKED
pending ratification, so no F11 capability can be minted from the repository registry today —
``require_bundle`` refuses ``BLOCKED_BINDING_INCOMPLETE:F11`` (the GV-010 boundary posture
``BLOCKED_UNTIL_PAR-158_RATIFIED``); a caller with no authenticated capability meets the named
refusal ``BLOCKED_ON_RATIFY(<parameter_id>)``. KNOWN TRANSPORT INTERLOCK (the PAR-036
precedent, pinned by test): the declared PAR-158 byte-string contains ``*``, which the
B01C-BIND-04 wildcard-sentinel law refuses inside an ACTIVE row's resolved fields — the
ratification train must additionally land a loader-acceptable declared-value transport.

Qualification per candidate bar ``j`` (R-F11 CORRECTED LAW, formula unchanged)::

    move_j = C_j - O_o                       (signed; O_o is the ORIGIN bar's own open)
    body_ratio_j = |C_j - O_j| / max(1, H_j - L_j)   >= 13/20   (cross-multiplied)
    close_loc_j  = (C_j - L_j) / max(1, H_j - L_j)   >= 4/5     (bull; cross-multiplied)
    bull:  move_j >= D_ticks AND C_j > O_j AND body AND close_loc
    bear:  move_j <= -D_ticks AND C_j < O_j AND body AND (H_j - C_j)*5 >= range*4

``D_ticks >= 5 > 0`` makes the two directions mutually exclusive. The EARLIEST qualifying ``j``
wins and the search stops there; no qualifying ``j`` within ``H`` → named abstention
``F11_NO_QUALIFYING_BAR`` and the origin expires. On qualification exactly one
``DISPLACEMENT_QUALIFIED`` event is emitted (GV-010: ``ATR14_before_origin = 10`` gives
``D_ticks = 15``; a move of ``14`` fails, ``15`` passes — equality passes, PAR-009).
"""

from __future__ import annotations

from .. import bindings
from ..e01_interface import QuarantineInvalidBar, ValidatedBar
from ..exact import guard_int64, rational
from ..transition import TransitionResult
from . import common

FORMULA_F11 = "F11"
SEMANTIC_VERSION = "displacement.closed_path.v1"

# The authenticated-capability surface: F11 consumes exactly FOUR bound parameters.
PARAMETER_BODY_FRACTION = "PAR-046"    # registry row FPB-0021 (BLOCKED until ratified)
PARAMETER_HORIZON = "PAR-157"          # registry row FPB-0065 (BLOCKED until ratified)
PARAMETER_MIN_MOVE = "PAR-158"         # registry row FPB-0066 (BLOCKED until ratified)
PARAMETER_CLOSE_LOCATION = "PAR-159"   # registry row FPB-0067 (BLOCKED until ratified)
REQUIRED_PARAMETERS = (
    PARAMETER_BODY_FRACTION, PARAMETER_HORIZON, PARAMETER_MIN_MOVE, PARAMETER_CLOSE_LOCATION)

# PAR-157's declared byte-string and its ONE executable instantiation. The declared-string gate
# admits only the exact byte-string — the integer is looked up, never parsed from foreign text.
DECLARED_DISPLACEMENT_HORIZON = "3"
_DECLARED_HORIZON_BARS = {DECLARED_DISPLACEMENT_HORIZON: 3}

DISPLACEMENT_QUALIFIED = "DISPLACEMENT_QUALIFIED"

ROLE_ORIGIN = "ORIGIN"
ROLE_BAR = "BAR"
_ROLES = (ROLE_ORIGIN, ROLE_BAR)

# Named event vocabulary (UPPER_SNAKE per common.abstention law) — unchanged from pre-repair.
NO_ATR = "F11_NO_ATR"
GAP_IN_SEARCH_WINDOW = "F11_GAP_IN_SEARCH_WINDOW"
NO_QUALIFYING_BAR = "F11_NO_QUALIFYING_BAR"

_STATE_KEYS = ("last_input_identity", "search")
_SEARCH_KEYS = ("origin_bar_identity", "origin_bar_index", "origin_open_ticks",
                "d_ticks", "next_bar_index", "examined")


class BlockedOnRatify(RuntimeError):
    """The named refusal ``BLOCKED_ON_RATIFY(<parameter_id>)`` (R-F11 BINDINGS posture).

    Raised when evaluation is attempted without an authenticated ``VerifiedCapability`` for a
    required F11 parameter. The mechanism exists; activation is ONLY via authenticated binding —
    no declared value is ever hardcoded as active (spec §0 rule 1).
    """

    def __init__(self, parameter_id: str) -> None:
        super().__init__(f"BLOCKED_ON_RATIFY({parameter_id})")
        self.parameter_id = parameter_id


# ---------------------------------------------------------------------------------------------
# Boundary law (spec §C.3): authenticated capabilities + E01-validated bar, nothing else
# ---------------------------------------------------------------------------------------------

def _require_caps(caps: object) -> tuple:
    """Admit the capability mapping; return ``(horizon_bars, body_num, body_den, close_num,
    close_den)``, else a typed refusal (all BEFORE any state transition)."""
    if not isinstance(caps, dict):
        raise bindings.CapabilityForgeryError(
            "F11 caps must be a mapping parameter_id -> VerifiedCapability; "
            f"got {type(caps).__name__}")
    unknown = [key for key in caps if key not in REQUIRED_PARAMETERS]
    if unknown:
        raise bindings.CapabilityForgeryError(
            f"F11 admits only the parameters {REQUIRED_PARAMETERS}; unknown key {unknown[0]!r}")
    values: dict = {}
    for parameter_id in REQUIRED_PARAMETERS:
        if parameter_id not in caps:
            # The R-F11 named refusal: no authenticated binding, no machine.
            raise BlockedOnRatify(parameter_id)
        cap = caps[parameter_id]
        if type(cap) is not bindings.VerifiedCapability:
            raise bindings.CapabilityForgeryError(
                "F11 parameters require a VerifiedCapability produced by require_bundle; "
                f"got {type(cap).__name__} for {parameter_id!r}")
        if cap.formula_id != FORMULA_F11:
            raise bindings.CapabilityForgeryError(
                f"capability formula_id {cap.formula_id!r} is not {FORMULA_F11!r}")
        if cap.parameter_id != parameter_id:
            raise bindings.CapabilityForgeryError(
                f"capability parameter_id {cap.parameter_id!r} does not equal its mapping key "
                f"{parameter_id!r}")
        values[parameter_id] = cap.value
    # Anti-hidden-experiment gate: each value must be the EXACT declared byte-string.
    if values[PARAMETER_MIN_MOVE] != common.DECLARED_DISPLACEMENT_MIN_MOVE:
        raise common.StructureLawError(
            f"F11 admits only the declared PAR-158 rule "
            f"{common.DECLARED_DISPLACEMENT_MIN_MOVE!r}, got {values[PARAMETER_MIN_MOVE]!r}")
    if values[PARAMETER_BODY_FRACTION] != common.DECLARED_DISPLACEMENT_BODY_FRACTION:
        raise common.StructureLawError(
            f"F11 admits only the declared PAR-046 rule "
            f"{common.DECLARED_DISPLACEMENT_BODY_FRACTION!r}, "
            f"got {values[PARAMETER_BODY_FRACTION]!r}")
    if values[PARAMETER_CLOSE_LOCATION] != common.DECLARED_DISPLACEMENT_CLOSE_LOCATION:
        raise common.StructureLawError(
            f"F11 admits only the declared PAR-159 rule "
            f"{common.DECLARED_DISPLACEMENT_CLOSE_LOCATION!r}, "
            f"got {values[PARAMETER_CLOSE_LOCATION]!r}")
    horizon_bars = _DECLARED_HORIZON_BARS.get(values[PARAMETER_HORIZON])
    if horizon_bars is None:
        raise common.StructureLawError(
            f"F11 admits only the declared PAR-157 horizon "
            f"{DECLARED_DISPLACEMENT_HORIZON!r}, got {values[PARAMETER_HORIZON]!r}")
    body_num, body_den = common.declared_fraction(values[PARAMETER_BODY_FRACTION])
    close_num, close_den = common.declared_fraction(values[PARAMETER_CLOSE_LOCATION])
    return horizon_bars, body_num, body_den, close_num, close_den


def _require_env(env: object) -> ValidatedBar:
    """Exactly an e01 ValidatedBar — a raw mapping/subclass never crosses the boundary (§1.1)."""
    if type(env) is not ValidatedBar:
        raise QuarantineInvalidBar(
            bar_identity=None,
            reason="F11 env must be an e01_interface.ValidatedBar produced by "
                   f"require_valid_bar; got {type(env).__name__}")
    return env


def _require_search(record: object) -> dict:
    if not isinstance(record, dict) or sorted(record) != sorted(_SEARCH_KEYS):
        raise common.StructureLawError(f"F11 state search must carry exactly {_SEARCH_KEYS}")
    origin_identity = record["origin_bar_identity"]
    if not isinstance(origin_identity, str) or not origin_identity:
        raise common.StructureLawError(
            "F11 state origin_bar_identity must be a non-empty str")
    out = {"origin_bar_identity": origin_identity}
    for name in ("origin_bar_index", "origin_open_ticks", "d_ticks", "next_bar_index",
                 "examined"):
        out[name] = guard_int64(record[name], formula_id=FORMULA_F11, field=name)
    if out["d_ticks"] <= 0:
        raise common.StructureLawError("F11 state d_ticks must be positive")
    if out["examined"] < 0:
        raise common.StructureLawError("F11 state examined must be >= 0")
    if out["next_bar_index"] <= out["origin_bar_index"]:
        raise common.StructureLawError(
            "F11 state next_bar_index must be after origin_bar_index")
    return out


def _require_state(state: object) -> dict:
    if not isinstance(state, dict) or sorted(state) != sorted(_STATE_KEYS):
        raise common.StructureLawError(f"F11 state must carry exactly the keys {_STATE_KEYS}")
    last = state["last_input_identity"]
    if last is not None and (not isinstance(last, str) or not last):
        raise common.StructureLawError(
            "F11 state last_input_identity must be None or a non-empty str")
    search = state["search"]
    if search is not None:
        search = _require_search(search)
    return {"last_input_identity": last, "search": search}


# ---------------------------------------------------------------------------------------------
# §1.1 VALID_BAR asserted locally (defense in depth) — EVERY arm, never a low<=high-only check
# ---------------------------------------------------------------------------------------------

def _int64_or_reason(value: object, name: str) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{name} must be an exact int, got {type(value).__name__}"
    if value < -(2 ** 63) or value > 2 ** 63 - 1:
        return f"{name} is outside the signed int64 domain (PAR-INT-01)"
    return None


def _valid_bar_violation(bar: ValidatedBar) -> str | None:
    """The full §1.1 VALID_BAR predicate re-asserted on the (type-checked) envelope object.

    The lawful constructor (``require_valid_bar``) already enforced every arm; this closes the
    forged-field hole (dataclass construction is unrestricted by design), so even a hand-built
    envelope object can never fabricate a displacement from invalid market data.
    """
    if not isinstance(bar.bar_identity, str) or not bar.bar_identity:
        return "bar_identity must be a non-empty str"
    if not isinstance(bar.metadata_revision, str) or not bar.metadata_revision:
        return "metadata_revision must be a non-empty str"
    for name, value in (
            ("open_ticks", bar.open_ticks), ("high_ticks", bar.high_ticks),
            ("low_ticks", bar.low_ticks), ("close_ticks", bar.close_ticks),
            ("base_volume", bar.base_volume), ("quote_volume", bar.quote_volume),
            ("trade_count", bar.trade_count)):
        reason = _int64_or_reason(value, name)
        if reason is not None:
            return reason
    if not bar.low_ticks <= min(bar.open_ticks, bar.close_ticks):
        return "low_ticks must satisfy low <= min(open, close)"
    if not max(bar.open_ticks, bar.close_ticks) <= bar.high_ticks:
        return "high_ticks must satisfy max(open, close) <= high"
    if not bar.low_ticks <= bar.high_ticks:  # implied by the two arms above; assert anyway
        return "low_ticks must satisfy low <= high"
    if bar.base_volume < 0 or bar.quote_volume < 0 or bar.trade_count < 0:
        return "base_volume, quote_volume and trade_count must each be >= 0"
    return None


def _quarantine_event(quarantine: QuarantineInvalidBar, *, refs: dict) -> dict:
    """The recorded ``QUARANTINE_INVALID_BAR{bar_identity, reason}`` fact, with F11 context.

    Deliberate shape choice (R-F11): the e01 quarantine ``record()`` shape IS the record —
    ``event_kind: QUARANTINE`` with the §1.1-required ``bar_identity`` + ``reason`` — augmented
    with the formula identity and sorted refs (the ``common.abstention`` refs convention).
    """
    event = quarantine.record()
    event["formula"] = FORMULA_F11
    event["semantic_version"] = SEMANTIC_VERSION
    event["refs"] = dict(sorted(refs.items()))
    return event


def _path_invalid_refs(search: dict | None, quarantined_bar_index: object) -> dict:
    refs: dict = {"quarantined_bar_index": quarantined_bar_index}
    if search is not None:
        refs["origin_bar_identity"] = search["origin_bar_identity"]
        refs["origin_bar_index"] = search["origin_bar_index"]
    return refs


# ---------------------------------------------------------------------------------------------
# The pure machine
# ---------------------------------------------------------------------------------------------

def initial_state() -> dict:
    """The cold state: no input consumed, no search open."""
    return {"last_input_identity": None, "search": None}


def evaluate(caps: dict, env: ValidatedBar, state: dict, *, role: str, bar_index: int,
             atr14_before_origin_ticks: int | None = None) -> TransitionResult:
    """The ONE ``displacement.closed_path.v1`` transition — identical for live and replay.

    Boundary order (all BEFORE any state transition): capability law -> E01 envelope law ->
    role/index law -> state-shape law -> §1.1 VALID_BAR (defense in depth) -> the semantic
    machine. ``bar_index`` is the finalized bar's index (the strict-order/gap axis the envelope
    type does not carry); ``atr14_before_origin_ticks`` is the injected causal F02 dependency,
    meaningful ONLY at ``role="ORIGIN"`` (``None`` = warm-up/gap -> ``F11_NO_ATR``).
    """
    horizon, body_num, body_den, close_num, close_den = _require_caps(caps)
    bar = _require_env(env)
    if role not in _ROLES:
        raise common.StructureLawError(
            f"F11 role must be one of {_ROLES}, got {role!r}")
    if role == ROLE_BAR and atr14_before_origin_ticks is not None:
        raise common.StructureLawError(
            "F11 atr14_before_origin_ticks is an ORIGIN-only injected dependency; "
            "a BAR call must not carry one")
    index = guard_int64(bar_index, formula_id=FORMULA_F11, field="bar_index")
    st = _require_state(state)

    bar_identity = (
        bar.bar_identity if isinstance(bar.bar_identity, str) and bar.bar_identity else None)
    identity = None if bar_identity is None else f"{role}:{bar_identity}"
    if identity is not None and identity == st["last_input_identity"]:
        return TransitionResult(state=st)  # exact retransmission: idempotent no-op
    next_last = identity if identity is not None else st["last_input_identity"]

    # §1.1 first (the §1.4 posture: INVALIDATED beats ordering and every progression): an
    # invalid bar emits no atom, records the quarantine, and invalidates the whole path.
    violation = _valid_bar_violation(bar)
    if violation is not None:
        quarantine = QuarantineInvalidBar(bar_identity=bar_identity, reason=violation)
        return TransitionResult(
            state={"last_input_identity": next_last, "search": None},
            events=(_quarantine_event(
                quarantine, refs=_path_invalid_refs(st["search"], index)),))

    if role == ROLE_ORIGIN:
        return _origin(next_last, bar, index, atr14_before_origin_ticks)
    return _bar(st, next_last, bar, index, horizon,
                body_num, body_den, close_num, close_den)


def evaluate_quarantined_bar(caps: dict, quarantine: QuarantineInvalidBar, state: dict, *,
                             bar_index: int | None = None) -> TransitionResult:
    """Invalidate the open F11 path for a bar the E01 boundary refused (§1.1 failure law).

    ``require_valid_bar`` raises BEFORE an invalid bar can become a ``ValidatedBar``, so the
    refused bar can never reach :func:`evaluate`; the caller hands the typed
    :class:`~triad_origin.e01_interface.QuarantineInvalidBar` here instead. With a search open,
    the quarantine record is emitted (with F11 context) and the search closes — the origin
    expires unqualified, exactly as a GAP. With no search open this is a structurally harmless
    no-op (the boundary refusal already surfaced the quarantine to the caller). Fail-closed on
    the window axis: ANY quarantined bar reported while a search is open invalidates the path —
    the machine never risks searching across an unverifiable slot. ``bar_index`` is optional
    (a malformed bar may not even carry a readable index); when supplied it is int64-guarded
    and echoed in the record refs.
    """
    _require_caps(caps)
    if type(quarantine) is not QuarantineInvalidBar:
        raise QuarantineInvalidBar(
            bar_identity=None,
            reason="F11 quarantine input must be an e01_interface.QuarantineInvalidBar "
                   f"raised by require_valid_bar; got {type(quarantine).__name__}")
    st = _require_state(state)
    index = None
    if bar_index is not None:
        index = guard_int64(bar_index, formula_id=FORMULA_F11, field="bar_index")
    if st["search"] is None:
        return TransitionResult(state=st)
    return TransitionResult(
        state={"last_input_identity": st["last_input_identity"], "search": None},
        events=(_quarantine_event(
            quarantine, refs=_path_invalid_refs(st["search"], index)),))


def _origin(next_last: str | None, bar: ValidatedBar, origin_bar_index: int,
            atr: int | None) -> TransitionResult:
    """Open a fresh search from the (VALID) origin bar; a new origin always supersedes."""
    if atr is None:
        return TransitionResult(
            state={"last_input_identity": next_last, "search": None},
            events=(common.abstention(
                NO_ATR, formula=FORMULA_F11,
                detail="causal ATR14_before_origin is null (warm-up/gap); no displacement "
                       "search opens for this origin",
                refs={"bar_identity": bar.bar_identity,
                      "origin_bar_index": origin_bar_index,
                      "semantic_version": SEMANTIC_VERSION}),))
    d_ticks = guard_int64(
        common.evaluate_displacement_min_move(
            guard_int64(atr, formula_id=FORMULA_F11, field="atr14_before_origin_ticks")),
        formula_id=FORMULA_F11, field="d_ticks")
    search = {
        "origin_bar_identity": bar.bar_identity,
        "origin_bar_index": origin_bar_index,
        "origin_open_ticks": guard_int64(
            bar.open_ticks, formula_id=FORMULA_F11, field="origin_open_ticks"),
        "d_ticks": d_ticks,
        "next_bar_index": guard_int64(
            origin_bar_index + 1, formula_id=FORMULA_F11, field="next_bar_index"),
        "examined": 0,
    }
    return TransitionResult(state={"last_input_identity": next_last, "search": search})


def _bar(st: dict, next_last: str | None, bar: ValidatedBar, bar_index: int, horizon: int,
         body_num: int, body_den: int, close_num: int, close_den: int) -> TransitionResult:
    search = st["search"]
    if search is None:
        # No open search (pre-origin, post-qualification, post-gap, post-quarantine, NO_ATR):
        # a structurally harmless no-op.
        return TransitionResult(state={"last_input_identity": next_last, "search": None})
    expected = search["next_bar_index"]
    if bar_index < expected:
        raise common.StructureLawError(
            f"F11 bar_index must not precede the expected search index: "
            f"got {bar_index}, expected {expected}")
    if bar_index > expected:
        return TransitionResult(
            state={"last_input_identity": next_last, "search": None},
            events=(common.abstention(
                GAP_IN_SEARCH_WINDOW, formula=FORMULA_F11,
                detail="a finalized bar was skipped inside the search window; the search "
                       "never crosses a gap and closes without a qualifying result",
                refs={"bar_identity": bar.bar_identity,
                      "expected_bar_index": expected, "got_bar_index": bar_index,
                      "semantic_version": SEMANTIC_VERSION}),))

    open_ticks, close_ticks = bar.open_ticks, bar.close_ticks
    high_ticks, low_ticks = bar.high_ticks, bar.low_ticks
    move_ticks = close_ticks - search["origin_open_ticks"]  # transient: may exceed int64 here
    d_ticks = search["d_ticks"]
    range_ticks = max(1, high_ticks - low_ticks)
    body_ok = abs(close_ticks - open_ticks) * body_den >= range_ticks * body_num
    long_close_loc_ok = (close_ticks - low_ticks) * close_den >= range_ticks * close_num
    short_close_loc_ok = (high_ticks - close_ticks) * close_den >= range_ticks * close_num
    qualifies_long = (
        move_ticks >= d_ticks and close_ticks > open_ticks and body_ok
        and long_close_loc_ok)
    qualifies_short = (
        move_ticks <= -d_ticks and close_ticks < open_ticks and body_ok
        and short_close_loc_ok)

    if qualifies_long or qualifies_short:
        direction = common.LONG if qualifies_long else common.SHORT
        close_loc_raw = (
            (close_ticks - low_ticks) if qualifies_long else (high_ticks - close_ticks))
        # §1.3: the STORED ratios are reduced fractions; §1.2: every emitted integer is
        # re-checked signed int64 at this boundary (overflow -> typed QUARANTINE_OVERFLOW).
        body_ratio = rational(abs(close_ticks - open_ticks), range_ticks)
        close_loc = rational(close_loc_raw, range_ticks)
        event = {
            "event_kind": DISPLACEMENT_QUALIFIED,
            "formula": FORMULA_F11,
            "semantic_version": SEMANTIC_VERSION,
            "direction": direction,
            "origin_bar_index": search["origin_bar_index"],
            "qualifying_bar_index": bar_index,
            "move_ticks": guard_int64(move_ticks, formula_id=FORMULA_F11, field="move_ticks"),
            "d_ticks": d_ticks,
            "body_ratio_numerator": guard_int64(
                body_ratio[0], formula_id=FORMULA_F11, field="body_ratio_numerator"),
            "body_ratio_denominator": guard_int64(
                body_ratio[1], formula_id=FORMULA_F11, field="body_ratio_denominator"),
            "close_loc_numerator": guard_int64(
                close_loc[0], formula_id=FORMULA_F11, field="close_loc_numerator"),
            "close_loc_denominator": guard_int64(
                close_loc[1], formula_id=FORMULA_F11, field="close_loc_denominator"),
            "origin_bar_identity": search["origin_bar_identity"],
            "confirmed_by_bar_identity": bar.bar_identity,
        }
        return TransitionResult(
            state={"last_input_identity": next_last, "search": None}, events=(event,))

    examined = search["examined"] + 1
    if examined >= horizon:
        return TransitionResult(
            state={"last_input_identity": next_last, "search": None},
            events=(common.abstention(
                NO_QUALIFYING_BAR, formula=FORMULA_F11,
                detail="no bar in the search window satisfied all four qualification "
                       "conjuncts in either direction",
                refs={"bar_identity": bar.bar_identity,
                      "origin_bar_index": search["origin_bar_index"],
                      "horizon": horizon,
                      "semantic_version": SEMANTIC_VERSION}),))
    next_search = dict(search)
    next_search["examined"] = examined
    next_search["next_bar_index"] = guard_int64(
        expected + 1, formula_id=FORMULA_F11, field="next_bar_index")
    return TransitionResult(state={"last_input_identity": next_last, "search": next_search})

"""``level_excursion_reclaim.closed.v2`` — F13 frozen-level excursion and timed reclaim (R-F13).

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §R-F13 (CRITICAL, FIX FIRST). Supersedes
``level_excursion_reclaim.closed.v1`` (:mod:`triad_origin.structures.excursion_reclaim_registry`,
retired with the §1.5 withdrawal banner; its bytes are preserved and its rows keep their version
tag forever — never-blend across formula versions). The four confirmed v1 defects this module
repairs:

1. **Reversed directions** — v1's LONG machine triggered on the SHORT geometry and vice versa.
   v2 implements the corrected law verbatim (both sides written out below); the T10 direction
   trap makes the reversal unrecoverable.
2. **Horizon off-by-one** — v1's per-observation ordinal ceiling let an ordinal-3 event satisfy a
   horizon of two. v2 uses the ratified tau total-window law (13b).
3. **Duplicate or non-consecutive ordinals satisfying the hold** — v2's hold chain demands
   EXACTLY consecutive ordinals; a duplicate is an idempotent no-op and a skipped finalized
   ordinal is a data-continuity break (``INVALIDATED{SEQUENCE_GAP}`` — there is no legitimate
   skipped finalized ordinal).
4. **Excursion extreme not retained** — v2 retains ``extreme`` in state, updates it per the
   normative within-bar order, and emits it (with ``excursion_depth_ticks``) on the CONFIRMED
   atom — downstream stop logic (F18 invalidation reference) consumes them.

CORRECTED LAW (R-F13, complete, both sides)::

    LONG (support sweep / spring):
      EXCURSION trigger .... L_t (bar low)  <= L_px - e
      extreme ............. E = min over excursion-phase bar lows (retained in state)
      RECLAIM trigger ..... C_t (bar close) >= L_px + r
      CONFIRM ............. n CONSECUTIVE finalized closes >= L_px + r

    SHORT (resistance sweep), exact mirror:
      EXCURSION trigger .... H_t >= L_px + e
      extreme ............. E = max over excursion-phase bar highs
      RECLAIM trigger ..... C_t <= L_px - r
      CONFIRM ............. n CONSECUTIVE finalized closes <= L_px - r

Ratified conventions (``RATIFY_WITH_THIS_REPAIR`` — owner signature on the repair PR):

* **13a** ``EXC_HOLD_INCLUDES_TRIGGER = TRUE`` — the first qualifying reclaim close IS hold #1;
  CONFIRMED lands on the n-th consecutive qualifying close (with ``n == 1`` the trigger close
  itself confirms).
* **13b** ``EXC_TAU_SCOPE = TOTAL_WINDOW_INCLUSIVE`` — tau bounds ordinals from the excursion
  trigger bar to the CONFIRMING bar inclusive: ``(t_confirm - t_excursion) <= tau``. Exceeding
  tau at any phase → EXPIRED.
* ``EXC_GAP_RULE = INVALIDATE`` — a declared GAP bar (and a §1.1 quarantined bar, which behaves
  exactly as a GAP) invalidates every non-terminal level lifecycle; a skipped finalized ordinal
  inside an open window is ``INVALIDATED{SEQUENCE_GAP}``.

EXTREME DEFINITION — the CORRECTED LAW ("``extreme = E = min over excursion-phase bar lows``")
governs, and this module implements it EXACTLY: the extreme deepens on every EXCURSION-phase bar
(incl. an expiring bar, which deepens first per the normative within-bar order, and a
RECLAIM_PENDING bar that RESETS back to EXCURSION because its close failed the reclaim), and a
qualifying RECLAIM_PENDING HOLD bar does NOT deepen (it is a reclaim close, not an excursion-phase
bar). This is pinned by ``test_excursion_reclaim_v2`` (``test_hold_bars_do_not_deepen_the_extreme``,
``test_h10_the_expiring_bar_still_deepens_the_extreme_first``, T9 ``via reset path``).

ERRATUM ERR-02 (owner decision D-21 — TRIAD-ORIGIN-V7-ERRATA-2026-08-13) is a **PROPOSED semantic
change**, NOT adopted here: it would redefine ``extreme`` to accrue over EVERY non-terminal bar
from ``t_exc`` to ``t_confirm`` inclusive (a step ``(0.5) extreme := min(extreme, L_t)`` at the top
of RECLAIM_PENDING, so a qualifying hold bar's intrabar low would also deepen the stop reference).
That reading CONTRADICTS the vendored CORRECTED LAW's explicit "min over **excursion-phase** bar
lows", flips ``test_hold_bars_do_not_deepen_the_extreme``, and changes the emitted
``extreme_ticks``/``excursion_depth_ticks`` consumed by F18 stop logic — so it is a formula-byte
change reserved for the owner's signature (D-21, alongside a prior spec-amendment PR per the
authority order "a semantic change updates the authoritative spec/control artifact in a prior
PR"). An agent does not silently pick between two conflicting spec statements; it is recorded in
``docs/plan/DECISIONS-REQUIRED.md`` (D-21) and left refusing-in-place — the current behaviour is
the faithful transcription of the law as written.

Same-event multi-transition law (§1.4, instantiated for F13): transitions map onto the global
precedence classes via :data:`TRANSITION_CLASSES` and same-bar coincidences in the EXCURSION
state are resolved by :func:`triad_origin.exact.dominant_transition`
(INVALIDATED > EXPIRED > terminal > progression) — a bar that is both beyond tau and reclaiming
EXPIRES, and the normative within-bar order still deepens the extreme first (a bar may both
deepen the extreme and expire/trigger). ONE declared carve-out, pseudocode-normative (§0.1 —
pseudocode wins): in RECLAIM_PENDING the numbered rule order evaluates the tau bound (rule 1)
BEFORE the missing-ordinal break (rule 4), so a skip that arrives beyond tau reads EXPIRED. In
the EXCURSION state the spec declares no gap rule, so the global order governs and the skip
reads INVALIDATED before any tau/extreme work.

C.3 entrypoint law: :func:`evaluate` consumes an authenticated capability map
(``parameter_id -> triad_origin.bindings.VerifiedCapability``, exact type per entry, formula
``F13``) and an E01 envelope (:class:`triad_origin.e01_interface.ValidatedBar`, exact type). A
raw dict or hand-built object in either seat raises a typed rejection BEFORE any state
transition. The per-bar stream coordinates (``ordinal`` — the per-(instrument,timeframe)
finalized-bar index, ``bucket_start_us`` — the bar's bucket start for the §1.4 availability law)
are injected keyword-only exact ints: the three fixed ``ValidatedInput`` shapes do not carry
them, and this module never reads a clock. Level facts (registration / defining revision) and
declared GAP / §1.1-quarantine facts are E01/F03-owned intake consumed through the pure
:func:`register_level` / :func:`revise_level` / :func:`note_gap` faces — replay and live drive
the SAME functions in recorded order.

Parameter bindings (existing rows, values still ``PROPOSED_MUST_RATIFY`` — the registry rows are
``BLOCKED_BINDING_V2_MIGRATION``, so a production sealed bundle refuses F13 with the typed
``BLOCKED_BINDING_INCOMPLETE{F13}`` before any capability exists): ``PAR-048`` e (ticks) ·
``PAR-164`` r (ticks) · ``PAR-049`` tau (bars, 13b total-window scope) · ``PAR-165`` n
(consecutive closes). This module's mechanism consumes each declared value as an EXACT
non-negative integer (n additionally >= 1 — under 13a the trigger close is hold #1, so a confirm
requires at least one hold); the v1 ATR-rule byte-strings are not ratified v2 tick values and
refuse by name (``F13_BINDING_VALUE_NOT_INTEGER``) — never evaluated, never defaulted.

GV-011: the R-F13 vector table (T1–T14) is the successor content of golden vector GV-011
(RC3-GVOP-003 REPLACE row); T3 is the canonical confirm walk.

Everything here is a pure function of its arguments: no clock, no I/O, no environment read, no
randomness, no float. Persisted integers are int64-guarded (§1.2); overflow is
``QUARANTINE_OVERFLOW{formula_id, field, value_digest}`` — the atom is never emitted and the
level lifecycle invalidates (fail closed).
"""

from __future__ import annotations

import re

from .. import bindings
from ..canonical import canonical_json, sha256_hex
from ..e01_interface import ValidatedBar
from ..exact import (
    QuarantineOverflow,
    TransitionPrecedence,
    availability_allows,
    dominant_transition,
    guard_int64,
)
from ..transition import TransitionResult
from .common import LONG, SHORT, StructureLawError, require_direction, require_int

FORMULA_ID = "F13"
VERSION = "level_excursion_reclaim.closed.v2"

# --- parameter bindings (the caps map keys — registry parameter_id values) -----------------------
PARAM_EXCURSION_MIN = "PAR-048"       # e, ticks   (FPB-0023 EXCURSION_MIN)
PARAM_RECLAIM_TAU = "PAR-049"         # tau, bars  (FPB-0024 RECLAIM_HORIZON, 13b total window)
PARAM_RECLAIM_CLOSE_BUFFER = "PAR-164"  # r, ticks (FPB-0072 RECLAIM_CLOSE_BUFFER)
PARAM_RECLAIM_HOLD_BARS = "PAR-165"   # n          (FPB-0073 RECLAIM_HOLD_BARS)
REQUIRED_PARAMETER_IDS = (
    PARAM_EXCURSION_MIN,
    PARAM_RECLAIM_TAU,
    PARAM_RECLAIM_CLOSE_BUFFER,
    PARAM_RECLAIM_HOLD_BARS,
)

# --- ratified conventions (RATIFY_WITH_THIS_REPAIR — R-F13 13a/13b + the gap row) -----------------
EXC_HOLD_INCLUDES_TRIGGER = True
EXC_TAU_SCOPE = "TOTAL_WINDOW_INCLUSIVE"
EXC_GAP_RULE = "INVALIDATE"

# --- the closed phase vocabulary ------------------------------------------------------------------
ARMED = "ARMED"
EXCURSION = "EXCURSION"
RECLAIM_PENDING = "RECLAIM_PENDING"
CONFIRMED = "CONFIRMED"
EXPIRED = "EXPIRED"
INVALIDATED = "INVALIDATED"
CONSUMED = "CONSUMED"  # reserved downstream terminal — nothing in F13 itself reaches it
PHASES = (ARMED, EXCURSION, RECLAIM_PENDING, CONFIRMED, EXPIRED, INVALIDATED, CONSUMED)
TERMINAL_PHASES = (CONFIRMED, EXPIRED, INVALIDATED, CONSUMED)

# §1.4 precedence classes, instantiated for F13's transitions.
TRANSITION_CLASSES = {
    INVALIDATED: TransitionPrecedence.INVALIDATED,
    EXPIRED: TransitionPrecedence.EXPIRED,
    CONFIRMED: TransitionPrecedence.TERMINAL,
    EXCURSION: TransitionPrecedence.PROGRESSION,
    RECLAIM_PENDING: TransitionPrecedence.PROGRESSION,
}

# --- event kinds / reason codes -------------------------------------------------------------------
STATE_KIND = "EXCURSION_RECLAIM_STATE"
ATOM_KIND = "EXCURSION_RECLAIM_ATOM"

TAU_EXCEEDED = "TAU_EXCEEDED"
SEQUENCE_GAP = "SEQUENCE_GAP"
HOLD_RESET = "HOLD_RESET"
LEVEL_REVISED = "LEVEL_REVISED"
GAP_BAR = "GAP_BAR"
QUARANTINE_OVERFLOW_REASON = "QUARANTINE_OVERFLOW"

# Named refusal for an unratified/non-integer declared binding value (PROPOSED_MUST_RATIFY law:
# the mechanism consumes exact integer ticks/bars/counts; anything else refuses by name).
BINDING_VALUE_NOT_INTEGER = "F13_BINDING_VALUE_NOT_INTEGER"
STATE_VERSION_MISMATCH = "F13_STATE_VERSION_MISMATCH"

_NONNEG_INT_STR = r"0|[1-9][0-9]*"

_UPPER_SNAKE = r"[A-Z][A-Z0-9_]*"


class EnvelopeContractError(TypeError):
    """A non-E01 envelope was presented at the F13 v2 boundary (typed, fail-closed).

    Raised BEFORE any state transition: a raw dict, a duck-typed stand-in, or a subclass in the
    ``env`` seat never reaches the machine (§C.3 — ``ValidatedInput`` exact type only).
    """


# ==================================================================================================
# capability + envelope + coordinate boundaries (all BEFORE any state transition)
# ==================================================================================================


def _capability_int(cap: bindings.VerifiedCapability, *, minimum: int, name: str) -> int:
    """An exact integer declared value, else the named ``F13_BINDING_VALUE_NOT_INTEGER`` refusal.

    Admits an exact int (bool excluded) or a canonical non-negative decimal string (the registry
    wire carries declared values as strings). The v1 ATR-rule byte-strings are NOT ratified v2
    values — they refuse here by name, never evaluated, never defaulted. ``minimum`` is the
    mechanism's structural domain floor (never a proposed value): ticks/bars are non-negative
    magnitudes (a negative buffer would invert the written geometry) and 13a makes ``n >= 1``
    structural (the trigger close is hold #1).
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
            f"{BINDING_VALUE_NOT_INTEGER}: {cap.parameter_id} declared value {value!r} is not an "
            f"exact non-negative integer (PROPOSED_MUST_RATIFY — the unratified rule string is "
            f"refused, never evaluated)")
    guarded = guard_int64(result, formula_id=FORMULA_ID, field=cap.parameter_id)
    if guarded < minimum:
        raise StructureLawError(
            f"{BINDING_VALUE_NOT_INTEGER}: {cap.parameter_id}={guarded} violates the structural "
            f"domain floor {name} >= {minimum}")
    return guarded


def _resolved_parameters(caps: object) -> tuple:
    """Validate the capability map and resolve ``(e, r, tau, n, digest_source)``.

    Exact-type check per entry (``type(entry) is bindings.VerifiedCapability`` — a subclass, duck-typed
    stand-in, dict, or int is a typed :class:`~triad_origin.bindings.CapabilityForgeryError`
    BEFORE any state transition); every entry must be minted for THIS formula and keyed by its
    own ``parameter_id``; the key set is exactly :data:`REQUIRED_PARAMETER_IDS`.
    """
    if not isinstance(caps, dict):
        raise bindings.CapabilityForgeryError(
            f"F13 v2 requires a parameter_id -> bindings.VerifiedCapability map, got "
            f"{type(caps).__name__}")
    unknown = sorted(set(caps) - set(REQUIRED_PARAMETER_IDS))
    if unknown:
        raise bindings.CapabilityForgeryError(f"unexpected capability for F13 v2: {unknown[0]!r}")
    missing = [pid for pid in REQUIRED_PARAMETER_IDS if pid not in caps]
    if missing:
        raise bindings.CapabilityForgeryError(f"missing capability for F13 v2: {missing[0]!r}")
    for pid in REQUIRED_PARAMETER_IDS:
        entry = caps[pid]
        if type(entry) is not bindings.VerifiedCapability:
            raise bindings.CapabilityForgeryError(
                f"F13 v2 parameter {pid!r} requires a bindings.VerifiedCapability, got "
                f"{type(entry).__name__}")
        if entry.formula_id != FORMULA_ID:
            raise bindings.CapabilityForgeryError(
                f"capability for {pid!r} was minted for formula {entry.formula_id!r}, "
                f"not {FORMULA_ID}")
        if entry.parameter_id != pid:
            raise bindings.CapabilityForgeryError(
                f"capability keyed {pid!r} carries parameter_id {entry.parameter_id!r}")
    e = _capability_int(caps[PARAM_EXCURSION_MIN], minimum=0, name="e")
    r = _capability_int(caps[PARAM_RECLAIM_CLOSE_BUFFER], minimum=0, name="r")
    tau = _capability_int(caps[PARAM_RECLAIM_TAU], minimum=0, name="tau")
    n = _capability_int(caps[PARAM_RECLAIM_HOLD_BARS], minimum=1, name="n")
    digest_source = tuple(
        (pid, caps[pid].value, caps[pid].signed_root_digest) for pid in REQUIRED_PARAMETER_IDS)
    return e, r, tau, n, digest_source


def _parameter_digest(digest_source: tuple) -> str:
    """The atom-identity parameter digest: resolved ids/values bound to the signed bundle root."""
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
            f"F13 v2 consumes a triad_origin.e01_interface.ValidatedBar produced by "
            f"require_valid_bar; got {type(env).__name__}")
    return env


def _coordinate(value: object, name: str, *, minimum: int | None = None) -> int:
    """An injected stream coordinate: exact int, int64-guarded, optionally floored."""
    exact = require_int(value, name)
    guarded = guard_int64(exact, formula_id=FORMULA_ID, field=name)
    if minimum is not None and guarded < minimum:
        raise StructureLawError(f"{name} must be >= {minimum}, got {guarded}")
    return guarded


_ROW_KEYS = (
    "level_id", "side", "level_px_ticks", "availability_time_us", "level_source", "phase",
    "extreme_ticks", "t_exc", "hold", "t_last", "t_confirm", "last_seen_ordinal",
    "excursion_source", "hold_sources", "terminal_reason",
)
_ROW_OPTIONAL_INT_KEYS = ("extreme_ticks", "t_exc", "t_last", "t_confirm", "last_seen_ordinal")


def _checked_row(row: object, level_id: str) -> dict:
    """A level row re-validated on READ (no float / no junk on a semantic compare, ever).

    Checkpointed state may round-trip through storage between calls; every field this machine
    compares is re-proven an exact int64 (or honest ``None``) before any comparison runs.
    """
    if not isinstance(row, dict) or sorted(row) != sorted(_ROW_KEYS):
        raise StructureLawError(
            f"F13 v2 level row {level_id!r} must carry exactly the keys {sorted(_ROW_KEYS)}")
    if row["level_id"] != level_id:
        raise StructureLawError(
            f"F13 v2 level row keyed {level_id!r} carries level_id {row['level_id']!r}")
    require_direction(row["side"])
    if row["phase"] not in PHASES:
        raise StructureLawError(f"F13 v2 level row phase {row['phase']!r} is not in {PHASES}")
    guard_int64(require_int(row["level_px_ticks"], "level_px_ticks"),
                formula_id=FORMULA_ID, field="level_px_ticks")
    guard_int64(require_int(row["availability_time_us"], "availability_time_us"),
                formula_id=FORMULA_ID, field="availability_time_us")
    guard_int64(require_int(row["hold"], "hold"), formula_id=FORMULA_ID, field="hold")
    for name in _ROW_OPTIONAL_INT_KEYS:
        if row[name] is not None:
            guard_int64(require_int(row[name], name), formula_id=FORMULA_ID, field=name)
    if not isinstance(row["level_source"], str) or not row["level_source"]:
        raise StructureLawError("F13 v2 level row level_source must be a non-empty str")
    if not isinstance(row["hold_sources"], list):
        raise StructureLawError("F13 v2 level row hold_sources must be a list")
    return row


def _require_state(state: object) -> dict:
    """The v2 machine state — version-checked so v1 rows can never blend into v2 (§1.5)."""
    if not isinstance(state, dict):
        raise StructureLawError("F13 v2 state must be an object")
    if state.get("formula_version") != VERSION:
        raise StructureLawError(
            f"{STATE_VERSION_MISMATCH}: state carries {state.get('formula_version')!r}, "
            f"this machine is {VERSION!r} (never-blend across formula versions)")
    levels = state.get("levels")
    if not isinstance(levels, dict):
        raise StructureLawError("F13 v2 state.levels must be an object")
    return levels


# ==================================================================================================
# the pure machine
# ==================================================================================================


def initial_state() -> dict:
    """The cold state: no tracked levels. The version stamp is the never-blend marker."""
    return {"formula_version": VERSION, "levels": {}}


_REGISTRATION_FIELDS = ("side", "level_px_ticks", "availability_time_us", "level_source")


def register_level(
    state: dict,
    *,
    level_id: str,
    side: str,
    level_px_ticks: int,
    availability_time_us: int,
    source_event_id: str,
) -> TransitionResult:
    """Track a frozen typed level (ARMED). Pure: returns the new state; emits nothing.

    The level is E01/F03-owned fact intake, frozen forever: ``L_px`` never rolls — a moving
    reference is INVALIDATED by :func:`revise_level` only. Re-registration with byte-identical
    facts is an idempotent no-op; re-registration with different facts is refused (a frozen
    level's defining facts never change in place).
    """
    levels = _require_state(state)
    if not isinstance(level_id, str) or not level_id:
        raise StructureLawError("level_id must be a non-empty str")
    if not isinstance(source_event_id, str) or not source_event_id:
        raise StructureLawError("source_event_id must be a non-empty str")
    row = {
        "level_id": level_id,
        "side": require_direction(side),
        "level_px_ticks": guard_int64(
            require_int(level_px_ticks, "level_px_ticks"),
            formula_id=FORMULA_ID, field="level_px_ticks"),
        "availability_time_us": guard_int64(
            require_int(availability_time_us, "availability_time_us"),
            formula_id=FORMULA_ID, field="availability_time_us"),
        "level_source": source_event_id,
        "phase": ARMED,
        "extreme_ticks": None,
        "t_exc": None,
        "hold": 0,
        "t_last": None,
        "t_confirm": None,
        "last_seen_ordinal": None,
        "excursion_source": None,
        "hold_sources": [],
        "terminal_reason": None,
    }
    prior = levels.get(level_id)
    if prior is not None:
        if all(prior.get(name) == row[name] for name in _REGISTRATION_FIELDS):
            return TransitionResult(state=state)  # idempotent duplicate registration
        raise StructureLawError(
            f"level {level_id!r} is already tracked with different defining facts; a frozen "
            f"level never re-registers in place (revision -> INVALIDATED, successor = new id)")
    new_levels = dict(levels)
    new_levels[level_id] = row
    return TransitionResult(state={"formula_version": VERSION, "levels": new_levels})


def revise_level(state: dict, *, level_id: str, source_event_id: str) -> TransitionResult:
    """A defining revision of the level → INVALIDATED (any non-terminal phase; §R-F13).

    Terminal or untracked levels are untouched (a terminal absorbs; an untracked id names
    nothing here).
    """
    levels = _require_state(state)
    if not isinstance(source_event_id, str) or not source_event_id:
        raise StructureLawError("source_event_id must be a non-empty str")
    row = levels.get(level_id)
    if row is None:
        return TransitionResult(state=state)
    row = _checked_row(row, level_id)
    if row["phase"] in TERMINAL_PHASES:
        return TransitionResult(state=state)
    new_row = dict(row)
    new_row["phase"] = INVALIDATED
    new_row["terminal_reason"] = LEVEL_REVISED
    new_levels = dict(levels)
    new_levels[level_id] = new_row
    event = _state_event(
        row, to_phase=INVALIDATED, ordinal=None, reason=LEVEL_REVISED, source=source_event_id)
    return TransitionResult(
        state={"formula_version": VERSION, "levels": new_levels}, events=(event,))


def note_gap(state: dict, *, ordinal: object = None, reason: str = GAP_BAR) -> TransitionResult:
    """A declared GAP bar / §1.1 quarantined bar: every non-terminal level → INVALIDATED.

    ``EXC_GAP_RULE = INVALIDATE`` (ratified with this repair). A quarantined VALID_BAR failure
    invalidates any hold chain that requires the bar exactly as a GAP does — the caller passes
    the quarantine's ``reason_code`` (e.g. ``QUARANTINE_INVALID_BAR``) as ``reason``.
    ``ordinal`` is the gapped ordinal when known, else ``None`` (a malformed bar may carry no
    usable ordinal — never fabricated).
    """
    levels = _require_state(state)
    if not isinstance(reason, str) or not re.fullmatch(_UPPER_SNAKE, reason):
        raise StructureLawError(f"gap reason must be UPPER_SNAKE, got {reason!r}")
    at = None if ordinal is None else _coordinate(ordinal, "ordinal", minimum=0)
    new_levels = dict(levels)
    events = []
    changed = False
    for level_id in sorted(levels):
        row = _checked_row(levels[level_id], level_id)
        if row["phase"] in TERMINAL_PHASES:
            continue
        new_row = dict(row)
        new_row["phase"] = INVALIDATED
        new_row["terminal_reason"] = reason
        new_levels[level_id] = new_row
        events.append(_state_event(row, to_phase=INVALIDATED, ordinal=at, reason=reason))
        changed = True
    if not changed:
        return TransitionResult(state=state)
    return TransitionResult(
        state={"formula_version": VERSION, "levels": new_levels}, events=tuple(events))


def evaluate(
    caps: dict, env: ValidatedBar, state: dict, *, ordinal: int, bucket_start_us: int
) -> TransitionResult:
    """The §C.3 production entrypoint: one finalized bar against every tracked level.

    * ``caps`` — ``parameter_id -> bindings.VerifiedCapability`` (exact type, formula F13, key ==
      ``parameter_id``); anything else is a typed rejection BEFORE any state transition.
    * ``env`` — the E01 :class:`~triad_origin.e01_interface.ValidatedBar` (exact type; a raw
      dict raises :class:`EnvelopeContractError`).
    * ``state`` — the v2 machine state (version-checked; a v1 state never blends in).
    * ``ordinal`` / ``bucket_start_us`` — injected per-bar stream coordinates (the consecutive
      per-(instrument,timeframe) finalized-bar index and the bar's bucket start); exact ints,
      int64-guarded, never read from a clock.

    Pure and deterministic: replay and live call THIS function; a checkpoint of the returned
    state resumes to a byte-identical stream (T14).
    """
    e, r, tau, n, digest_source = _resolved_parameters(caps)
    bar = _require_validated_bar(env)
    t = _coordinate(ordinal, "ordinal", minimum=0)
    bucket = _coordinate(bucket_start_us, "bucket_start_us")
    levels = _require_state(state)
    new_levels = dict(levels)
    events: list = []
    changed = False
    for level_id in sorted(levels):
        row = _checked_row(levels[level_id], level_id)
        new_row, row_events = _level_on_bar(
            row, bar, t, bucket, e=e, r=r, tau=tau, n=n, digest_source=digest_source)
        if new_row is not row:
            new_levels[level_id] = new_row
            changed = True
        events.extend(row_events)
    if not changed:
        return TransitionResult(state=state, events=tuple(events))
    return TransitionResult(
        state={"formula_version": VERSION, "levels": new_levels}, events=tuple(events))


# --- per-level bar law -----------------------------------------------------------------------------


def _excursion_trigger(side: str, level_px: int, bar: ValidatedBar, e: int) -> bool:
    if side == LONG:
        return bar.low_ticks <= level_px - e  # inclusive (T1)
    return bar.high_ticks >= level_px + e


def _excursion_probe(side: str, bar: ValidatedBar) -> int:
    return bar.low_ticks if side == LONG else bar.high_ticks


def _deepen(side: str, extreme: int, bar: ValidatedBar) -> int:
    probe = _excursion_probe(side, bar)
    if side == LONG:
        return probe if probe < extreme else extreme
    return probe if probe > extreme else extreme


def _reclaim_qualifies(side: str, level_px: int, bar: ValidatedBar, r: int) -> bool:
    if side == LONG:
        return bar.close_ticks >= level_px + r  # inclusive
    return bar.close_ticks <= level_px - r


def _state_event(row: dict, *, to_phase: str, ordinal: object, reason: object,
                 source: object = None) -> dict:
    event = {
        "event_kind": STATE_KIND,
        "formula": FORMULA_ID,
        "formula_version": VERSION,
        "level_id": row["level_id"],
        "side": row["side"],
        "from_phase": row["phase"],
        "to_phase": to_phase,
        "ordinal": ordinal,
        "reason": reason,
    }
    if source is not None:
        event["source"] = source
    return event


def _terminal(row: dict, *, phase: str, reason: str, ordinal: int) -> tuple:
    new_row = dict(row)
    new_row["phase"] = phase
    new_row["terminal_reason"] = reason
    new_row["last_seen_ordinal"] = ordinal
    return new_row, (_state_event(row, to_phase=phase, ordinal=ordinal, reason=reason),)


def _confirm(row: dict, new_row: dict, t: int, digest_source: tuple) -> tuple:
    """CONFIRMED: emit the mandatory atom, every persisted integer re-checked at the boundary.

    §1.2: an overflowing ``excursion_depth_ticks`` (or any other emitted integer) is
    ``QUARANTINE_OVERFLOW`` — never wrap, never saturate, never emit; the lifecycle fails closed
    to INVALIDATED and the quarantine record replaces the atom.
    """
    side = new_row["side"]
    level_px = new_row["level_px_ticks"]
    extreme = new_row["extreme_ticks"]
    depth = level_px - extreme if side == LONG else extreme - level_px
    try:
        emitted = {
            "extreme_ticks": guard_int64(
                extreme, formula_id=FORMULA_ID, field="extreme_ticks"),
            "t_exc": guard_int64(new_row["t_exc"], formula_id=FORMULA_ID, field="t_exc"),
            "t_confirm": guard_int64(t, formula_id=FORMULA_ID, field="t_confirm"),
            "hold": guard_int64(new_row["hold"], formula_id=FORMULA_ID, field="hold"),
            "excursion_depth_ticks": guard_int64(
                depth, formula_id=FORMULA_ID, field="excursion_depth_ticks"),
        }
    except QuarantineOverflow as exc:
        quarantined = dict(row)
        quarantined["phase"] = INVALIDATED
        quarantined["terminal_reason"] = QUARANTINE_OVERFLOW_REASON
        quarantined["last_seen_ordinal"] = t
        return quarantined, (
            exc.record(),
            _state_event(
                row, to_phase=INVALIDATED, ordinal=t, reason=QUARANTINE_OVERFLOW_REASON),
        )
    new_row["phase"] = CONFIRMED
    new_row["t_confirm"] = emitted["t_confirm"]
    new_row["last_seen_ordinal"] = t
    atom = {
        "event_kind": ATOM_KIND,
        "formula": FORMULA_ID,
        "formula_version": VERSION,
        "level_id": new_row["level_id"],
        "side": side,
        "extreme_ticks": emitted["extreme_ticks"],
        "t_exc": emitted["t_exc"],
        "t_confirm": emitted["t_confirm"],
        "hold": emitted["hold"],
        "excursion_depth_ticks": emitted["excursion_depth_ticks"],
        "identity": {
            "level_id": new_row["level_id"],
            "excursion_source": new_row["excursion_source"],
            "hold_sources": list(new_row["hold_sources"]),
            "parameter_digest": _parameter_digest(digest_source),
        },
    }
    return new_row, (
        _state_event(row, to_phase=CONFIRMED, ordinal=t, reason=None),
        atom,
    )


def _level_on_bar(row: dict, bar: ValidatedBar, t: int, bucket_start_us: int, *,
                  e: int, r: int, tau: int, n: int, digest_source: tuple) -> tuple:
    phase = row["phase"]
    if phase in TERMINAL_PHASES:
        return row, ()  # a terminal absorbs; never silently re-applied

    side = row["side"]
    level_px = row["level_px_ticks"]

    if phase == ARMED:
        # §1.4 availability: the level may be tested only by bars whose bucket start is not
        # before its availability time (inclusive boundary).
        if not availability_allows(row["availability_time_us"], bucket_start_us):
            return row, ()
        if not _excursion_trigger(side, level_px, bar, e):
            return row, ()  # T2: no excursion this bar
        new_row = dict(row)
        new_row["phase"] = EXCURSION
        new_row["extreme_ticks"] = _excursion_probe(side, bar)
        new_row["t_exc"] = t
        new_row["last_seen_ordinal"] = t
        new_row["excursion_source"] = bar.bar_identity
        new_row["hold"] = 0
        new_row["t_last"] = None
        new_row["hold_sources"] = []
        return new_row, (_state_event(row, to_phase=EXCURSION, ordinal=t, reason=None),)

    last_seen = row["last_seen_ordinal"]
    if t <= last_seen:
        return row, ()  # rule (0) generalized: duplicate/regressing ordinal — idempotent no-op

    if phase == EXCURSION:
        if t > last_seen + 1:
            # No declared EXCURSION gap rule in the pseudocode -> the §1.4 global order governs:
            # INVALIDATED dominates every other candidate this bar could raise.
            winner = dominant_transition((
                TransitionPrecedence.INVALIDATED, TransitionPrecedence.EXPIRED))
            assert winner is TransitionPrecedence.INVALIDATED
            return _terminal(row, phase=INVALIDATED, reason=SEQUENCE_GAP, ordinal=t)
        new_row = dict(row)
        new_row["extreme_ticks"] = _deepen(side, row["extreme_ticks"], bar)  # (1) runs FIRST
        new_row["last_seen_ordinal"] = t
        candidates = []
        if t - row["t_exc"] > tau:  # (2) 13b total window, inclusive
            candidates.append(TransitionPrecedence.EXPIRED)
        if _reclaim_qualifies(side, level_px, bar, r):  # (3)
            candidates.append(
                TransitionPrecedence.TERMINAL if n <= 1 else TransitionPrecedence.PROGRESSION)
        if not candidates:
            return new_row, ()  # the extreme may have deepened; silent state change
        winner = dominant_transition(candidates)
        if winner is TransitionPrecedence.EXPIRED:
            new_row["phase"] = EXPIRED
            new_row["terminal_reason"] = TAU_EXCEEDED
            # The bar that expires still deepened the extreme first (normative order).
            return new_row, (
                _state_event(row, to_phase=EXPIRED, ordinal=t, reason=TAU_EXCEEDED),)
        # Reclaim trigger: 13a — this qualifying close IS hold #1.
        new_row["hold"] = 1
        new_row["t_last"] = t
        new_row["hold_sources"] = [bar.bar_identity]
        if new_row["hold"] >= n:  # n == 1: the trigger close confirms
            return _confirm(row, new_row, t, digest_source)
        new_row["phase"] = RECLAIM_PENDING
        return new_row, (_state_event(row, to_phase=RECLAIM_PENDING, ordinal=t, reason=None),)

    # RECLAIM_PENDING — the numbered rules verbatim; rule (1) tau precedes rule (4) gap
    # (pseudocode-normative same-event order — see the module docstring).
    if t - row["t_exc"] > tau:  # (1)
        return _terminal(row, phase=EXPIRED, reason=TAU_EXCEEDED, ordinal=t)
    if t == row["t_last"] + 1:
        if _reclaim_qualifies(side, level_px, bar, r):  # (2)
            new_row = dict(row)
            new_row["hold"] = row["hold"] + 1
            new_row["t_last"] = t
            new_row["last_seen_ordinal"] = t
            new_row["hold_sources"] = list(row["hold_sources"]) + [bar.bar_identity]
            if new_row["hold"] >= n:
                return _confirm(row, new_row, t, digest_source)
            return new_row, ()  # a silent hold increment (no phase change)
        # (3) back to EXCURSION — extreme retained AND still updating on this very bar (T9);
        # a later qualifying close restarts hold=1.
        new_row = dict(row)
        new_row["extreme_ticks"] = _deepen(side, row["extreme_ticks"], bar)
        new_row["phase"] = EXCURSION
        new_row["hold"] = 0
        new_row["t_last"] = None
        new_row["hold_sources"] = []
        new_row["last_seen_ordinal"] = t
        return new_row, (_state_event(row, to_phase=EXCURSION, ordinal=t, reason=HOLD_RESET),)
    # (4) t > t_last + 1 — missing finalized ordinal: data-continuity break. There is no
    # legitimate skipped finalized ordinal; treat any skip as gap.
    return _terminal(row, phase=INVALIDATED, reason=SEQUENCE_GAP, ordinal=t)

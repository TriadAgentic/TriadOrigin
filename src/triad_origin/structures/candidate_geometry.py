"""F18 — candidate geometry and geometric reward/risk (golden vector GV-015).

A pure evaluator, not a :class:`triad_origin.transition.DeterministicMachine` — F18 has no
lifecycle of its own; it scores one already-frozen candidate occurrence exactly once, from inputs
that are already resolved by the time it runs: a direction, an entry reference ``E``, a frozen
natural-invalidation edge, a causally available target set, and the candidate's own knowledge-time
cutoff. Formula (F18, ``candidate.geometry.v1``)::

    risk_ticks = abs(E - S)
    reward_ticks = dir_sign * (T - E)
    RR_geom = reward_ticks / risk_ticks
    admit only risk_ticks > 0, reward_ticks > 0, RR_geom >= 2

``dir_sign`` is ``+1`` for LONG, ``-1`` for SHORT — the mirror law: a full price reflection
(``E'=-E, S'=-S, T'=-T``, direction swapped) reproduces the exact same ``risk_ticks``/
``reward_ticks``/admit verdict, proved by :class:`TestMirror` below.

**``S`` — the formula's own "natural invalidation" — is derived here, never taken verbatim.** The
caller supplies the FROZEN structural edge (``natural_invalidation_source_ticks``, e.g. a swing low
for LONG), and this module moves the stop one PAR-172 buffer BEYOND that edge in the
risk-increasing direction (:data:`triad_origin.structures.capsules.DECLARED_NATURAL_INVALIDATION_BUFFER`
— the same declared rule byte-string as F09's break buffer): MINUS the buffer for LONG (further
from entry, i.e. lower), PLUS for SHORT (further from entry, i.e. higher). Never the frozen edge
itself, and never a hand-tuned amount.

Every semantic parameter arrives via :func:`triad_origin.transition.require` — no code default,
ever — and only the exact declared byte-string per parameter is admitted; anything else fails
closed (:class:`triad_origin.structures.common.StructureLawError`). The three GENERIC,
capsule-independent PAR-064/172/173 parameter keys are the ones
:mod:`triad_origin.structures.capsules` already reserves for F18
(:data:`capsules.PAR_TARGET_AVAILABILITY_RULE`, :data:`capsules.PAR_NATURAL_INVALIDATION_BUFFER_RULE`,
:data:`capsules.PAR_TARGET_SELECTOR`) — this module reuses those exact keys rather than
re-declaring them. PAR-061 ``MIN_GEOMETRIC_RR`` (RATIFIED_RC1, ``declared_value "2/1"``) is likewise
a required declared-rule parameter (:data:`PARAM_MIN_GEOMETRIC_RR_RULE`) — even a ratified, fixed
floor is never a code default (Doc 02 §02.15).

**Target selection (PAR-064 causal availability + PAR-173 ``nearest_positive_reward``).**
``available_targets`` is filtered first to causally available
(``target.knowledge_time_us <= candidate_knowledge_time_us``, inclusive — PAR-009), then to
strictly positive reward (``dir_sign * (target_ticks - E) > 0`` — exactly the declared value's own
``nearest_positive_reward`` name), then the NEAREST surviving target wins (smallest reward
magnitude — for a positive-reward target the reward IS the distance), tied first by
:data:`capsules.TARGET_SELECTOR_PRIORITY` type order (``PROTECTED_SWING`` > ``SESSION_LEVEL`` >
``EQUAL_LEVEL``), then by ``root_id`` ascending string sort. No surviving target ->
``F18_NO_TARGET``. An unknown ``target_type`` is a structural violation and raises, never silently
excluded.

**Level identity (RC3 F18 identity_material "capsule occurrence + E/S/T level IDs + formula/params").**
The selected target's ``root_id`` (the T level ID) is returned on the result as
``selected_target_root_id`` — because the tie-break is ON ``root_id``, the winner's level identity
is NOT recoverable from ``(target_type, target_ticks)`` alone, so discarding it would leave the T
level ID unbindable by the publisher/identity layer. The E and S level IDs are optional pass-through
inputs (``entry_reference_level_id`` / ``natural_invalidation_level_id``, honest-null when the caller
does not supply them — never fabricated) echoed onto the result so all three of the bundle-declared
E/S/T level IDs can reach candidate identity.

**Sequence, each a named abstention (never a silent null, never a fabricated value):** the capsule
resolves (an unknown ``capsule_semantic_id`` raises
:class:`triad_origin.structures.capsules.CapsuleUnavailableError`, never swallowed) -> the four
declared-rule parameters check -> ``ATR14_ticks`` present (``F18_NO_ATR``) -> the buffered stop ->
**the directional stop-side invariant** (``F18_INVALID_STOP_SIDE`` — the buffered stop must land
strictly on the risk-bearing side of entry: below for LONG, above for SHORT; checked BEFORE
``risk_ticks = abs(entry - stop)`` can launder a wrong-side stop into a positive "risk", which would
otherwise admit directionally-invalid geometry) -> ``risk_ticks > 0`` (``F18_ZERO_RISK``, the
exact-equality boundary) -> target filter+select (``F18_NO_TARGET``) -> the winner's recomputed
``reward_ticks > 0`` (``F18_NONPOSITIVE_REWARD`` — structurally unreachable through this module's own
public entry point, since the selector's own PAR-173 filter already excludes a nonpositive-reward
target before it can ever win; kept as ORIGIN's "never trust, recompute" re-verification, the same
discipline F11 applies to its own qualification conjuncts) -> the PAR-061 floor, decided by exact
integer cross-multiplication ``reward_ticks*1 >= risk_ticks*2`` — never a float division —
``F18_GEOMETRY_BELOW_FLOOR`` below it, inclusive at equality (PAR-009).

An abstention result carries every field legitimately determined before the abstention point and
``None`` for everything past it — nothing later is fabricated to fill in the shape.

GV-015: LONG, ``E=100``, a frozen edge and ``ATR14_ticks`` chosen so the buffered stop lands at
``S=98`` (``risk_ticks=2``); ``T=104`` -> ``reward_ticks=4``, ``4*1 >= 2*2`` -> admit,
``(rr_numerator, rr_denominator) = (4, 2)`` — the exact UNREDUCED occurrence pair, never simplified
to ``(2, 1)`` (matching ``triad.edge_candidate.v2``'s separate ``rr_numerator``/``rr_denominator``
wire fields); ``T=103`` -> ``reward_ticks=3``, ``3*1 < 2*2`` -> ``F18_GEOMETRY_BELOW_FLOOR``, one
tick below the floor.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..transition import Params, require
from . import capsules, common

FORMULA_F18 = "F18"

# PAR-061 MIN_GEOMETRIC_RR (RATIFIED_RC1) is not one of common.py's ATR-scaled rational rules and
# not one of the two capsule-independent F18 entry-convention parameters capsules.py already
# reserves — it is F18's own required declared floor, admitted only by its exact declared_value
# byte-string, exactly like every other declared-rule parameter in ORIGIN.
PARAM_MIN_GEOMETRIC_RR_RULE = "min_geometric_rr_rule"
DECLARED_MIN_GEOMETRIC_RR = "2/1"  # PAR-061, declared_value "2/1"
_MIN_GEOMETRIC_RR_FRACTION = (2, 1)  # admit iff reward_ticks*1 >= risk_ticks*2

ABSTAIN_NO_ATR = "F18_NO_ATR"
ABSTAIN_INVALID_STOP_SIDE = "F18_INVALID_STOP_SIDE"
ABSTAIN_ZERO_RISK = "F18_ZERO_RISK"
ABSTAIN_NO_TARGET = "F18_NO_TARGET"
ABSTAIN_NONPOSITIVE_REWARD = "F18_NONPOSITIVE_REWARD"
ABSTAIN_GEOMETRY_BELOW_FLOOR = "F18_GEOMETRY_BELOW_FLOOR"


@dataclass(frozen=True)
class GeometryResult:
    """F18's one evaluated result — admitted geometry, or a named abstention.

    ``rr_numerator``/``rr_denominator`` are populated ONLY on ``admitted=True`` — the RAW
    unreduced occurrence pair (``reward_ticks``, ``risk_ticks``), never re-simplified. On an
    abstention, ``risk_ticks``/``reward_ticks``/``natural_invalidation_ticks``/the selected-target
    fields still carry whatever was legitimately computed before the abstention point (an honest
    diagnostic, distinct from the admitted RR pair); anything not yet computed stays ``None``.
    """

    admitted: bool
    risk_ticks: int | None
    reward_ticks: int | None
    rr_numerator: int | None
    rr_denominator: int | None
    entry_reference_ticks: int | None
    natural_invalidation_ticks: int | None
    selected_target_ticks: int | None
    selected_target_type: str | None
    selected_target_root_id: str | None
    entry_reference_level_id: str | None
    natural_invalidation_level_id: str | None
    abstain_reason: str | None
    abstain_detail: str | None


def _dir_sign(direction: str) -> int:
    return 1 if direction == common.LONG else -1


def _require_nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise common.StructureLawError(f"{name} must be a non-empty string")
    return value


def _abstain(reason_code: str, detail: str, refs: dict, **known: object) -> GeometryResult:
    event = common.abstention(reason_code, formula=FORMULA_F18, detail=detail, refs=refs)
    fields: dict[str, object] = {
        "admitted": False,
        "risk_ticks": None,
        "reward_ticks": None,
        "rr_numerator": None,
        "rr_denominator": None,
        "entry_reference_ticks": None,
        "natural_invalidation_ticks": None,
        "selected_target_ticks": None,
        "selected_target_type": None,
        "selected_target_root_id": None,
        "entry_reference_level_id": None,
        "natural_invalidation_level_id": None,
        "abstain_reason": event["reason_code"],
        "abstain_detail": event["detail"],
    }
    fields.update(known)
    return GeometryResult(**fields)  # type: ignore[arg-type]


def _select_target(
    direction: str,
    entry_reference_ticks: int,
    targets: object,
    candidate_knowledge_time_us: int,
    selector_priority: tuple[str, ...],
) -> tuple[str, int, str] | None:
    """The PAR-064 + PAR-173 winner ``(target_type, target_ticks, root_id)``, or ``None``.

    The winning ``root_id`` (the T level ID) is returned because the tie-break is ON ``root_id`` —
    ``(target_type, target_ticks)`` alone does not disambiguate the selected level.
    """
    if not isinstance(targets, list):
        raise common.StructureLawError("available_targets must be a list")
    dir_sign = _dir_sign(direction)
    priority_rank = {name: index for index, name in enumerate(selector_priority)}
    candidates: list[tuple[int, int, str, str, int]] = []
    for raw in targets:
        if not isinstance(raw, dict):
            raise common.StructureLawError("each available target must be an object")
        target_type = raw.get("target_type")
        if target_type not in priority_rank:
            raise common.StructureLawError(f"unknown target_type: {target_type!r}")
        target_ticks = common.require_int(raw.get("target_ticks"), "target_ticks")
        knowledge_time_us = common.require_int(raw.get("knowledge_time_us"), "knowledge_time_us")
        root_id = _require_nonempty_str(raw.get("root_id"), "root_id")
        if knowledge_time_us > candidate_knowledge_time_us:
            continue  # PAR-064: not causally available at candidate publication (equality passes)
        reward = dir_sign * (target_ticks - entry_reference_ticks)
        if reward <= 0:
            continue  # PAR-173 "nearest_positive_reward": zero/negative reward is excluded
        candidates.append((reward, priority_rank[target_type], root_id, target_type, target_ticks))
    if not candidates:
        return None
    candidates.sort(key=lambda row: (row[0], row[1], row[2]))
    _, _, root_id, target_type, target_ticks = candidates[0]
    return target_type, target_ticks, root_id


def evaluate_candidate_geometry(
    *,
    direction: str,
    entry_reference_ticks: int,
    natural_invalidation_source_ticks: int,
    atr14_ticks: int | None,
    capsule_semantic_id: str,
    available_targets: list[dict],
    candidate_knowledge_time_us: int,
    params: Params,
    entry_reference_level_id: str | None = None,
    natural_invalidation_level_id: str | None = None,
) -> GeometryResult:
    """F18 — evaluate one candidate occurrence's geometry and geometric reward/risk (GV-015).

    ``entry_reference_level_id`` / ``natural_invalidation_level_id`` are the OPTIONAL E/S level IDs
    (RC3 F18 identity_material) echoed onto the result — honest-null when the caller omits them,
    never fabricated; a supplied value must be a non-empty string.
    """
    capsules.resolve_capsule(capsule_semantic_id)  # fail closed; propagate CapsuleUnavailableError

    buffer_rule = require(params, capsules.PAR_NATURAL_INVALIDATION_BUFFER_RULE)
    if buffer_rule != capsules.DECLARED_NATURAL_INVALIDATION_BUFFER:
        raise common.StructureLawError(
            f"F18 admits only the declared PAR-172 rule "
            f"{capsules.DECLARED_NATURAL_INVALIDATION_BUFFER!r}, got {buffer_rule!r}")

    availability_rule = require(params, capsules.PAR_TARGET_AVAILABILITY_RULE)
    if availability_rule != capsules.TARGET_AVAILABILITY_RULE:
        raise common.StructureLawError(
            f"F18 admits only the declared PAR-064 rule "
            f"{capsules.TARGET_AVAILABILITY_RULE!r}, got {availability_rule!r}")

    selector_priority = require(params, capsules.PAR_TARGET_SELECTOR)
    if isinstance(selector_priority, list):
        selector_priority = tuple(selector_priority)
    if selector_priority != capsules.TARGET_SELECTOR_PRIORITY:
        raise common.StructureLawError(
            f"F18 admits only the declared PAR-173 selector priority "
            f"{capsules.TARGET_SELECTOR_PRIORITY!r}, got {selector_priority!r}")

    min_rr_rule = require(params, PARAM_MIN_GEOMETRIC_RR_RULE)
    if min_rr_rule != DECLARED_MIN_GEOMETRIC_RR:
        raise common.StructureLawError(
            f"F18 admits only the declared PAR-061 rule {DECLARED_MIN_GEOMETRIC_RR!r}, "
            f"got {min_rr_rule!r}")

    direction = common.require_direction(direction)
    entry = common.require_int(entry_reference_ticks, "entry_reference_ticks")
    source = common.require_int(
        natural_invalidation_source_ticks, "natural_invalidation_source_ticks")
    knowledge_time = common.require_int(
        candidate_knowledge_time_us, "candidate_knowledge_time_us")
    entry_level_id = (
        None if entry_reference_level_id is None
        else _require_nonempty_str(entry_reference_level_id, "entry_reference_level_id"))
    natural_level_id = (
        None if natural_invalidation_level_id is None
        else _require_nonempty_str(natural_invalidation_level_id, "natural_invalidation_level_id"))

    refs = {"capsule_semantic_id": capsule_semantic_id, "direction": direction}

    if atr14_ticks is None:
        return _abstain(
            ABSTAIN_NO_ATR, "no causal ATR at candidate-geometry evaluation time", refs,
            entry_reference_ticks=entry, entry_reference_level_id=entry_level_id)

    atr = common.require_int(atr14_ticks, "atr14_ticks")
    buffer_ticks = common.evaluate_declared_rational(buffer_rule, atr)
    dir_sign = _dir_sign(direction)
    stop = source - buffer_ticks if direction == common.LONG else source + buffer_ticks

    # Directional stop-side invariant, checked BEFORE abs() can launder it: a LONG stop must land
    # strictly below entry and a SHORT stop strictly above it. Without this, a wrong-side
    # natural_invalidation_source (e.g. an edge already past entry, or a buffer too small to cross
    # back over it) produces a stop on the WRONG side of entry, and abs(entry - stop) turns that
    # invalid geometry into a positive "risk" that can admit — exactly backwards, since the
    # candidate's true directional risk is unbounded on that side. The exact-equality case
    # (stop == entry) is deliberately left to the existing risk_ticks<=0 check below, which already
    # names it ABSTAIN_ZERO_RISK — this catches only the strictly-wrong-side case.
    if direction == common.LONG and stop > entry:
        return _abstain(
            ABSTAIN_INVALID_STOP_SIDE,
            "the buffered LONG stop landed at or above entry — directionally invalid geometry",
            refs, entry_reference_ticks=entry, natural_invalidation_ticks=stop,
            entry_reference_level_id=entry_level_id,
            natural_invalidation_level_id=natural_level_id)
    if direction == common.SHORT and stop < entry:
        return _abstain(
            ABSTAIN_INVALID_STOP_SIDE,
            "the buffered SHORT stop landed at or below entry — directionally invalid geometry",
            refs, entry_reference_ticks=entry, natural_invalidation_ticks=stop,
            entry_reference_level_id=entry_level_id,
            natural_invalidation_level_id=natural_level_id)

    risk_ticks = abs(entry - stop)

    if risk_ticks <= 0:
        return _abstain(
            ABSTAIN_ZERO_RISK,
            "entry reference and the buffered natural-invalidation stop coincide", refs,
            entry_reference_ticks=entry, natural_invalidation_ticks=stop, risk_ticks=risk_ticks,
            entry_reference_level_id=entry_level_id,
            natural_invalidation_level_id=natural_level_id)

    winner = _select_target(direction, entry, available_targets, knowledge_time, selector_priority)
    if winner is None:
        return _abstain(
            ABSTAIN_NO_TARGET,
            "no causally available, strictly-positive-reward target survives selection", refs,
            entry_reference_ticks=entry, natural_invalidation_ticks=stop, risk_ticks=risk_ticks,
            entry_reference_level_id=entry_level_id,
            natural_invalidation_level_id=natural_level_id)
    target_type, target_ticks, target_root_id = winner

    reward_ticks = dir_sign * (target_ticks - entry)
    if reward_ticks <= 0:
        # See the module docstring: unreachable through this function's own selector, kept as the
        # "never trust, recompute" re-verification.
        return _abstain(
            ABSTAIN_NONPOSITIVE_REWARD, "the selected target's recomputed reward is not positive",
            refs, entry_reference_ticks=entry, natural_invalidation_ticks=stop,
            risk_ticks=risk_ticks, reward_ticks=reward_ticks,
            selected_target_ticks=target_ticks, selected_target_type=target_type,
            selected_target_root_id=target_root_id, entry_reference_level_id=entry_level_id,
            natural_invalidation_level_id=natural_level_id)

    floor_num, floor_den = _MIN_GEOMETRIC_RR_FRACTION
    if reward_ticks * floor_den < risk_ticks * floor_num:
        return _abstain(
            ABSTAIN_GEOMETRY_BELOW_FLOOR,
            f"reward:risk {reward_ticks}:{risk_ticks} falls below the {floor_num}:{floor_den} "
            "PAR-061 floor",
            refs, entry_reference_ticks=entry, natural_invalidation_ticks=stop,
            risk_ticks=risk_ticks, reward_ticks=reward_ticks,
            selected_target_ticks=target_ticks, selected_target_type=target_type,
            selected_target_root_id=target_root_id, entry_reference_level_id=entry_level_id,
            natural_invalidation_level_id=natural_level_id)

    return GeometryResult(
        admitted=True, risk_ticks=risk_ticks, reward_ticks=reward_ticks,
        rr_numerator=reward_ticks, rr_denominator=risk_ticks,
        entry_reference_ticks=entry, natural_invalidation_ticks=stop,
        selected_target_ticks=target_ticks, selected_target_type=target_type,
        selected_target_root_id=target_root_id, entry_reference_level_id=entry_level_id,
        natural_invalidation_level_id=natural_level_id,
        abstain_reason=None, abstain_detail=None)

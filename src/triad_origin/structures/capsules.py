"""B06 — the explicit semantic capsule registry (5 stable IDs, no guessed ordinal mapping).

RC1/RC2 named five entry-convention parameters by ORDINAL position — ``PAR-174 CAP01_OB_ENTRY``
through ``PAR-178 CAP05_SESSION_ENTRY``. RC3/the reconciled plan retires that ordinal scheme in
favor of five STABLE SEMANTIC IDs (``dc_swing_bos_first_retest.v1``,
``protected_swing_choch_first_retest.v1``, ``fvg_displacement_first_touch.v1``,
``ob_displacement_bos_first_touch.v1``, ``level_excursion_reclaim_flow_confirmed.v1``) and is
explicit that **the ordinal position (CAP01..CAP05) must never be trusted as the mapping** —
"replace them with explicit semantic-ID-bound parameter rows or keep the capsule unavailable"
(``docs/plan/01_MILESTONE_BREAKDOWN.md`` B06). This module IS that explicit binding, reasoned by
NAME and by each parameter's own ``formula_refs``/``exact_rule`` text — never by position.

**The binding, derived (each row cites its own evidence, not a position)**::

    ob_displacement_bos_first_touch.v1  -> PAR-174 CAP01_OB_ENTRY  (declared_value "zone_midpoint")
        Evidence: PAR-174's NAME is literally "OB_ENTRY" (Order Block); F12 (order_block_registry)
        is this capsule's own structural composition. formula_refs on PAR-174 is sparse
        ("F18;F21" — F12 absent from it), so the bind is by NAME, not by cross-reference; recorded
        honestly in the disposition register (row E21) rather than silently assumed airtight.

    fvg_displacement_first_touch.v1  -> PAR-175 CAP02_FVG_ENTRY  ("zone_midpoint")
        Evidence: PAR-175's formula_refs is "F10;F18;F21" — F10 IS the FVG registry
        (fvg_registry.py). Both name AND cross-reference agree; the strongest of the five binds.

    level_excursion_reclaim_flow_confirmed.v1  -> PAR-176 CAP03_EQUAL_SWEEP_ENTRY
        ("frozen_equal_level_anchor")
        Evidence: PAR-176's formula_refs is "F06;F13;F14;F18" — F06 is the equal-level cluster
        (typed_level_registry.EqualLevelCluster) and F13 is excursion/reclaim
        (excursion_reclaim_registry.ExcursionReclaimTracker); "equal sweep" names exactly the
        F06-anchor-then-F13-sweep-and-reclaim shape this capsule's own name describes.

    protected_swing_choch_first_retest.v1  -> PAR-177 CAP04_CHOCH_ENTRY ("accepted_break_level")
        Evidence: PAR-177's formula_refs is "F08;F09;F14;F18" — F08 IS
        ``structure_state.ProtectedSwingStructure`` (the CHoCH machine) and F09 is the
        break/BOS detector; both name AND cross-reference agree.

    dc_swing_bos_first_retest.v1  -> **NO RC2 CAP-row match.**
        No PAR-174..178 row references the (F03 DirectionalChangeSwing, F09 BreakDetector) pair
        this capsule's own name names — CAP04's refs list F08 (protected swing / CHoCH), not F03
        (directional-change swing / BOS), and no other CAP row lists F03 at all. Rather than force
        this capsule onto a mismatched RC2 row, it uses ONLY the generic, capsule-independent F18
        entry-convention parameters (:data:`PAR_TARGET_AVAILABILITY_RULE`,
        :data:`PAR_NATURAL_INVALIDATION_BUFFER`, :data:`PAR_TARGET_SELECTOR` — PAR-064/172/173,
        which carry no capsule-specific entry-reference override) — an honest "this capsule has no
        RC2-era entry-anchor override" rather than a guessed one.

**The orphaned RC2 row.** ``PAR-178 CAP05_SESSION_ENTRY`` (``F07;F13;F14;F18``,
``"completed_session_anchor"``) has no home among the five ratified RC3 semantic capsules — none
of the five canonical IDs names a session-anchored entry. It is registered here as
:data:`ORPHANED_LEGACY_PARAMETERS` (a NAMED fact, not silently dropped) and bound to NO capsule; a
future sixth capsule (or an operator ruling that folds it into an existing one) is a ratification
act, never guessed by this module. See the disposition register (row E21) for the full accounting.

**Isolation law (no voting/ensemble; LEV-... mirrors the "one formula/parameter/trial identity per
instance" B06 deliverable).** :func:`resolve_capsule` returns EXACTLY one
:class:`CapsuleDefinition` for a semantic id, or raises :class:`CapsuleUnavailableError` — there is
structurally no code path here that blends, votes across, or ensembles two capsules' outputs; every
capsule occurrence stamps its own ``capsule_id``/``capsule_version``/``parameter_digest`` (the
identity fields ``triad.edge_candidate.v2`` already declares) and nothing here computes a second,
competing identity for the same occurrence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import common

# The three GENERIC (capsule-independent) F18 entry-convention parameters — PAR-064/172/173.
PAR_TARGET_AVAILABILITY_RULE = "target_availability_rule"
PAR_NATURAL_INVALIDATION_BUFFER_RULE = "natural_invalidation_buffer_rule"
PAR_TARGET_SELECTOR = "target_selector"

# PAR-172's declared value is the byte-identical rational expression as F09's break buffer
# (PAR-043, common.DECLARED_BOS_CLOSE_BUFFER) — same declared string, reused rather than
# re-declared (the F13 precedent).
DECLARED_NATURAL_INVALIDATION_BUFFER = common.DECLARED_BOS_CLOSE_BUFFER  # PAR-172 (F18)

TARGET_AVAILABILITY_RULE = "target.knowledge_time<=candidate.knowledge_time"  # PAR-064, RATIFIED_RC1
TARGET_SELECTOR_PRIORITY = ("PROTECTED_SWING", "SESSION_LEVEL", "EQUAL_LEVEL")  # PAR-173 tie order


class CapsuleLawError(ValueError):
    """A capsule-registry usage error (fail closed, named)."""


class CapsuleUnavailableError(CapsuleLawError):
    """The requested semantic capsule id has no registered, ratifiable definition."""


@dataclass(frozen=True)
class CapsuleDefinition:
    """One isolated capsule's identity: its structural composition + its entry-anchor rule.

    ``entry_anchor_rule`` is ``None`` for a capsule with no RC2-era capsule-specific override
    (``dc_swing_bos_first_retest.v1``) — it consumes only the three generic PAR-064/172/173
    parameters, never a fabricated capsule-specific one.
    """

    semantic_id: str
    capsule_version: str
    structural_formulas: tuple[str, ...]
    entry_anchor_rule: str | None
    entry_anchor_par_id: str | None
    source_par_id: str | None
    rc2_ordinal_disclaimer: str


_CAPSULES: dict[str, CapsuleDefinition] = {
    "ob_displacement_bos_first_touch.v1": CapsuleDefinition(
        semantic_id="ob_displacement_bos_first_touch.v1",
        capsule_version="1",
        structural_formulas=("F11", "F12", "F14", "F18"),
        entry_anchor_rule="zone_midpoint",
        entry_anchor_par_id="PAR-174",
        source_par_id="PAR-174",
        rc2_ordinal_disclaimer=(
            "bound by NAME (PAR-174 is 'CAP01_OB_ENTRY') — its own formula_refs field does not "
            "list F12; the bind is documented, not silently trusted"),
    ),
    "fvg_displacement_first_touch.v1": CapsuleDefinition(
        semantic_id="fvg_displacement_first_touch.v1",
        capsule_version="1",
        structural_formulas=("F10", "F11", "F14", "F18"),
        entry_anchor_rule="zone_midpoint",
        entry_anchor_par_id="PAR-175",
        source_par_id="PAR-175",
        rc2_ordinal_disclaimer="bound by NAME and formula_refs agreement (PAR-175 lists F10)",
    ),
    "level_excursion_reclaim_flow_confirmed.v1": CapsuleDefinition(
        semantic_id="level_excursion_reclaim_flow_confirmed.v1",
        capsule_version="1",
        structural_formulas=("F06", "F13", "F14", "F15", "F16", "F17", "F18"),
        entry_anchor_rule="frozen_equal_level_anchor",
        entry_anchor_par_id="PAR-176",
        source_par_id="PAR-176",
        rc2_ordinal_disclaimer=(
            "bound by NAME and formula_refs agreement (PAR-176 'CAP03_EQUAL_SWEEP_ENTRY' lists "
            "F06 equal-level + F13 excursion/reclaim)"),
    ),
    "protected_swing_choch_first_retest.v1": CapsuleDefinition(
        semantic_id="protected_swing_choch_first_retest.v1",
        capsule_version="1",
        structural_formulas=("F08", "F09", "F14", "F18"),
        entry_anchor_rule="accepted_break_level",
        entry_anchor_par_id="PAR-177",
        source_par_id="PAR-177",
        rc2_ordinal_disclaimer=(
            "bound by NAME and formula_refs agreement (PAR-177 'CAP04_CHOCH_ENTRY' lists F08 "
            "protected-swing + F09 break)"),
    ),
    "dc_swing_bos_first_retest.v1": CapsuleDefinition(
        semantic_id="dc_swing_bos_first_retest.v1",
        capsule_version="1",
        structural_formulas=("F03", "F09", "F14", "F18"),
        entry_anchor_rule=None,
        entry_anchor_par_id=None,
        source_par_id=None,
        rc2_ordinal_disclaimer=(
            "NO RC2 CAP-row references (F03,F09) together; this capsule has no capsule-specific "
            "entry-anchor override and consumes only the generic PAR-064/172/173 parameters"),
    ),
}

# PAR-178 CAP05_SESSION_ENTRY: registered honestly as unbound to any of the five ratified
# capsules — never silently dropped, never guessed onto an existing capsule.
ORPHANED_LEGACY_PARAMETERS: dict[str, dict[str, str]] = {
    "PAR-178": {
        "legacy_name": "CAP05_SESSION_ENTRY",
        "declared_value": "completed_session_anchor",
        "formula_refs": "F07;F13;F14;F18",
        "disposition": (
            "no home among the five ratified semantic capsules; a session-anchored capsule "
            "would be a new, separately ratified sixth capsule, never assumed onto an existing "
            "one — see docs/plan/09_OPEN_QUESTIONS.md row E21"),
    },
}

CANONICAL_SEMANTIC_IDS: tuple[str, ...] = tuple(sorted(_CAPSULES))


def resolve_capsule(semantic_id: str) -> CapsuleDefinition:
    """Return the ONE isolated capsule definition for ``semantic_id``.

    Fails closed (``CapsuleUnavailableError``) for anything not in :data:`CANONICAL_SEMANTIC_IDS`
    — including any RC2 ``CAP01``..``CAP05`` ordinal spelling, which is never accepted as an alias.
    """
    if not isinstance(semantic_id, str) or semantic_id not in _CAPSULES:
        raise CapsuleUnavailableError(
            f"unknown or unratified semantic capsule id: {semantic_id!r} (RC2 CAP-ordinal "
            "spellings are never accepted — see CANONICAL_SEMANTIC_IDS)")
    return _CAPSULES[semantic_id]


def capsule_digest(definition: CapsuleDefinition) -> str:
    """A stable content digest identifying this capsule's exact composition (isolation proof)."""
    payload = {
        "semantic_id": definition.semantic_id,
        "capsule_version": definition.capsule_version,
        "structural_formulas": list(definition.structural_formulas),
        "entry_anchor_rule": definition.entry_anchor_rule,
    }
    return common.geometry_digest(payload)

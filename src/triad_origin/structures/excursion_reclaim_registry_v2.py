"""Versioned successor face of the retired ``excursion_reclaim_registry`` (F13 v1 -> v2).

``tools/verify_formula_entrypoints.py`` enforces that a module retired with a MODULE-docstring
``RETIRED_DEFECTIVE`` banner has a versioned successor named ``<stem>_v*.py`` — retirement can
never silently remove a formula's production surface. The R-F13 implementation lives in
:mod:`triad_origin.structures.excursion_reclaim_v2` (``level_excursion_reclaim.closed.v2``);
this module is that implementation's stem-preserving successor face and re-exports the complete
public surface verbatim. ONE implementation, one law — nothing is redefined here.
"""

from __future__ import annotations

from .excursion_reclaim_v2 import (
    ARMED,
    ATOM_KIND,
    BINDING_VALUE_NOT_INTEGER,
    CONFIRMED,
    CONSUMED,
    EXC_GAP_RULE,
    EXC_HOLD_INCLUDES_TRIGGER,
    EXC_TAU_SCOPE,
    EXCURSION,
    EXPIRED,
    EnvelopeContractError,
    FORMULA_ID,
    GAP_BAR,
    HOLD_RESET,
    INVALIDATED,
    LEVEL_REVISED,
    PARAM_EXCURSION_MIN,
    PARAM_RECLAIM_CLOSE_BUFFER,
    PARAM_RECLAIM_HOLD_BARS,
    PARAM_RECLAIM_TAU,
    PHASES,
    QUARANTINE_OVERFLOW_REASON,
    RECLAIM_PENDING,
    REQUIRED_PARAMETER_IDS,
    SEQUENCE_GAP,
    STATE_KIND,
    STATE_VERSION_MISMATCH,
    TAU_EXCEEDED,
    TERMINAL_PHASES,
    TRANSITION_CLASSES,
    VERSION,
    evaluate,
    initial_state,
    note_gap,
    register_level,
    revise_level,
)

__all__ = (
    "ARMED",
    "ATOM_KIND",
    "BINDING_VALUE_NOT_INTEGER",
    "CONFIRMED",
    "CONSUMED",
    "EXC_GAP_RULE",
    "EXC_HOLD_INCLUDES_TRIGGER",
    "EXC_TAU_SCOPE",
    "EXCURSION",
    "EXPIRED",
    "EnvelopeContractError",
    "FORMULA_ID",
    "GAP_BAR",
    "HOLD_RESET",
    "INVALIDATED",
    "LEVEL_REVISED",
    "PARAM_EXCURSION_MIN",
    "PARAM_RECLAIM_CLOSE_BUFFER",
    "PARAM_RECLAIM_HOLD_BARS",
    "PARAM_RECLAIM_TAU",
    "PHASES",
    "QUARANTINE_OVERFLOW_REASON",
    "RECLAIM_PENDING",
    "REQUIRED_PARAMETER_IDS",
    "SEQUENCE_GAP",
    "STATE_KIND",
    "STATE_VERSION_MISMATCH",
    "TAU_EXCEEDED",
    "TERMINAL_PHASES",
    "TRANSITION_CLASSES",
    "VERSION",
    "evaluate",
    "initial_state",
    "note_gap",
    "register_level",
    "revise_level",
)

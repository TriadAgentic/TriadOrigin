"""Deterministic identity hierarchy (Doc 03 §03.4).

    semantic_instance_id = hash(formula_version, parameter_digest, venue_model, timeframe)
    structure_id         = hash(identity_schema_version, instrument_id, venue_model,
                                structure_kind, semantic_instance_id, direction,
                                immutable_source_ids, original_geometry_digest)
    reaction_id          = hash(structure_id, reaction_formula, trigger_source_ids)
    hypothesis_id        = hash(reaction_id, capsule_version, parameter_digest)
    candidate_id         = hash(hypothesis_id, candidate_formula, publication_occurrence)

Mutable geometry revisions retain ``structure_id`` and increment ``state_seq``. Attempt/order/fill
IDs never replace candidate/hypothesis identity.

Every ID is a length-prefixed field digest (``canonical.digest_fields``) — deterministic, and
independent of logging, wall clock, process id, thread count, iteration order or deployment instance
(Doc 02 §02.16 identity stability).
"""

from __future__ import annotations

from collections.abc import Iterable

from .canonical import digest_fields

IDENTITY_SCHEMA_VERSION = "origin.identity.v1"

# Short human-facing prefixes (mirroring Doc 03 normative examples: str_, cand_, stx_ …).
_PREFIX = {
    "semantic_instance": "sinst_",
    "structure": "str_",
    "reaction": "rct_",
    "hypothesis": "hyp_",
    "candidate": "cand_",
    "opportunity_cluster": "opp_",
}
_HEXLEN = 40  # 160 bits of the SHA-256 digest is ample and keeps IDs compact + stable.


def _seq_digest(items: Iterable[str]) -> str:
    """Order-preserving digest of a sequence of source IDs (never sorted — order is semantic)."""
    items = list(items)
    return digest_fields("seq", len(items), *items)


def semantic_instance_id(
    formula_version: str,
    parameter_digest: str,
    venue_model: str,
    timeframe: str,
) -> str:
    h = digest_fields(
        "semantic_instance",
        formula_version,
        parameter_digest,
        venue_model,
        timeframe,
    )
    return _PREFIX["semantic_instance"] + h[:_HEXLEN]


def structure_id(
    instrument_id: str,
    venue_model: str,
    structure_kind: str,
    semantic_instance_id_: str,
    direction: str,
    immutable_source_ids: Iterable[str],
    original_geometry_digest: str,
    *,
    identity_schema_version: str = IDENTITY_SCHEMA_VERSION,
) -> str:
    h = digest_fields(
        "structure",
        identity_schema_version,
        instrument_id,
        venue_model,
        structure_kind,
        semantic_instance_id_,
        direction,
        _seq_digest(immutable_source_ids),
        original_geometry_digest,
    )
    return _PREFIX["structure"] + h[:_HEXLEN]


def reaction_id(
    structure_id_: str,
    reaction_formula: str,
    trigger_source_ids: Iterable[str],
) -> str:
    h = digest_fields(
        "reaction",
        structure_id_,
        reaction_formula,
        _seq_digest(trigger_source_ids),
    )
    return _PREFIX["reaction"] + h[:_HEXLEN]


def hypothesis_id(reaction_id_: str, capsule_version: str, parameter_digest: str) -> str:
    h = digest_fields("hypothesis", reaction_id_, capsule_version, parameter_digest)
    return _PREFIX["hypothesis"] + h[:_HEXLEN]


def candidate_id(hypothesis_id_: str, candidate_formula: str, publication_occurrence: str) -> str:
    h = digest_fields("candidate", hypothesis_id_, candidate_formula, publication_occurrence)
    return _PREFIX["candidate"] + h[:_HEXLEN]


def opportunity_cluster_id(member_hypothesis_ids: Iterable[str]) -> str:
    """Identity of a correlated hypothesis cluster.

    Membership is order-insensitive here (a cluster is a *set* of aliases), so members are sorted
    before hashing — distinct from the order-sensitive source-id sequences above.
    """
    members = sorted(set(member_hypothesis_ids))
    h = digest_fields("opportunity_cluster", len(members), *members)
    return _PREFIX["opportunity_cluster"] + h[:_HEXLEN]

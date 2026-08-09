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

from collections.abc import Iterable, Sequence

from .canonical import CanonicalError, canonical_json, digest_fields, digest_fields_v2, nfc

IDENTITY_SCHEMA_VERSION = "origin.identity.v1"
# CTRL-B01-003 / BLK-RC2-017: typed identity framing. v1 IDs remain valid under their version;
# v2 adds per-field type tags so cross-type values can never collide.
IDENTITY_SCHEMA_VERSION_V2 = "origin.identity.v2"
SUPPORTED_IDENTITY_VERSIONS = (IDENTITY_SCHEMA_VERSION, IDENTITY_SCHEMA_VERSION_V2)

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
    if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
        raise TypeError("identity source IDs must be an explicitly ordered sequence of strings")
    items = [_canonical_text(item, "source ID") for item in items]
    return digest_fields("seq", len(items), *items)


def _seq_digest_v2(items: Iterable[str]) -> str:
    if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
        raise TypeError("identity source IDs must be an explicitly ordered sequence of strings")
    items = [_canonical_text(item, "source ID") for item in items]
    return digest_fields_v2("seq", len(items), *items)


def _require_identity_version(version: str) -> None:
    if version not in SUPPORTED_IDENTITY_VERSIONS:
        raise TypeError(f"unknown identity schema version: {version!r}")


def _require_strings(**fields: str) -> None:
    for name, value in fields.items():
        _canonical_text(value, name)


def _canonical_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"identity field {name} must be a non-empty string")
    normalized = nfc(value)
    try:
        canonical_json(normalized)
    except (CanonicalError, UnicodeError, RecursionError) as exc:
        raise TypeError(f"identity field {name} is not canonical-wire encodable") from exc
    return normalized


def semantic_instance_id(
    formula_version: str,
    parameter_digest: str,
    venue_model: str,
    timeframe: str,
    *,
    identity_schema_version: str = IDENTITY_SCHEMA_VERSION,
) -> str:
    _require_identity_version(identity_schema_version)
    _require_strings(
        formula_version=formula_version,
        parameter_digest=parameter_digest,
        venue_model=venue_model,
        timeframe=timeframe,
    )
    if identity_schema_version == IDENTITY_SCHEMA_VERSION_V2:
        h = digest_fields_v2(
            "semantic_instance", identity_schema_version, formula_version, parameter_digest,
            venue_model, timeframe,
        )
    else:
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
    _require_identity_version(identity_schema_version)
    _require_strings(
        instrument_id=instrument_id,
        venue_model=venue_model,
        structure_kind=structure_kind,
        semantic_instance_id=semantic_instance_id_,
        direction=direction,
        original_geometry_digest=original_geometry_digest,
        identity_schema_version=identity_schema_version,
    )
    if identity_schema_version == IDENTITY_SCHEMA_VERSION_V2:
        h = digest_fields_v2(
            "structure", identity_schema_version, instrument_id, venue_model, structure_kind,
            semantic_instance_id_, direction, _seq_digest_v2(immutable_source_ids),
            original_geometry_digest,
        )
    else:
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
    *,
    identity_schema_version: str = IDENTITY_SCHEMA_VERSION,
) -> str:
    _require_identity_version(identity_schema_version)
    _require_strings(structure_id=structure_id_, reaction_formula=reaction_formula)
    if identity_schema_version == IDENTITY_SCHEMA_VERSION_V2:
        h = digest_fields_v2(
            "reaction", identity_schema_version, structure_id_, reaction_formula,
            _seq_digest_v2(trigger_source_ids),
        )
    else:
        h = digest_fields(
            "reaction",
            structure_id_,
            reaction_formula,
            _seq_digest(trigger_source_ids),
        )
    return _PREFIX["reaction"] + h[:_HEXLEN]


def hypothesis_id(
    reaction_id_: str,
    capsule_version: str,
    parameter_digest: str,
    *,
    identity_schema_version: str = IDENTITY_SCHEMA_VERSION,
) -> str:
    _require_identity_version(identity_schema_version)
    _require_strings(
        reaction_id=reaction_id_,
        capsule_version=capsule_version,
        parameter_digest=parameter_digest,
    )
    if identity_schema_version == IDENTITY_SCHEMA_VERSION_V2:
        h = digest_fields_v2(
            "hypothesis", identity_schema_version, reaction_id_, capsule_version, parameter_digest)
    else:
        h = digest_fields("hypothesis", reaction_id_, capsule_version, parameter_digest)
    return _PREFIX["hypothesis"] + h[:_HEXLEN]


def candidate_id(
    hypothesis_id_: str,
    candidate_formula: str,
    publication_occurrence: str,
    *,
    identity_schema_version: str = IDENTITY_SCHEMA_VERSION,
) -> str:
    _require_identity_version(identity_schema_version)
    _require_strings(
        hypothesis_id=hypothesis_id_,
        candidate_formula=candidate_formula,
        publication_occurrence=publication_occurrence,
    )
    if identity_schema_version == IDENTITY_SCHEMA_VERSION_V2:
        h = digest_fields_v2(
            "candidate", identity_schema_version, hypothesis_id_, candidate_formula,
            publication_occurrence)
    else:
        h = digest_fields("candidate", hypothesis_id_, candidate_formula, publication_occurrence)
    return _PREFIX["candidate"] + h[:_HEXLEN]


def opportunity_cluster_id(
    member_hypothesis_ids: Iterable[str],
    *,
    identity_schema_version: str = IDENTITY_SCHEMA_VERSION,
) -> str:
    """Identity of a correlated hypothesis cluster.

    Membership is order-insensitive here (a cluster is a *set* of aliases), so members are sorted
    before hashing — distinct from the order-sensitive source-id sequences above.
    """
    _require_identity_version(identity_schema_version)
    if isinstance(member_hypothesis_ids, (str, bytes)):
        raise TypeError("cluster members must be an iterable of IDs, not a scalar")
    supplied = list(member_hypothesis_ids)
    if not supplied:
        raise TypeError("cluster member hypothesis IDs must be non-empty strings")
    members = sorted({_canonical_text(member, "cluster member") for member in supplied})
    if identity_schema_version == IDENTITY_SCHEMA_VERSION_V2:
        h = digest_fields_v2("opportunity_cluster", identity_schema_version, len(members), *members)
    else:
        h = digest_fields("opportunity_cluster", len(members), *members)
    return _PREFIX["opportunity_cluster"] + h[:_HEXLEN]

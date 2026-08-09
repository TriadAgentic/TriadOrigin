"""B07 parameter-materialization battery: partition exhaustiveness, allowlist fail-closed law,
digest/scope/staleness refusal, defense-in-depth NOT_RATIFIED consistency, read faces."""

from __future__ import annotations

import copy
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.config import parameters as p  # noqa: E402
from triad_origin.structures import common  # noqa: E402


@pytest.fixture(scope="module")
def registry() -> p.ParameterRegistry:
    return p.load_registry()


# ---------------------------------------------------------------------------------------------
# Partition exhaustiveness (E25 disposition)
# ---------------------------------------------------------------------------------------------


def test_every_row_lands_in_exactly_one_bucket(registry):
    assert len(registry.materialized_ids()) == 51
    assert len(registry.refused_ids()) == 141
    assert len(set(registry.materialized_ids()) & set(registry.refused_ids())) == 0
    assert len(registry.materialized_ids()) + len(registry.refused_ids()) == 192


def test_status_counts_match_the_documented_partition(registry):
    counts = registry.status_counts()
    assert counts == {
        "BLOCKING_OWNER_DECISION": 8,
        "BLOCKING_RESEARCH_DECISION": 3,
        "CURRENT_VENDOR_REQUIRED": 4,
        "DECLARED_RC2": 8,
        "DECLARED_RC3": 3,
        "DECLARED_RC3_FROM_UNION": 1,
        "FORMULA_DERIVED": 1,
        "PROPOSED_RC2_MUST_RATIFY": 123,
        "RATIFIED_MAKER_LAW": 1,
        "RATIFIED_RC1": 21,
        "RATIFIED_RC3_OVERRIDE": 1,
        "SUPERSEDED": 3,
        "TARGET_FROM_TOPOLOGY": 8,
        "TARGET_NOT_PROVISIONED": 4,
        "VENUE_DERIVED": 2,
        "VERIFIED_AS_BUILT_2026_08_07": 1,
    }


def test_allowlist_and_refuse_set_are_disjoint_and_close_all_seen_statuses(registry):
    assert p.MATERIALIZABLE_STATUSES.isdisjoint(p.REFUSED_STATUSES)
    seen = set(registry.status_counts())
    assert seen <= (p.MATERIALIZABLE_STATUSES | p.REFUSED_STATUSES)


# ---------------------------------------------------------------------------------------------
# require() refusal law
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "parameter_id",
    ["PAR-070", "PAR-072", "PAR-076", "PAR-077", "PAR-118", "PAR-119", "PAR-120", "PAR-121"],
)
def test_blocking_owner_decision_rows_refuse(registry, parameter_id):
    with pytest.raises(p.ParameterRefusedError) as exc:
        registry.require(parameter_id)
    assert exc.value.status == "BLOCKING_OWNER_DECISION"
    assert exc.value.parameter_id == parameter_id


@pytest.mark.parametrize(
    "parameter_id", ["RC3-PAR-STRUCT-001", "RC3-PAR-STRUCT-002", "RC3-PAR-STRUCT-003"])
def test_blocking_research_decision_rows_refuse(registry, parameter_id):
    with pytest.raises(p.ParameterRefusedError) as exc:
        registry.require(parameter_id)
    assert exc.value.status == "BLOCKING_RESEARCH_DECISION"


def test_proposed_rc2_rows_refuse(registry):
    with pytest.raises(p.ParameterRefusedError) as exc:
        registry.require("PAR-051")  # ZONE_TTL, PROPOSED_RC2_MUST_RATIFY
    assert exc.value.status == "PROPOSED_RC2_MUST_RATIFY"


def test_superseded_rows_refuse_even_though_a_real_value_is_declared(registry):
    row = registry.row("PAR-024")
    assert row["declared_value"]  # a real (stale) value exists
    with pytest.raises(p.ParameterRefusedError) as exc:
        registry.require("PAR-024")
    assert exc.value.status == "SUPERSEDED"


def test_target_not_provisioned_rows_refuse(registry):
    with pytest.raises(p.ParameterRefusedError) as exc:
        registry.require("PAR-149")  # JETSTREAM_REPLICAS
    assert exc.value.status == "TARGET_NOT_PROVISIONED"


def test_refusal_names_the_bundles_own_failure_behavior(registry):
    row = registry.row("PAR-070")
    with pytest.raises(p.ParameterRefusedError) as exc:
        registry.require("PAR-070")
    assert row["failure_behavior"] in str(exc.value)


def test_materializable_status_rows_succeed(registry):
    row = registry.require("PAR-001")  # RATIFIED_RC1
    assert row["status"] == "RATIFIED_RC1"
    assert row["name"] == "PRICE_WIRE_TYPE"


def test_the_comparator_axes_are_materializable_declared_rc3(registry):
    cohort = registry.require("RC3-PAR-EXP-001")
    arm = registry.require("RC3-PAR-EXP-002")
    assert cohort["declared_value"] == "LEGACY_COMPARATOR|ORIGIN_CANDIDATE"
    assert arm["declared_value"] == "DETERMINISTIC_CONTROL|INTELLIGENCE_TREATMENT"


def test_unknown_id_raises_unknown_never_a_default(registry):
    with pytest.raises(p.ParameterUnknownError):
        registry.require("PAR-999999")
    with pytest.raises(p.ParameterUnknownError):
        registry.row("PAR-999999")


# ---------------------------------------------------------------------------------------------
# Digest (staleness) law
# ---------------------------------------------------------------------------------------------


def test_digest_is_deterministic_across_loads():
    a = p.load_registry()
    b = p.load_registry()
    assert a.parameter_digest == b.parameter_digest
    assert len(a.parameter_digest) == 64


def test_matching_expected_digest_passes_through(registry):
    row = registry.require("PAR-001", expected_digest=registry.parameter_digest)
    assert row["id"] == "PAR-001"


def test_stale_expected_digest_refuses_before_the_status_check(registry):
    # A stale caller must be refused even for a row that WOULD have materialized.
    with pytest.raises(p.ParameterDigestMismatchError):
        registry.require("PAR-001", expected_digest="0" * 64)
    # And even for a row that would have refused anyway — digest is checked first.
    with pytest.raises(p.ParameterDigestMismatchError):
        registry.require("PAR-070", expected_digest="0" * 64)


def test_digest_changes_if_a_row_changes(registry):
    rows = [dict(registry.row(pid)) for pid in registry.materialized_ids()]
    rows += [dict(registry.row(pid)) for pid in registry.refused_ids()]
    tampered = copy.deepcopy(rows)
    tampered[0] = dict(tampered[0])
    tampered[0]["declared_value"] = tampered[0]["declared_value"] + "_TAMPERED"
    original = p.ParameterRegistry(rows)
    changed = p.ParameterRegistry(tampered)
    assert original.parameter_digest != changed.parameter_digest


# ---------------------------------------------------------------------------------------------
# Scope law
# ---------------------------------------------------------------------------------------------


def test_matching_scope_passes_through(registry):
    row = registry.require("PAR-001", scope="Binance USD-M")
    assert row["id"] == "PAR-001"


def test_mismatched_scope_refuses(registry):
    with pytest.raises(p.ParameterScopeMismatchError):
        registry.require("PAR-001", scope="Hyperliquid")


def test_scope_check_runs_after_the_status_refusal_names_the_real_cause(registry):
    # A refused row refuses on ITS OWN status, not a scope mismatch — the caller learns the true
    # blocking reason first.
    with pytest.raises(p.ParameterRefusedError):
        registry.require("PAR-070", scope="anything not in the row")


# ---------------------------------------------------------------------------------------------
# Load-time defects (fail closed before any consumption)
# ---------------------------------------------------------------------------------------------


def test_missing_bundle_file_fails_closed(tmp_path):
    with pytest.raises(p.ParameterRegistryError):
        p.load_registry(tmp_path / "does_not_exist.json")


def test_empty_rows_fails_closed():
    with pytest.raises(p.ParameterRegistryError):
        p.ParameterRegistry([])


def test_missing_required_field_fails_closed():
    row = dict(p.load_registry().row("PAR-001"))
    del row["status"]
    with pytest.raises(p.ParameterRegistryError):
        p.ParameterRegistry([row])


def test_duplicate_id_fails_closed():
    row = dict(p.load_registry().row("PAR-001"))
    with pytest.raises(p.ParameterRegistryError):
        p.ParameterRegistry([row, dict(row)])


def test_unrecognized_status_fails_closed_never_silently_admitted():
    row = dict(p.load_registry().row("PAR-001"))
    row = dict(row)
    row["status"] = "SOME_FUTURE_STATUS_NOBODY_HAS_CATEGORIZED"
    with pytest.raises(p.ParameterRegistryError):
        p.ParameterRegistry([row])


def test_not_ratified_on_a_materializable_status_is_a_load_time_defect():
    row = dict(p.load_registry().row("PAR-001"))  # RATIFIED_RC1, a materializable status
    row = dict(row)
    row["declared_value"] = common.NOT_RATIFIED
    with pytest.raises(p.ParameterRegistryError):
        p.ParameterRegistry([row])


# ---------------------------------------------------------------------------------------------
# Read faces do not mutate cached truth
# ---------------------------------------------------------------------------------------------


def test_row_returns_a_detached_copy(registry):
    row = registry.row("PAR-001")
    row["status"] = "TAMPERED"
    assert registry.row("PAR-001")["status"] != "TAMPERED"


def test_require_returns_a_detached_copy(registry):
    row = registry.require("PAR-001")
    row["status"] = "TAMPERED"
    assert registry.require("PAR-001")["status"] != "TAMPERED"

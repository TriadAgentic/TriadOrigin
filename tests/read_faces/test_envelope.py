"""B08 read-face envelope battery: the ONE shared projection shape's honesty laws — the closed
status vocabulary (AVAILABLE vs UNAVAILABLE vs NOT_MEASURABLE, the last two distinct and each a
NAMED reason, never a fabricated zero / empty green), freshness carried as two separate timestamps
(as_of snapshot vs source watermark — never conflated into one liveness claim, LEV-V-0124),
declared completeness with a derived bounded/paginated truncation flag (the envelope owns no page
size — PAR-132..138 stay fail-closed), the read-of-record detached-copy law, the exact-key contract
(no vendored schema — validate() IS the contract), determinism, the no-clock structural law, and the
no-write-verb / capability-scan structural walls."""

from __future__ import annotations

import ast
import inspect
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin.read_faces import envelope as ev  # noqa: E402

# A representative caller-frozen snapshot instant + source watermark (UTC epoch microseconds); the
# envelope never reads a clock, so every timestamp is a literal fixture.
AS_OF = 1_700_000_000_000_000
WATERMARK = 1_699_999_999_000_000


# ---------------------------------------------------------------------------------------------
# The builders mint valid, self-validating envelopes
# ---------------------------------------------------------------------------------------------
def test_available_builds_a_valid_source_named_freshness_stamped_projection():
    env = ev.available(
        face="get_shadow_health",
        source="control.shadow_health.ShadowHealth.state",
        as_of_us=AS_OF,
        watermark_us=WATERMARK,
        plane=ev.PLANE_SHADOW,
        value={"dedupe_count": 0, "collision_count": 0, "contamination_count": 0},
    )
    ev.validate(env)  # does not raise
    d = env.to_dict()
    assert d["status"] == ev.STATUS_AVAILABLE
    assert d["source"] == "control.shadow_health.ShadowHealth.state"
    assert d["plane"] == "SHADOW"
    assert d["completeness"] == ev.COMPLETENESS_COMPLETE
    assert d["reason"] is None
    # a measured zero is an honest AVAILABLE value, not a fabricated one
    assert d["value"]["contamination_count"] == 0


def test_unavailable_and_not_measurable_are_distinct_named_absences_with_no_value():
    un = ev.unavailable(
        face="get_engine_lever_attestation",
        source="control.lever_registry.attestations",
        as_of_us=AS_OF,
        reason="VENUE_ENVIRONMENT_UNVERIFIED",
    )
    nm = ev.not_measurable(
        face="get_engine_inventory_reconciliation",
        source="control.shadow_health.v1.coverage",
        as_of_us=AS_OF,
        reason="SHADOW_HEALTH_COVERAGE_HAS_NO_MACHINE_SOURCE",
    )
    assert un.status == ev.STATUS_UNAVAILABLE
    assert nm.status == ev.STATUS_NOT_MEASURABLE
    assert un.status != nm.status  # the two honest-null statuses are never the same fact
    for env in (un, nm):
        d = env.to_dict()
        assert d["value"] is None  # never a fabricated zero / empty green
        assert d["reason"] != "" and d["reason"] is not None  # always a NAMED reason
        assert d["completeness"] == ev.COMPLETENESS_NOT_APPLICABLE
        assert d["returned"] == 0 and d["limit"] is None and d["cursor"] is None
        assert d["truncated"] is False


# ---------------------------------------------------------------------------------------------
# "no empty green": an absent source is never AVAILABLE(None); a non-AVAILABLE never carries a value
# ---------------------------------------------------------------------------------------------
def test_available_with_a_none_value_is_refused_no_empty_green():
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.available(
            face="get_four_plane_status",
            source="s",
            as_of_us=AS_OF,
            value=None,
        )


def test_unavailable_requires_a_named_reason_never_silent():
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.unavailable(face="f", source="s", as_of_us=AS_OF, reason="")


def test_a_non_available_envelope_carrying_a_value_is_refused():
    bad = ev.ReadFaceEnvelope(
        face="f",
        status=ev.STATUS_UNAVAILABLE,
        source="s",
        as_of_us=AS_OF,
        completeness=ev.COMPLETENESS_NOT_APPLICABLE,
        reason="SOURCE_ABSENT",
        value={"count": 0},  # a fabricated zero smuggled onto an UNAVAILABLE — must refuse
    )
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(bad)


def test_an_available_envelope_may_not_name_a_reason():
    bad = ev.ReadFaceEnvelope(
        face="f",
        status=ev.STATUS_AVAILABLE,
        source="s",
        as_of_us=AS_OF,
        completeness=ev.COMPLETENESS_COMPLETE,
        reason="SOMETHING",
        value={"ok": True},
    )
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(bad)


# ---------------------------------------------------------------------------------------------
# Freshness: as_of and watermark carried SEPARATELY, watermark honest-null (LEV-V-0124)
# ---------------------------------------------------------------------------------------------
def test_as_of_and_watermark_are_separate_timestamps_never_conflated():
    env = ev.available(
        face="get_engine_inventory_reconciliation",
        source="cross_machine_census",
        as_of_us=AS_OF,
        watermark_us=WATERMARK,
        value={"fresh_paper": AS_OF, "stale_relay": WATERMARK},
    )
    d = env.to_dict()
    # both present, distinct, and not merged into one green liveness number
    assert d["as_of_us"] == AS_OF
    assert d["watermark_us"] == WATERMARK
    assert d["as_of_us"] != d["watermark_us"]


def test_watermark_may_be_honest_null_when_the_source_has_no_watermark():
    env = ev.available(
        face="get_engine_lever_registry",
        source="control.lever_registry.levers",
        as_of_us=AS_OF,
        watermark_us=None,
        value={"revision": 0, "levers": {}},
    )
    assert env.to_dict()["watermark_us"] is None


def test_as_of_us_must_be_a_non_negative_epoch_integer():
    for bad_as_of in (-1, 1.5, True, "1700"):
        with pytest.raises(ev.ReadFaceEnvelopeError):
            ev.unavailable(face="f", source="s", as_of_us=bad_as_of, reason="X")


# ---------------------------------------------------------------------------------------------
# Bounded / paginated: cursor <=> truncated <=> TRUNCATED; the envelope owns no page-size default
# ---------------------------------------------------------------------------------------------
def test_a_cursor_derives_truncated_and_truncated_completeness():
    env = ev.available(
        face="get_engine_lever_history",
        source="journal.MANIFEST_ACCEPTED events",
        as_of_us=AS_OF,
        value=[{"revision": 1}, {"revision": 2}],
        returned=2,
        limit=2,
        cursor="offset:2",
    )
    d = env.to_dict()
    assert d["truncated"] is True
    assert d["completeness"] == ev.COMPLETENESS_TRUNCATED
    assert d["cursor"] == "offset:2"


def test_a_complete_page_carries_no_cursor_and_reads_complete():
    env = ev.available(
        face="get_engine_lever_history",
        source="journal.MANIFEST_ACCEPTED events",
        as_of_us=AS_OF,
        value=[{"revision": 1}],
        returned=1,
        limit=500,
    )
    d = env.to_dict()
    assert d["truncated"] is False
    assert d["completeness"] == ev.COMPLETENESS_COMPLETE
    assert d["cursor"] is None
    # the caller-supplied bound is recorded verbatim; the envelope invented no default
    assert d["limit"] == 500


def test_returned_may_not_exceed_the_applied_bound():
    bad = ev.ReadFaceEnvelope(
        face="f",
        status=ev.STATUS_AVAILABLE,
        source="s",
        as_of_us=AS_OF,
        completeness=ev.COMPLETENESS_COMPLETE,
        returned=6,
        limit=5,
        value=[],
    )
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(bad)


def test_a_truncated_page_without_a_cursor_is_refused():
    bad = ev.ReadFaceEnvelope(
        face="f",
        status=ev.STATUS_AVAILABLE,
        source="s",
        as_of_us=AS_OF,
        completeness=ev.COMPLETENESS_TRUNCATED,
        returned=5,
        limit=5,
        cursor=None,
        truncated=True,
        value=[],
    )
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(bad)


def test_returned_and_limit_reject_bool_and_float():
    for kwargs in (
        dict(returned=True),
        dict(returned=1.0),
        dict(returned=-1),
        dict(limit=True),
        dict(limit=-1),
    ):
        with pytest.raises(ev.ReadFaceEnvelopeError):
            ev.available(face="f", source="s", as_of_us=AS_OF, value=[], **kwargs)


# ---------------------------------------------------------------------------------------------
# The closed vocabularies
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("plane", list(ev.PLANES_ALL) + [None])
def test_every_declared_plane_and_none_is_accepted(plane):
    env = ev.available(
        face="get_four_plane_status", source="s", as_of_us=AS_OF, value={"n": 0}, plane=plane
    )
    assert env.to_dict()["plane"] == plane


def test_an_unknown_plane_is_refused():
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.available(
            face="f", source="s", as_of_us=AS_OF, value={"n": 0}, plane="MAINNET"
        )


def test_status_and_completeness_vocabularies_are_closed():
    bad_status = ev.ReadFaceEnvelope(
        face="f", status="OK", source="s", as_of_us=AS_OF,
        completeness=ev.COMPLETENESS_COMPLETE, value={},
    )
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(bad_status)
    bad_completeness = ev.ReadFaceEnvelope(
        face="f", status=ev.STATUS_AVAILABLE, source="s", as_of_us=AS_OF,
        completeness="PARTIAL", value={},
    )
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(bad_completeness)


def test_four_market_planes_are_the_rc4_populations_in_order():
    assert ev.PLANES == ("SHADOW", "PAPER", "TESTNET", "LIVE")
    assert ev.CONTROL_PLANE not in ev.PLANES  # the control plane is not a market population


# ---------------------------------------------------------------------------------------------
# The exact-key contract + version integrity (validate() IS the contract; no vendored schema)
# ---------------------------------------------------------------------------------------------
def test_a_missing_or_extra_key_is_refused():
    good = ev.available(face="f", source="s", as_of_us=AS_OF, value={"n": 0}).to_dict()
    missing = dict(good)
    del missing["source"]
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(missing)
    extra = dict(good)
    extra["surprise"] = 1
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(extra)


def test_a_wrong_evidence_view_version_is_refused():
    d = ev.available(face="f", source="s", as_of_us=AS_OF, value={"n": 0}).to_dict()
    d["evidence_view_version"] = "origin.evidence_view.v1"
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(d)


def test_evidence_view_version_is_an_internal_shape_not_a_vendored_contract_id():
    # W25's "evidence_view.v2" is a logical binding, not a contracts/ schema (row E37). The
    # internal version string must therefore NOT be a registered vendored contract id.
    assert ev.EVIDENCE_VIEW_VERSION == "origin.evidence_view.v2"
    assert ev.EVIDENCE_VIEW_VERSION not in contracts.known_contracts()
    assert not ev.EVIDENCE_VIEW_VERSION.startswith("triad.")


def test_validate_rejects_a_non_mapping():
    with pytest.raises(ev.ReadFaceEnvelopeError):
        ev.validate(["not", "a", "dict"])


# ---------------------------------------------------------------------------------------------
# Read of record: detached copies; from_dict round-trip
# ---------------------------------------------------------------------------------------------
def test_to_dict_is_a_detached_copy_a_caller_mutation_never_corrupts_the_envelope():
    env = ev.available(face="f", source="s", as_of_us=AS_OF, value={"levers": {"a": 1}})
    view = env.to_dict()
    view["value"]["levers"]["a"] = 999
    view["status"] = "TAMPERED"
    fresh = env.to_dict()
    assert fresh["value"]["levers"]["a"] == 1
    assert fresh["status"] == ev.STATUS_AVAILABLE


def test_available_ingress_is_detached_a_later_mutation_of_the_source_value_never_leaks_in():
    source_value = {"levers": {"a": 1}}
    env = ev.available(face="f", source="s", as_of_us=AS_OF, value=source_value)
    source_value["levers"]["a"] = 999  # mutate the caller's object after the build
    assert env.to_dict()["value"]["levers"]["a"] == 1


def test_from_dict_round_trips_a_validated_view():
    original = ev.available(
        face="get_engine_lever_registry",
        source="control.lever_registry.levers",
        as_of_us=AS_OF,
        watermark_us=WATERMARK,
        plane=ev.CONTROL_PLANE,
        value={"revision": 3, "levers": {"engine_a": {"value": "OFF"}}},
        returned=1,
        limit=500,
    )
    rebuilt = ev.from_dict(original.to_dict())
    assert rebuilt == original
    assert rebuilt.to_dict() == original.to_dict()


# ---------------------------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------------------------
def test_two_identical_builds_are_equal_and_serialize_identically():
    a = ev.unavailable(face="f", source="s", as_of_us=AS_OF, reason="R")
    b = ev.unavailable(face="f", source="s", as_of_us=AS_OF, reason="R")
    assert a == b
    assert a.to_dict() == b.to_dict()


# ---------------------------------------------------------------------------------------------
# The no-clock structural law: every builder takes an explicit as_of_us, no default
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("builder", [ev.available, ev.unavailable, ev.not_measurable])
def test_no_builder_defaults_the_snapshot_instant_time_is_always_caller_supplied(builder):
    params = inspect.signature(builder).parameters
    assert "as_of_us" in params
    assert params["as_of_us"].default is inspect.Parameter.empty


# ---------------------------------------------------------------------------------------------
# The no-write-verb / no-control-verb structural wall
# ---------------------------------------------------------------------------------------------
def test_module_exposes_no_issuance_admission_or_activation_verb():
    banned_prefixes = ("issue_", "admit_", "select_authority", "arm_", "activate_", "switch_")
    banned_substrings = ("armed", "authorized", "live_", "credential", "venue")
    for name in dir(ev):
        if name.startswith("_"):
            continue
        low = name.lower()
        for pre in banned_prefixes:
            assert not name.startswith(pre), f"{name} looks like a write verb"
        for sub in banned_substrings:
            assert sub not in low, f"{name} contains the forbidden token {sub!r}"


# ---------------------------------------------------------------------------------------------
# Capability scan: the module is import-isolated and the whole runtime stays keyless/clockless
# ---------------------------------------------------------------------------------------------
def test_module_imports_only_allowed_and_relative_roots():
    src = (ROOT / "src" / "triad_origin" / "read_faces" / "envelope.py").read_text()
    tree = ast.parse(src)
    allowed = {"__future__", "copy", "dataclasses", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in allowed or root == "triad_origin", alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import inside the package
            root = (node.module or "").split(".")[0]
            assert root in allowed or root == "triad_origin", node.module


def test_forbidden_capability_scan_stays_green_with_the_new_read_face():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_no_forbidden_capabilities.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

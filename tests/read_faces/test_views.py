"""B08 W25-views battery: the nine read-only evidence projection views (offsets · watermarks ·
quality · lineage · funnel · divergence · replay · receipt · readiness) as honest, bounded
projections over the evidence substrate — each returns the shared evidence envelope naming its
source/freshness/completeness; UNAVAILABLE (source absent) and NOT_MEASURABLE (source present, fact
uncomputable) are distinct named absences, never a fabricated zero (RC3 W25 "no empty green"); the
candidate funnel carries named zeros (a conjunct never failing is a measured 0); divergence keeps an
unrecognized class explicit NOT_MEASURABLE (no auto-resolution, RC3-AC-WIRE-W08A-05); the readiness
view (row CTRL-B08-001) adds the four still-open evidence dimensions yet NEVER claims more than
READY_NO_AUTHORITY; and the no-clock / no-write-verb / capability-scan / poison-envelope structural
walls hold."""

from __future__ import annotations

import ast
import inspect
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import timings  # noqa: E402
from triad_origin.control import comparator, shadow_ledger  # noqa: E402
from triad_origin.health import Readiness  # noqa: E402
from triad_origin.read_faces import envelope as ev  # noqa: E402
from triad_origin.read_faces import views  # noqa: E402
from triad_origin.structures import candidate_publisher as cp  # noqa: E402

# Caller-frozen snapshot instant + source watermark (UTC epoch microseconds); a view never reads a
# clock, so every timestamp is a literal fixture.
AS_OF = 1_700_000_000_000_000
WATERMARK = 1_699_999_999_000_000

# The scanner's closed allowed import-root set (verbatim, tools/verify_no_forbidden_capabilities.py).
_ALLOWED_ROOTS = frozenset({
    "__future__", "collections", "copy", "dataclasses", "decimal", "enum", "fcntl", "functools",
    "hashlib", "json", "jsonschema", "math", "os", "pathlib", "re", "threading", "typing",
    "unicodedata",
})


# ---------------------------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------------------------
def _offsets():
    return {
        "p2": {"input_segment": "seg-b", "input_offset": 7, "output_segment": "out-b",
               "output_offset": 3, "state_seq": 9, "last_transition_id": "t9"},
        "p1": {"input_segment": "seg-a", "input_offset": 4},  # partial — missing fields named
    }


def _watermarks():
    return {
        "p1": {"allowed_lateness_us": 1000, "completed_through_us": 500,
               "clocks": {"event_time_us": 400}},
        "p2": {"allowed_lateness_us": 1000, "completed_through_us": -1},  # not yet advanced
    }


def _refused_event(*conjuncts):
    return {"event_kind": cp.CANDIDATE_PUBLICATION_REFUSED, "candidate_id": "c",
            "reason_code": shadow_ledger.MARKER_SHADOW_UNTRADEABLE,
            "failed_conjuncts": sorted(conjuncts)}


def _published_event(cid="c"):
    return {"event_kind": cp.CANDIDATE_PUBLISHED, "candidate_id": cid, "transition_id": "t"}


def _real_divergence_record():
    # Drive the REAL comparator: an absent control + a present ORIGIN_CANDIDATE treatment is an
    # EXTRA divergence (the treatment must carry its expected engine_cohort label).
    return comparator.compare_engine_cohort(
        None, {"candidate_id": "c1", "engine_cohort": "ORIGIN_CANDIDATE"},
        input_offset=3, evaluated_at_us=AS_OF, divergence_id="d1")


def _replay_receipt(**overrides):
    base = {
        "receipt_id": "r1", "fidelity_class": "EXACT", "input_offsets": [[0, 4]],
        "input_segment_hashes": ["h0", "h1"], "output_segment_hashes": ["o0"],
        "checkpoint_identity": "genesis", "run_seed": "s", "platform": "p",
        "state_checksums": {"final": "abc"}, "divergence_links": [], "signer": "sig",
        "test_suite_result": {"passed": True}}
    base.update(overrides)
    return base


def _receipt(**overrides):
    base = {
        "receipt_id": "B08", "scope": {"milestone": "B08"}, "result": "PASS",
        "builder": "alice", "reviewer": "bob", "evidence_ids": ["e1", "e2"],
        "evidence_sha256s": ["s1", "s2"], "observed_at_us": 10, "expires_at_us": 20,
        "signature": "sig"}
    base.update(overrides)
    return base


ALL_VIEW_CALLS = (
    lambda: views.get_offsets_view(partitions=_offsets(), as_of_us=AS_OF, watermark_us=WATERMARK),
    lambda: views.get_watermarks_view(watermarks=_watermarks(), as_of_us=AS_OF),
    lambda: views.get_quality_view(quality={"finalized": True}, as_of_us=AS_OF),
    lambda: views.get_lineage_view(
        structures_state={"last_event_id": "e", "structures": {"s1": {"state": "CONFIRMED"}}},
        as_of_us=AS_OF),
    lambda: views.get_funnel_view(events=[_published_event(), _refused_event("side")], as_of_us=AS_OF),
    lambda: views.get_divergence_view(records=[_real_divergence_record()], as_of_us=AS_OF),
    lambda: views.get_replay_view(receipts=[_replay_receipt()], as_of_us=AS_OF),
    lambda: views.get_receipt_view(receipt=_receipt(), as_of_us=AS_OF),
    lambda: views.get_readiness_view(bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=AS_OF),
)

# Each view's "absent source" call (must return a validating UNAVAILABLE envelope).
ABSENT_SOURCE_CALLS = (
    lambda: views.get_offsets_view(partitions=None, as_of_us=AS_OF),
    lambda: views.get_watermarks_view(watermarks=None, as_of_us=AS_OF),
    lambda: views.get_quality_view(quality=None, as_of_us=AS_OF),
    lambda: views.get_lineage_view(structures_state=None, as_of_us=AS_OF),
    lambda: views.get_funnel_view(events=None, as_of_us=AS_OF),
    lambda: views.get_divergence_view(records=None, as_of_us=AS_OF),
    lambda: views.get_replay_view(receipts=None, as_of_us=AS_OF),
    lambda: views.get_receipt_view(receipt=None, as_of_us=AS_OF),
    lambda: views.get_readiness_view(bootstrap_readiness=None, as_of_us=AS_OF),
)


# =============================================================================================
# Cross-view: envelope validity, determinism, detachment, and named source/freshness/completeness
# =============================================================================================
@pytest.mark.parametrize("call", ALL_VIEW_CALLS)
def test_every_view_returns_a_validating_envelope(call):
    env = call()
    ev.validate(env)  # raises on any law violation
    view = env.to_dict()
    # RC3 W25: "response names plane, source, freshness and completeness."
    assert isinstance(view["source"], str) and view["source"] != ""
    assert view["as_of_us"] == AS_OF
    assert view["completeness"] in ev.COMPLETENESS_VOCAB
    assert view["face"] in views.VIEW_NAMES


@pytest.mark.parametrize("call", ABSENT_SOURCE_CALLS)
def test_absent_source_is_unavailable_never_a_fabricated_zero(call):
    env = call()
    ev.validate(env)
    assert env.status == ev.STATUS_UNAVAILABLE
    assert env.value is None  # no empty green: an absent dependency carries no value
    assert env.reason  # a named absence


@pytest.mark.parametrize("call", ALL_VIEW_CALLS)
def test_views_are_deterministic(call):
    assert call().to_dict() == call().to_dict()


def test_read_of_record_detaches_from_input_and_output():
    offsets = _offsets()
    env = views.get_offsets_view(partitions=offsets, as_of_us=AS_OF)
    # Mutating a returned view never corrupts a later projection (detached deep copy).
    view = env.to_dict()
    view["value"]["partitions"].clear()
    assert len(env.to_dict()["value"]["partitions"]) == 2
    # Mutating the caller's input after the call never changes the already-projected value.
    offsets["p3"] = {"input_offset": 99}
    assert env.to_dict()["value"]["partition_count"] == 2


# =============================================================================================
# offsets
# =============================================================================================
def test_offsets_projects_fields_and_names_missing_ones():
    env = views.get_offsets_view(partitions=_offsets(), as_of_us=AS_OF)
    rows = {r["partition"]: r for r in env.value["partitions"]}
    assert rows["p2"]["missing_fields"] == []
    # p1 supplied only input_segment + input_offset — the rest are NAMED missing, never fabricated 0.
    assert set(rows["p1"]["missing_fields"]) == {
        "output_segment", "output_offset", "state_seq", "last_transition_id"}
    assert rows["p1"]["offsets"]["output_offset"] is None


def test_offsets_bounded_and_paginated_preserves_order():
    parts = {f"p{i}": {"input_offset": i} for i in range(5)}
    first = views.get_offsets_view(partitions=parts, as_of_us=AS_OF, limit=2)
    assert first.returned == 2 and first.cursor is not None
    second = views.get_offsets_view(partitions=parts, as_of_us=AS_OF, limit=2, after=first.cursor)
    third = views.get_offsets_view(partitions=parts, as_of_us=AS_OF, limit=2, after=second.cursor)
    seen = [r["partition"] for r in first.value["partitions"]] \
        + [r["partition"] for r in second.value["partitions"]] \
        + [r["partition"] for r in third.value["partitions"]]
    assert seen == sorted(parts) and third.cursor is None


# =============================================================================================
# watermarks
# =============================================================================================
def test_watermark_unadvanced_is_not_measurable_never_a_fabricated_zero():
    env = views.get_watermarks_view(watermarks=_watermarks(), as_of_us=AS_OF)
    rows = {r["partition"]: r for r in env.value["partitions"]}
    assert rows["p1"]["completed_through_us"]["status"] == ev.STATUS_AVAILABLE
    assert rows["p1"]["completed_through_us"]["value"] == 500 and rows["p1"]["advanced"] is True
    # The -1 sentinel is "no finalized event yet" — NOT_MEASURABLE, never a fabricated 0 timestamp.
    assert rows["p2"]["completed_through_us"]["status"] == ev.STATUS_NOT_MEASURABLE
    assert "value" not in rows["p2"]["completed_through_us"] and rows["p2"]["advanced"] is False
    # both timestamps carried; the clocks are echoed verbatim, never re-derived.
    assert rows["p1"]["clocks"] == {"event_time_us": 400}


# =============================================================================================
# quality — ORIGIN computes no quality
# =============================================================================================
def test_quality_absent_empty_and_present_are_three_distinct_honest_states():
    absent = views.get_quality_view(quality=None, as_of_us=AS_OF)
    empty = views.get_quality_view(quality={}, as_of_us=AS_OF)
    present = views.get_quality_view(quality={"finalized": True}, as_of_us=AS_OF)
    assert absent.status == ev.STATUS_UNAVAILABLE          # no attestation at all
    assert empty.status == ev.STATUS_NOT_MEASURABLE        # present but no quality fact
    assert present.status == ev.STATUS_AVAILABLE
    assert absent.status != empty.status != present.status
    # The load-bearing honesty: the value is the producer's stamp, echoed verbatim, never computed.
    assert present.value["attested_quality"] == {"finalized": True}
    assert present.value["attested_not_computed"] is True


# =============================================================================================
# lineage — missing lineage is NOT_MEASURABLE, distinct from an absent source
# =============================================================================================
def test_lineage_single_structure_found_and_missing_is_not_measurable():
    state = {"last_event_id": "e9", "structures": {"s1": {"state": "CONFIRMED"}}}
    found = views.get_lineage_view(structures_state=state, as_of_us=AS_OF, structure_id="s1")
    assert found.status == ev.STATUS_AVAILABLE and found.value["lineage"]["state"] == "CONFIRMED"
    missing = views.get_lineage_view(structures_state=state, as_of_us=AS_OF, structure_id="nope")
    # source present, this structure has no lineage ⇒ NOT_MEASURABLE (never estimated)…
    assert missing.status == ev.STATUS_NOT_MEASURABLE
    # …distinct from the absent-source case, which is UNAVAILABLE.
    absent = views.get_lineage_view(structures_state=None, as_of_us=AS_OF)
    assert absent.status == ev.STATUS_UNAVAILABLE
    assert missing.status != absent.status


def test_lineage_lists_structures_bounded():
    state = {"structures": {f"s{i}": {"state": "FORMED"} for i in range(4)}}
    env = views.get_lineage_view(structures_state=state, as_of_us=AS_OF, limit=3)
    assert env.returned == 3 and env.cursor is not None
    assert env.value["structure_count"] == 4


# =============================================================================================
# funnel — named zeros + poison safety
# =============================================================================================
def test_funnel_counts_and_named_zeros_over_the_twelve_conjuncts():
    events = [
        _published_event(), _published_event(),
        _refused_event("side"), _refused_event("side", "finite_numbers")]
    env = views.get_funnel_view(events=events, as_of_us=AS_OF)
    assert env.value["published"] == 2 and env.value["refused"] == 2
    assert env.value["shadow_untradeable_refusals"] == 2
    fbc = env.value["failed_by_conjunct"]
    # every one of the 12 tradeability conjuncts is a NAMED key…
    assert set(fbc) == set(shadow_ledger.TRADEABILITY_REQUIREMENTS)
    assert fbc["side"] == 2 and fbc["finite_numbers"] == 1
    # …and a conjunct that never failed is a measured 0 (a named zero), never omitted.
    assert fbc["horizon"] == 0 and "horizon" in fbc


def test_funnel_is_poison_safe_and_empty_is_a_measured_zero():
    # a malformed event is counted unclassified, never raised on (poison-envelope law)…
    env = views.get_funnel_view(events=[42, {"event_kind": "SOMETHING_ELSE"}, None], as_of_us=AS_OF)
    assert env.status == ev.STATUS_AVAILABLE and env.value["unclassified"] == 3
    # …and a present-but-empty stream is a measured zero funnel (AVAILABLE), distinct from absent.
    empty = views.get_funnel_view(events=[], as_of_us=AS_OF)
    assert empty.status == ev.STATUS_AVAILABLE and empty.value["published"] == 0
    absent = views.get_funnel_view(events=None, as_of_us=AS_OF)
    assert absent.status == ev.STATUS_UNAVAILABLE


def test_funnel_only_the_caller_envelope_shape_may_raise():
    with pytest.raises(ev.ReadFaceEnvelopeError):
        views.get_funnel_view(events={"not": "a list"}, as_of_us=AS_OF)


# =============================================================================================
# divergence — real records, per-class roll-up, no auto-resolution of ambiguous classes
# =============================================================================================
def test_divergence_rolls_up_real_records_by_class_with_named_zeros():
    record = _real_divergence_record()
    assert record["divergence_class"] == "EXTRA"  # sanity: the comparator produced a real record
    env = views.get_divergence_view(records=[record], as_of_us=AS_OF)
    assert set(env.value["by_class"]) == set(comparator.DIVERGENCE_CLASSES)
    assert env.value["by_class"]["EXTRA"] == 1 and env.value["by_class"]["MISSING"] == 0
    assert env.value["not_measurable"] == 0


def test_divergence_unrecognized_class_stays_not_measurable_no_auto_resolution():
    ambiguous = {"divergence_id": "x", "divergence_class": "MYSTERY"}
    env = views.get_divergence_view(records=[ambiguous, 99], as_of_us=AS_OF)
    # an unrecognized / unparseable record is explicit NOT_MEASURABLE — never dropped, never
    # re-classified into a known bucket (RC3-AC-WIRE-W08A-05 "no auto-resolution").
    assert env.value["not_measurable"] == 2
    assert all(v == 0 for v in env.value["by_class"].values())
    rows = env.value["records"]
    assert rows[0]["status"] == ev.STATUS_NOT_MEASURABLE
    assert rows[0]["divergence_class"] == "MYSTERY"  # the raw class is surfaced, not erased


def test_divergence_bounded_and_absent_vs_empty():
    records = [_real_divergence_record() for _ in range(3)]
    env = views.get_divergence_view(records=records, as_of_us=AS_OF, limit=2)
    assert env.returned == 2 and env.cursor is not None and env.value["records_considered"] == 3
    assert views.get_divergence_view(records=None, as_of_us=AS_OF).status == ev.STATUS_UNAVAILABLE
    assert views.get_divergence_view(records=[], as_of_us=AS_OF).status == ev.STATUS_AVAILABLE


# =============================================================================================
# replay
# =============================================================================================
def test_replay_projects_fields_counts_and_names_missing():
    env = views.get_replay_view(
        receipts=[_replay_receipt(), _replay_receipt(receipt_id=None)], as_of_us=AS_OF)
    r0, r1 = env.value["receipts"]
    assert r0["receipt_id"] == "r1" and r0["input_segment_hashes_count"] == 2
    assert r0["test_suite_result_present"] is True and r0["missing_fields"] == []
    # a receipt missing an identity field NAMES it, never fabricates it.
    assert "receipt_id" in r1["missing_fields"]
    assert views.get_replay_view(receipts=None, as_of_us=AS_OF).status == ev.STATUS_UNAVAILABLE


# =============================================================================================
# receipt
# =============================================================================================
def test_receipt_projects_declared_result_and_as_of_freshness():
    fresh = views.get_receipt_view(receipt=_receipt(expires_at_us=AS_OF + 1), as_of_us=AS_OF)
    assert fresh.value["declared_result"] == "PASS"  # echoed, not a re-derived verdict
    assert fresh.value["expired_as_of"]["status"] == ev.STATUS_AVAILABLE
    assert fresh.value["expired_as_of"]["value"] is False
    assert fresh.value["builder_reviewer_distinct"] is True
    # expiry before the snapshot instant reads expired (an honest freshness fact).
    stale = views.get_receipt_view(receipt=_receipt(expires_at_us=AS_OF - 1), as_of_us=AS_OF)
    assert stale.value["expired_as_of"]["value"] is True
    # a non-integer expiry is NOT_MEASURABLE, never a guessed freshness.
    unk = views.get_receipt_view(receipt=_receipt(expires_at_us=None), as_of_us=AS_OF)
    assert unk.value["expired_as_of"]["status"] == ev.STATUS_NOT_MEASURABLE
    assert views.get_receipt_view(receipt=None, as_of_us=AS_OF).status == ev.STATUS_UNAVAILABLE


# =============================================================================================
# readiness — row CTRL-B08-001: adds evidence, never authority
# =============================================================================================
def test_readiness_r00_has_all_four_evidence_dimensions_honest_null():
    env = views.get_readiness_view(bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=AS_OF)
    dims = env.value["evidence_dimensions"]
    # The exact CTRL-B08-001 gap: with no evidence supplied, each dimension is honest UNAVAILABLE,
    # never a fabricated green.
    assert {"source_freshness", "coverage", "lease_validity", "estate_activation"} == set(dims)
    assert all(d["status"] == ev.STATUS_UNAVAILABLE for d in dims.values())
    assert env.value["authority"] == "NONE"
    assert env.value["ceiling"] == "READY_NO_AUTHORITY"


def test_readiness_never_claims_more_than_ready_no_authority_even_when_evidence_supplied():
    env = views.get_readiness_view(
        bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=AS_OF,
        source_freshness={"age_ms": 10, "bound": "runtime_attestation_max_age_ms"},
        coverage={"reconciled": 5, "presented": 5},
        lease_validity={"state": "ACTIVE"},
        estate_activation={"venue_environment": "OFF"})
    dims = env.value["evidence_dimensions"]
    assert all(d["status"] == ev.STATUS_AVAILABLE for d in dims.values())
    # THE NARROWNESS LAW: a read face ADDS evidence, never AUTHORITY — the ceiling holds regardless.
    assert env.value["authority"] == "NONE"
    assert env.value["ceiling"] == "READY_NO_AUTHORITY"
    assert env.value["operational_readiness_claimed"] is False
    # no authority-escalation token can appear anywhere in the serialized view.
    blob = json.dumps(env.to_dict())
    for token in ("AUTHORIZED", "ARMED", "OPERATIONAL", "ACTIVATED"):
        assert token not in blob, token


def test_readiness_coverage_is_an_exact_integer_pair_no_float():
    ok = views.get_readiness_view(
        bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=AS_OF,
        coverage={"reconciled": 3, "presented": 4})
    cov = ok.value["evidence_dimensions"]["coverage"]
    assert cov["status"] == ev.STATUS_AVAILABLE and cov["fully_reconciled"] is False
    assert isinstance(cov["reconciled"], int) and isinstance(cov["presented"], int)
    bad = views.get_readiness_view(
        bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=AS_OF,
        coverage={"reconciled": 3})  # malformed pair
    assert bad.value["evidence_dimensions"]["coverage"]["status"] == ev.STATUS_NOT_MEASURABLE


def test_readiness_freshness_known_bound_is_measurable_unknown_is_not():
    known = views.get_readiness_view(
        bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=AS_OF,
        source_freshness={"age_ms": timings.timing_ms("runtime_attestation_max_age_ms") + 1,
                          "bound": "runtime_attestation_max_age_ms"})
    fr = known.value["evidence_dimensions"]["source_freshness"]
    assert fr["status"] == ev.STATUS_AVAILABLE and fr["stale"] is True
    # an unknown bound is NOT_MEASURABLE (never raised on — the bound name is caller content).
    unk = views.get_readiness_view(
        bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=AS_OF,
        source_freshness={"age_ms": 1, "bound": "not_a_real_bound"})
    assert unk.value["evidence_dimensions"]["source_freshness"]["status"] == ev.STATUS_NOT_MEASURABLE


def test_readiness_unrecognized_bootstrap_is_not_measurable_not_a_crash():
    env = views.get_readiness_view(bootstrap_readiness="TOTALLY_READY", as_of_us=AS_OF)
    # a caller-supplied unknown readiness string is content, not a crash — NOT_MEASURABLE, and it is
    # NEVER coerced into a recognized Readiness state.
    facet = env.value["bootstrap_readiness"]
    assert facet["status"] == ev.STATUS_NOT_MEASURABLE and facet["raw"] == "TOTALLY_READY"
    assert facet["raw"] not in {r.value for r in Readiness}
    assert views.get_readiness_view(bootstrap_readiness=None, as_of_us=AS_OF).status \
        == ev.STATUS_UNAVAILABLE


# =============================================================================================
# Cross-view structural walls: read-only / capability scan / no-clock / bounded-cursor / no-write
# =============================================================================================
def test_capability_scanner_passes_over_the_read_face_package():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_no_forbidden_capabilities.py")],
        cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_views_module_imports_only_allowed_roots_or_relative():
    source = (ROOT / "src" / "triad_origin" / "read_faces" / "views.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    saw_relative = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in _ALLOWED_ROOTS, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:  # a relative triad_origin import — allowed
                saw_relative = True
                continue
            assert (node.module or "").split(".")[0] in _ALLOWED_ROOTS, node.module
    assert saw_relative


def test_no_write_verb_or_credential_in_the_public_surface():
    banned_prefixes = ("issue_", "admit_", "select_authority", "arm_", "activate_", "place_",
                       "submit_", "send_", "create_", "cancel_", "amend_")
    forbidden_ids = ("api_key", "api_secret", "arm_token", "private_key", "secret_key",
                     "venue_credentials")
    for name in dir(views):
        if name.startswith("_"):
            continue
        assert not name.startswith(banned_prefixes), name
        assert name not in forbidden_ids, name


def test_no_view_name_carries_an_authority_or_venue_substring():
    # a read face must not read as "more ready"/authority/venue in its very name.
    forbidden_substrings = ("armed", "authorized", "live_", "credential", "venue")
    for name in dir(views):
        if name.startswith("_"):
            continue
        assert not any(sub in name.lower() for sub in forbidden_substrings), name


@pytest.mark.parametrize("view", (
    views.get_offsets_view, views.get_watermarks_view, views.get_quality_view,
    views.get_lineage_view, views.get_funnel_view, views.get_divergence_view,
    views.get_replay_view, views.get_receipt_view, views.get_readiness_view))
def test_every_view_takes_as_of_us_with_no_default(view):
    # the no-clock law, structural: freshness is a required caller input, never a read clock.
    param = inspect.signature(view).parameters["as_of_us"]
    assert param.default is inspect.Parameter.empty
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_a_bad_cursor_fails_closed_named():
    with pytest.raises(ev.ReadFaceEnvelopeError):
        views.get_offsets_view(partitions=_offsets(), as_of_us=AS_OF, after="not-a-cursor")
    with pytest.raises(ev.ReadFaceEnvelopeError):
        views.get_offsets_view(partitions=_offsets(), as_of_us=AS_OF, limit=-1)

"""CO-09 status-and-checklist truth tests.

One canonical status source; PRESENCE never reads as CLOSURE.  These tests prove:

* regeneration is byte-deterministic from the same committed inputs;
* a hand edit to a generated status/checklist page fails CI (the drift-lock covers both docs);
* no ``passed``/closed/checked-box wording attaches to a presence-only fact;
* the typed artifact-presence states (ARTIFACT_PRESENT / HISTORICAL_RECEIPT_PRESERVED /
  AUTHORITY_OPEN) render, with a preserved historical receipt reading HISTORICAL_RECEIPT_PRESERVED;
* every generated status page embeds the self-identifying provider head + run-id block, and the
  embedded head reflects the REAL committed generation context (never a fabricated provider run id).
"""

from __future__ import annotations

import copy
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import closure_control as cc  # noqa: E402


def _error(code: str):
    return pytest.raises(cc.ClosureControlError, match=rf"^{code}:")


def _projection() -> dict:
    semantics = cc.load_canonical_object(ROOT / cc.SEMANTICS_REL)
    semantics_digest = cc.compute_envelope_digest(semantics, cc.SEMANTICS_DOMAIN)
    status_events = cc.load_canonical_object(ROOT / cc.STATUS_EVENTS_REL)
    status_events_schema = cc.load_json_object(ROOT / cc.STATUS_EVENTS_SCHEMA_REL)
    task_bindings = cc.load_canonical_object(ROOT / cc.TASK_BINDING_REL)
    events_digest, states = cc.validate_status_events(
        status_events, status_events_schema, semantics, semantics_digest
    )
    task_digest = cc.compute_envelope_digest(task_bindings, cc.TASK_BINDING_DOMAIN)
    return cc.derive_status_projection(
        semantics, semantics_digest, status_events, events_digest,
        task_bindings, task_digest, states, root=ROOT,
    )


def test_regeneration_is_byte_deterministic_from_the_same_inputs() -> None:
    first = cc.write_generated_outputs(ROOT)
    generated = (
        ROOT / cc.STATUS_REL,
        ROOT / cc.STATUS_DOC_REL,
        ROOT / cc.CHECKLIST_DOC_REL,
    )
    snapshot = {path: path.read_bytes() for path in generated}
    second = cc.write_generated_outputs(ROOT)
    assert first == second
    assert {path: path.read_bytes() for path in generated} == snapshot
    # The committed tree already matches a fresh regeneration (no drift after --write).
    assert cc.check_all(ROOT)["open_blockers"] > 0


@pytest.mark.parametrize("doc_rel", [cc.STATUS_DOC_REL, cc.CHECKLIST_DOC_REL])
def test_hand_edit_of_a_generated_status_page_fails_ci(
    tmp_path: pathlib.Path, doc_rel: pathlib.Path
) -> None:
    # Mirror the committed control tree into an isolated root so the fixture edit is safe.
    dest = tmp_path
    for rel in (
        cc.SEMANTICS_SCHEMA_REL, cc.SEMANTICS_REL, cc.STATUS_SCHEMA_REL, cc.STATUS_REL,
        cc.STATUS_EVENTS_SCHEMA_REL, cc.STATUS_EVENTS_REL, cc.TASK_BINDING_SCHEMA_REL,
        cc.TASK_BINDING_REL, cc.B00R_POLICY_REL, cc.STATUS_DOC_REL, cc.CHECKLIST_DOC_REL,
        cc.GENERATION_CONTEXT_SCHEMA_REL, cc.GENERATION_CONTEXT_REL,
        cc.BUILD_LEDGER_REL, cc.BUILD_LEDGER_REVIEW_REL, cc.BUILD_LEDGER_REVIEW_SUBJECT_REL,
    ):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / rel).read_bytes())
    for legacy in cc.EXPECTED_LEGACY_BINDINGS.values():
        receipt_rel = legacy[3]
        if receipt_rel is not None:
            target = dest / receipt_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / receipt_rel).read_bytes())

    assert cc.check_all(dest)["open_blockers"] > 0  # the mirror is clean

    edited = dest / doc_rel
    edited.write_bytes(edited.read_bytes() + b"\nhand edit\n")
    expected_code = (
        "GENERATED_STATUS_DOCUMENT_DRIFT"
        if doc_rel == cc.STATUS_DOC_REL
        else "GENERATED_CHECKLIST_DOCUMENT_DRIFT"
    )
    with _error(expected_code):
        cc.check_all(dest)


@pytest.mark.parametrize("doc_rel", [cc.STATUS_DOC_REL, cc.CHECKLIST_DOC_REL])
def test_no_passed_or_closure_wording_attaches_to_a_presence_only_fact(
    doc_rel: pathlib.Path,
) -> None:
    text = (ROOT / doc_rel).read_text(encoding="utf-8")
    # No presence-only fact may ever be worded as a pass, a close, or a checked box.
    assert re.search(r"(?i)\bpass(?:ed|es|ing)?\b", text) is None
    assert "[x]" not in text
    assert "✅" not in text


def test_typed_artifact_presence_states_render_and_a_receipt_reads_preserved() -> None:
    projection = _projection()
    presence = projection["payload"]["artifact_presence"]
    states = {row["presence_state"] for row in presence}
    assert states == set(cc.PRESENCE_STATES)  # all three typed states present

    by_ref = {row["artifact_ref"]: row for row in presence}
    # A historical receipt file that exists reads HISTORICAL_RECEIPT_PRESERVED — never a pass.
    b07 = by_ref["evidence/receipts/B07.json"]
    assert b07["presence_state"] == "HISTORICAL_RECEIPT_PRESERVED"
    assert b07["subject_kind"] == "HISTORICAL_RECEIPT"
    # A required-but-unmerged source receipt reads AUTHORITY_OPEN.
    assert (
        by_ref["evidence/receipts/B00R.g2.receipt.v3.json"]["presence_state"]
        == "AUTHORITY_OPEN"
    )
    # A present controlling input reads ARTIFACT_PRESENT.
    assert (
        by_ref["docs/control/closure/closure_semantics.v1.json"]["presence_state"]
        == "ARTIFACT_PRESENT"
    )

    text = (ROOT / cc.STATUS_DOC_REL).read_text(encoding="utf-8")
    assert "## Artifact presence" in text
    assert "Presence is not closure" in text
    for state in cc.PRESENCE_STATES:
        assert f"`{state}`" in text


def test_provider_head_and_run_id_block_is_embedded_and_real() -> None:
    projection = _projection()
    context_ref = projection["payload"]["generation_context"]
    assert context_ref["path"] == cc.GENERATION_CONTEXT_REL.as_posix()
    assert context_ref["provider_run_id_state"] == "AUTHORITY_OPEN"
    assert context_ref["provider_run_id_value"] is None

    committed = cc.load_canonical_object(ROOT / cc.GENERATION_CONTEXT_REL)
    head = committed["payload"]["provider_head"]
    assert context_ref["provider_head_kind"] == head["kind"]
    assert context_ref["provider_head_value"] == head["value"]
    # The head is REAL: either a 40-hex git sha, or the honest AUTHORITY_OPEN placeholder.
    if head["kind"] == "GIT_HEAD_SHA1":
        assert re.fullmatch(r"[0-9a-f]{40}", head["value"])
    else:
        assert head["kind"] == "AUTHORITY_OPEN"
        assert head["value"] is None

    for doc_rel in (cc.STATUS_DOC_REL, cc.CHECKLIST_DOC_REL):
        text = (ROOT / doc_rel).read_text(encoding="utf-8")
        assert "Generated against provider head:" in text
        assert "Provider run id: `AUTHORITY_OPEN`" in text
        assert context_ref["digest_sha256"] in text


def test_status_rejects_an_injected_presence_row_and_a_run_id_overclaim() -> None:
    semantics = cc.load_canonical_object(ROOT / cc.SEMANTICS_REL)
    status_schema = cc.load_json_object(ROOT / cc.STATUS_SCHEMA_REL)
    semantics_digest = cc.compute_envelope_digest(semantics, cc.SEMANTICS_DOMAIN)
    status = cc.load_canonical_object(ROOT / cc.STATUS_REL)

    # A closure-worded presence row (even in the closed enum shape) is refused.
    injected = copy.deepcopy(status)
    injected["payload"]["artifact_presence"].append({
        "artifact_ref": "evidence/receipts/B07.json",
        "presence_state": "ARTIFACT_PRESENT",
        "subject_kind": "HISTORICAL_RECEIPT",
    })
    injected["digest"]["value"] = cc.compute_envelope_digest(injected, cc.STATUS_DOMAIN)
    with _error("STATUS_ARTIFACT_PRESENCE_MISMATCH"):
        cc.validate_status(injected, status_schema, semantics, semantics_digest, root=ROOT)

    # The generation-context reference must match the committed context.
    tampered = copy.deepcopy(status)
    tampered["payload"]["generation_context"]["provider_head_value"] = "0" * 40
    tampered["digest"]["value"] = cc.compute_envelope_digest(tampered, cc.STATUS_DOMAIN)
    with _error("STATUS_GENERATION_CONTEXT_MISMATCH"):
        cc.validate_status(tampered, status_schema, semantics, semantics_digest, root=ROOT)


def test_generation_context_never_fabricates_a_run_id_or_head() -> None:
    schema = cc.load_json_object(ROOT / cc.GENERATION_CONTEXT_SCHEMA_REL)

    # A fabricated provider run id value is refused by the schema (the slot is pinned to null).
    overclaim = cc.build_generation_context("a" * 40)
    overclaim["payload"]["provider_run_id"]["value"] = "run-12345"
    overclaim["digest"]["value"] = cc.compute_envelope_digest(
        overclaim, cc.GENERATION_CONTEXT_DOMAIN
    )
    with pytest.raises(cc.ClosureControlError):
        cc.validate_generation_context(overclaim, schema)

    # Defense-in-depth: even behind a permissive schema, the validator's own guard refuses a
    # fabricated run id value.
    permissive = copy.deepcopy(schema)
    permissive["properties"]["payload"]["properties"]["provider_run_id"]["properties"][
        "value"
    ] = {"type": ["null", "string"]}
    with _error("GENERATION_CONTEXT_RUN_ID_OVERCLAIM"):
        cc.validate_generation_context(overclaim, permissive)

    # A GIT_HEAD_SHA1 kind without a real 40-hex sha is refused.
    fake_head = cc.build_generation_context("a" * 40)
    fake_head["payload"]["provider_head"]["value"] = "not-a-real-sha"
    fake_head["digest"]["value"] = cc.compute_envelope_digest(
        fake_head, cc.GENERATION_CONTEXT_DOMAIN
    )
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_generation_context(fake_head, schema)

    # Absent git → honest AUTHORITY_OPEN head, never a fabricated sha.
    absent = cc.build_generation_context(None)
    assert cc.validate_generation_context(absent, schema)
    assert absent["payload"]["provider_head"]["kind"] == "AUTHORITY_OPEN"
    assert absent["payload"]["provider_head"]["value"] is None

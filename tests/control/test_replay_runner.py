"""B07 replay-runner battery: same-code replay identity (twice, byte-identical), checkpoint-resume
receipt identity vs a cold full-tape run, exact-offset accounting, schema self-validation,
fail-closed identity-field/inputs-type checks, zero side effect (no clock/randomness leakage)."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from triad_origin.checkpoint import Checkpoint  # noqa: E402
from triad_origin.control import replay_runner as rr  # noqa: E402
from triad_origin.journal import ReplayContext, replay  # noqa: E402
from triad_origin.transition import TransitionResult  # noqa: E402


class _CounterMachine:
    """A trivial deterministic machine: counts inputs, emits one TICK event per input."""

    def initial_state(self) -> dict:
        return {"count": 0}

    def transition(self, state, envelope, params, quality):
        new_state = dict(state)
        new_state["count"] = state["count"] + 1
        return TransitionResult(new_state, ({"event_kind": "TICK", "n": new_state["count"]},))


IDENTITY_KWARGS = dict(
    partition="toy",
    build_commit="b" * 40,
    config_bundle_sha256="0" * 64,
    contract_manifest_sha256="1" * 64,
    parameter_digest="2" * 64,
    instrument_digest="3" * 64,
    platform="linux-x86_64",
    run_seed="seed-1",
    receipt_id="rcpt-1",
    signer="signer-1",
)


def _inputs(n: int) -> list:
    return [{"event_id": f"e{i}"} for i in range(n)]


# ---------------------------------------------------------------------------------------------
# Replay identity (run twice, byte-identical)
# ---------------------------------------------------------------------------------------------


def test_two_independent_runs_produce_byte_identical_receipts():
    m = _CounterMachine()
    inputs = _inputs(5)
    r1 = rr.run_replay(m, inputs, {}, **IDENTITY_KWARGS)
    r2 = rr.run_replay(m, inputs, {}, **IDENTITY_KWARGS)
    assert r1 == r2


def test_receipt_is_schema_valid_against_the_vendored_contract():
    m = _CounterMachine()
    payload = rr.run_replay(m, _inputs(3), {}, **IDENTITY_KWARGS)
    contracts.validate_payload(rr.REPLAY_RECEIPT_SCHEMA, payload)  # raises if invalid


def test_different_inputs_produce_different_state_checksums():
    m = _CounterMachine()
    r1 = rr.run_replay(m, _inputs(3), {}, **IDENTITY_KWARGS)
    r2 = rr.run_replay(m, _inputs(4), {}, **IDENTITY_KWARGS)
    assert r1["state_checksums"] != r2["state_checksums"]
    assert r1["input_segment_hashes"] != r2["input_segment_hashes"]


# ---------------------------------------------------------------------------------------------
# Checkpoint-resume identity vs a cold full-tape run
# ---------------------------------------------------------------------------------------------


def _checkpoint_after(machine, inputs_prefix, partition):
    journal, _ = replay(machine, inputs_prefix, {}, partition=partition)
    records = journal.records()
    last = records[-1]
    projection = journal.project()
    return Checkpoint(
        partition=partition,
        state=projection,
        input_segment="seg-a",
        input_offset=len(inputs_prefix) - 1,
        input_prefix_digest=sha256_hex(canonical_json(inputs_prefix)),
        last_domain_event_id=inputs_prefix[-1]["event_id"],
        highest_producer_epoch=0,
        projection_checksum=sha256_hex(canonical_json(projection)),
        output_segment="out-a",
        output_offset=len(inputs_prefix) - 1,
        state_seq=last.state_seq,
        last_transition_id=last.transition_id,
        digests={"build": "b" * 64, "config": "c" * 64, "contract": "d" * 64,
                 "parameter": "e" * 64, "instrument": "f" * 64},
    ).sealed()


def _context_for(cp: Checkpoint) -> ReplayContext:
    return ReplayContext(
        input_segment=cp.input_segment, input_prefix_digest=cp.input_prefix_digest,
        output_segment=cp.output_segment, output_offset=cp.output_offset,
        highest_producer_epoch=cp.highest_producer_epoch, state_seq=cp.state_seq,
        last_transition_id=cp.last_transition_id, projection_checksum=cp.projection_checksum,
        digests=cp.digests,
    )


def test_checkpoint_resumed_receipt_state_matches_a_cold_full_tape_run():
    m = _CounterMachine()
    full = _inputs(6)
    cold = rr.run_replay(m, full, {}, **IDENTITY_KWARGS)

    cp = _checkpoint_after(m, full[:3], "toy")
    ctx = _context_for(cp)
    resumed_kwargs = dict(IDENTITY_KWARGS)
    resumed_kwargs["receipt_id"] = "rcpt-resumed"
    resumed = rr.run_replay(
        m, full, {}, resume_from=cp, resume_context=ctx, **resumed_kwargs)

    assert cold["state_checksums"] == resumed["state_checksums"]


def test_cold_and_resumed_offsets_are_exact():
    m = _CounterMachine()
    full = _inputs(6)
    cold = rr.run_replay(m, full, {}, **IDENTITY_KWARGS)
    assert cold["input_offsets"] == [[0, 6]]
    assert cold["checkpoint_identity"] == "genesis"

    cp = _checkpoint_after(m, full[:3], "toy")
    ctx = _context_for(cp)
    resumed_kwargs = dict(IDENTITY_KWARGS)
    resumed_kwargs["receipt_id"] = "rcpt-resumed"
    resumed = rr.run_replay(
        m, full, {}, resume_from=cp, resume_context=ctx, **resumed_kwargs)
    assert resumed["input_offsets"] == [[3, 6]]
    assert resumed["checkpoint_identity"] == cp.state_checksum


def test_resuming_with_a_short_tape_refuses():
    m = _CounterMachine()
    full = _inputs(6)
    cp = _checkpoint_after(m, full[:3], "toy")
    ctx = _context_for(cp)
    with pytest.raises(rr.ReplayRunnerError):
        rr.run_replay(m, full[:2], {}, resume_from=cp, resume_context=ctx, **IDENTITY_KWARGS)


# ---------------------------------------------------------------------------------------------
# Fail-closed identity/input checks
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("field", list(IDENTITY_KWARGS))
def test_missing_or_empty_identity_field_refuses(field):
    m = _CounterMachine()
    kwargs = dict(IDENTITY_KWARGS)
    kwargs[field] = ""
    with pytest.raises(rr.ReplayRunnerError):
        rr.run_replay(m, _inputs(3), {}, **kwargs)


def test_non_list_inputs_refuses():
    m = _CounterMachine()
    with pytest.raises(rr.ReplayRunnerError):
        rr.run_replay(m, "not-a-list", {}, **IDENTITY_KWARGS)  # type: ignore[arg-type]


def test_empty_fidelity_class_refuses():
    m = _CounterMachine()
    with pytest.raises(rr.ReplayRunnerError):
        rr.run_replay(m, _inputs(3), {}, fidelity_class="", **IDENTITY_KWARGS)


def test_a_raising_machine_wraps_into_replay_runner_error():
    class BrokenMachine:
        def initial_state(self):
            return {}

        def transition(self, state, envelope, params, quality):
            raise ValueError("boom")

    with pytest.raises(rr.ReplayRunnerError):
        rr.run_replay(BrokenMachine(), _inputs(1), {}, **IDENTITY_KWARGS)


# ---------------------------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------------------------


def test_optional_test_suite_result_and_divergence_links_pass_through():
    m = _CounterMachine()
    payload = rr.run_replay(
        m, _inputs(2), {}, test_suite_result={"passed": 10, "failed": 0},
        divergence_links=["div-1"], **IDENTITY_KWARGS)
    assert payload["test_suite_result"] == {"passed": 10, "failed": 0}
    assert payload["divergence_links"] == ["div-1"]


def test_omitted_optional_fields_default_to_empty_never_null():
    m = _CounterMachine()
    payload = rr.run_replay(m, _inputs(2), {}, **IDENTITY_KWARGS)
    assert payload["test_suite_result"] == {}
    assert payload["divergence_links"] == []

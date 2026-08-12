"""Registry and fail-closed behavior guards for the always-current E2E walk."""

from __future__ import annotations

import subprocess

import pytest

from tools import e2e_audit


EXPECTED_STAGES = (
    "contracts_manifest",
    "golden_vectors",
    "identity_walk",
    "ledger_walk",
    "journal_replay_walk",
    "checkpoint_walk",
    "epoch_fence",
    "anchor_walk",
    "fence_restore_walk",
    "timing_law",
    "identity_v2_walk",
    "lever_law_walk",
    "receipt_walk",
    "capability_boundary",
    "build_ledger",
    "combined_dag",
    "structures_walk",
    "structure_flow_walk",
    "binding_walk",
    "four_plane_walk",
    "candidate_publisher_walk",
    "b07_control_plane_walk",
    "b00r_governance_evidence",
    "b01c_contract_binding_promotion",
    "c0_closure_control",
    "b02c_security_boundary",
)


def _completed(returncode: int, output: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=output, stderr="")


def test_registry_is_exactly_the_26_stage_walk() -> None:
    assert tuple(name for name, _doc in e2e_audit.STAGES) == EXPECTED_STAGES
    assert len({name for name, _doc in e2e_audit.STAGES}) == 26


def test_c0_stage_proves_structural_green_is_not_closure_green(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []
    results = iter((
        _completed(
            0,
            "OK: C0 closure control canonical; 103 open blockers; "
            "OFF/OFF/OFF/LIVE; no closure claim\n",
        ),
        _completed(
            2,
            "CLOSURE_NOT_READY: 103 open blockers; no closure claim\n",
        ),
    ))

    def fake_run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append((script, args))
        return next(results)

    monkeypatch.setattr(e2e_audit, "_run_tool_result", fake_run)
    e2e_audit.c0_closure_control()

    assert calls == [
        ("closure_control.py", ("--check",)),
        ("closure_control.py", ("--require-closure-ready",)),
    ]


@pytest.mark.parametrize(
    ("structural", "ready", "message"),
    (
        (_completed(1, "FAIL"), _completed(2, "CLOSURE_NOT_READY: 3 open blockers"),
         "did not validate"),
        (_completed(0, "OK: 0 open blockers; no closure claim"),
         _completed(2, "CLOSURE_NOT_READY: 3 open blockers"), "positive open-blocker"),
        (_completed(0, "OK: 3 open blockers"),
         _completed(2, "CLOSURE_NOT_READY: 3 open blockers"), "no-closure-claim"),
        (_completed(0, "OK: 3 open blockers; no closure claim"),
         _completed(0, "closure ready"), "with exit 2"),
        (_completed(0, "OK: 3 open blockers; no closure claim"),
         _completed(2, "argument refused: 3 open blockers"), "CLOSURE_NOT_READY"),
        (_completed(0, "OK: 3 open blockers; no closure claim"),
         _completed(2, "CLOSURE_NOT_READY"), "positive open-blocker"),
    ),
)
def test_c0_stage_rejects_false_green_or_ambiguous_results(
    monkeypatch,
    structural: subprocess.CompletedProcess[str],
    ready: subprocess.CompletedProcess[str],
    message: str,
) -> None:
    results = iter((structural, ready))
    monkeypatch.setattr(e2e_audit, "_run_tool_result", lambda *_args: next(results))
    with pytest.raises(AssertionError, match=message):
        e2e_audit.c0_closure_control()

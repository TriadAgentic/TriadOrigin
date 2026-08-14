"""CO-02 — fail-closed tests for the canonical milestone registry, crosswalk and validator.

Every test either proves a committed invariant on the real artifacts or plants a defect in an
isolated copy and proves the validator refuses it.  Nothing here closes a milestone; the
registry is a derived, non-evidence projection of the canonical closure route.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import verify_milestone_registry as vmr  # noqa: E402

from triad_origin.canonical import canonical_json, loads_canonical  # noqa: E402


# --- fixtures -------------------------------------------------------------------------------
COPY_RELS = [
    vmr.REGISTRY_REL,
    vmr.CROSSWALK_REL,
    vmr.SEMANTICS_REL,
    vmr.INVALIDATION_REL,
    vmr.GENERATION_LEDGER_REL,
    vmr.PLAN_BREAKDOWN_REL,
    # allowlisted historical files carrying legitimate bare-B rows
    pathlib.Path("docs/control/b00r_policy.v1.json"),
    pathlib.Path("docs/control/b00r_policy.v2.json"),
    pathlib.Path("docs/governance/decisions/DEC-B00-REPAIR-001.json"),
]


@pytest.fixture()
def isolated_root(tmp_path: pathlib.Path) -> pathlib.Path:
    for rel in COPY_RELS:
        src = ROOT / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return tmp_path


def _load(root: pathlib.Path, rel: pathlib.Path) -> dict:
    return loads_canonical((root / rel).read_bytes())


def _rewrap_registry(root: pathlib.Path, payload: dict) -> None:
    artifact = vmr.wrap_artifact(vmr.REGISTRY_DOMAIN, vmr.REGISTRY_SCHEMA, payload)
    (root / vmr.REGISTRY_REL).write_bytes(canonical_json(artifact))


# --- committed-artifact truths ---------------------------------------------------------------
def test_committed_registry_verifies_green() -> None:
    assert vmr.verify(ROOT) == []


def test_registry_is_exact_canonical_json_with_recomputable_digest() -> None:
    for rel, domain, schema in (
        (vmr.REGISTRY_REL, vmr.REGISTRY_DOMAIN, vmr.REGISTRY_SCHEMA),
        (vmr.CROSSWALK_REL, vmr.CROSSWALK_DOMAIN, vmr.CROSSWALK_SCHEMA),
    ):
        raw = (ROOT / rel).read_bytes()
        artifact = loads_canonical(raw)
        assert canonical_json(artifact) == raw
        assert artifact["digest"]["value"] == vmr.artifact_digest(
            domain, schema, vmr.ARTIFACT_VERSION, artifact["payload"]
        )


def test_regeneration_is_byte_deterministic(isolated_root: pathlib.Path) -> None:
    before_r = (isolated_root / vmr.REGISTRY_REL).read_bytes()
    before_x = (isolated_root / vmr.CROSSWALK_REL).read_bytes()
    vmr.write_artifacts(isolated_root)
    assert (isolated_root / vmr.REGISTRY_REL).read_bytes() == before_r
    assert (isolated_root / vmr.CROSSWALK_REL).read_bytes() == before_x


def test_origin_repair_track_carries_the_full_repair_lane() -> None:
    registry = _load(ROOT, vmr.REGISTRY_REL)["payload"]
    origin = sorted(
        row["milestone_id"] for row in registry["rows"] if row["track_id"] == "ORIGIN_REPAIR"
    )
    assert origin == sorted(vmr.ORIGIN_REPAIR_IDS)


def test_legacy_program_rows_are_immutable_and_never_receipt_targets() -> None:
    registry = _load(ROOT, vmr.REGISTRY_REL)["payload"]
    legacy = [row for row in registry["rows"] if row["track_id"] == "LEGACY_PROGRAM"]
    assert sorted(r["milestone_id"] for r in legacy) == sorted(vmr.LEGACY_PROGRAM_IDS)
    for row in legacy:
        assert row["permitted_terminal"] is None
        assert "no new receipt" in row["receipt_law"]


def test_b10_lane_is_nonzero_with_real_rows() -> None:
    registry = _load(ROOT, vmr.REGISTRY_REL)["payload"]
    (b10,) = [
        row
        for row in registry["rows"]
        if row["track_id"] == "ORIGIN_REPAIR" and row["milestone_id"] == "B10"
    ]
    lane = b10["lane"]
    assert len(lane["tasks"]) >= 1
    assert len(lane["criteria"]) >= 1
    assert len(lane["verifications"]) >= 1
    assert lane["receipt_anchor_law"]["required_result"] == "PASS_REPOSITORY_SAFE_HOLD"


def test_b10_bare_id_collision_is_documented_not_resolved_by_invention() -> None:
    registry = _load(ROOT, vmr.REGISTRY_REL)["payload"]
    (legacy_b10,) = [
        row
        for row in registry["rows"]
        if row["track_id"] == "LEGACY_PROGRAM" and row["milestone_id"] == "B10"
    ]
    sources = {entry["source"] for entry in legacy_b10["bare_id_collision"]}
    assert any("legacy_crosswalk" in s for s in sources)
    assert any("01_MILESTONE_BREAKDOWN" in s for s in sources)


def test_future_expansion_row_is_pending_owner() -> None:
    registry = _load(ROOT, vmr.REGISTRY_REL)["payload"]
    (row,) = [r for r in registry["rows"] if r["row_kind"] == "FUTURE_EXPANSION_DEFERRED"]
    assert row["ratified_by"] == "PENDING-OWNER"
    assert row["signature_state"] == "PENDING_SIGNATURE"
    assert row["refusal_while_pending"] == "FUTURE_EXPANSION_ROW_UNRATIFIED_NO_TASK_MAY_BIND"


def test_underivable_facts_are_explicit_unresolved_rows() -> None:
    registry = _load(ROOT, vmr.REGISTRY_REL)["payload"]
    states = {row["state"] for row in registry["unresolved_rows"]}
    assert "UNRESOLVED_NOT_DERIVABLE_FROM_THIS_REPOSITORY" in states
    assert vmr.UNRESOLVED_SCOPE in states
    legacy_b08 = [
        row
        for row in registry["rows"]
        if row["track_id"] == "LEGACY_PROGRAM" and row["milestone_id"] in ("B08", "B09", "B10")
    ]
    for row in legacy_b08:
        assert row["scope_digest"] == vmr.UNRESOLVED_SCOPE


def test_crosswalk_covers_every_canonical_legacy_ref_with_lawful_dispositions() -> None:
    crosswalk = _load(ROOT, vmr.CROSSWALK_REL)["payload"]
    semantics = _load(ROOT, vmr.SEMANTICS_REL)["payload"]
    assert sorted(r["legacy_ref"] for r in crosswalk["rows"]) == sorted(
        r["legacy_ref"] for r in semantics["legacy_crosswalk"]
    )
    for row in crosswalk["rows"]:
        assert row["co02_disposition"] in ("PRESERVED_HISTORICAL", "SUPERSEDED_BY")
        if row["co02_disposition"] == "SUPERSEDED_BY":
            assert row["superseded_by"], row["legacy_ref"]
        else:
            assert row["superseded_by"] is None


def test_registry_posture_is_safe_hold_and_never_claims_closure() -> None:
    for rel in (vmr.REGISTRY_REL, vmr.CROSSWALK_REL):
        payload = _load(ROOT, rel)["payload"]
        assert payload["activation_result"] == "DENIED_SAFE_HOLD"
        assert payload["closure_claimed"] is False
        assert payload["levers"] == vmr.LEVERS


# --- planted-defect refusals ------------------------------------------------------------------
def test_hand_edit_fails_verification(isolated_root: pathlib.Path) -> None:
    registry = _load(isolated_root, vmr.REGISTRY_REL)
    registry["payload"]["rows"][0]["owner"] = "hand-edited owner"
    _rewrap_registry(isolated_root, registry["payload"])
    problems = vmr.verify(isolated_root)
    assert any("differ from deterministic regeneration" in p for p in problems)


def test_duplicate_composite_key_fails(isolated_root: pathlib.Path) -> None:
    registry = _load(isolated_root, vmr.REGISTRY_REL)
    registry["payload"]["rows"].append(dict(registry["payload"]["rows"][0]))
    _rewrap_registry(isolated_root, registry["payload"])
    problems = vmr.verify(isolated_root)
    assert any("COMPOSITE_KEY_DUPLICATE" in p for p in problems)


def test_dag_cycle_fails(isolated_root: pathlib.Path) -> None:
    registry = _load(isolated_root, vmr.REGISTRY_REL)
    rows = registry["payload"]["rows"]
    by_id = {
        row["milestone_id"]: row
        for row in rows
        if row["row_kind"] == "MACHINE_CANONICAL_PROJECTION" and row["track_id"] == "ORIGIN_REPAIR"
    }
    # Point B00R_G2's predecessor at B10 (which transitively depends on B00R_G2): a cycle.
    by_id["B00R_G2"]["predecessor"] = by_id["B10"]["composite_identity"]
    _rewrap_registry(isolated_root, registry["payload"])
    problems = vmr.verify(isolated_root)
    assert any("DAG_CYCLE" in p for p in problems)


def test_closure_route_disagreement_fails_registry_never_wins(
    isolated_root: pathlib.Path,
) -> None:
    registry = _load(isolated_root, vmr.REGISTRY_REL)
    for row in registry["payload"]["rows"]:
        if row["row_kind"] == "MACHINE_CANONICAL_PROJECTION" and row["milestone_id"] == "B01C":
            row["scope_text"] = "a different scope claim"
    _rewrap_registry(isolated_root, registry["payload"])
    problems = vmr.verify(isolated_root)
    assert any("CLOSURE_DISAGREEMENT" in p for p in problems)


def test_zeroed_b10_lane_fails(isolated_root: pathlib.Path) -> None:
    registry = _load(isolated_root, vmr.REGISTRY_REL)
    for row in registry["payload"]["rows"]:
        if row["track_id"] == "ORIGIN_REPAIR" and row["milestone_id"] == "B10":
            row["lane"]["tasks"] = []
    _rewrap_registry(isolated_root, registry["payload"])
    problems = vmr.verify(isolated_root)
    assert any("B10_LANE_ZERO" in p for p in problems)


def test_new_bare_b_receipt_row_is_not_constructible(isolated_root: pathlib.Path) -> None:
    rogue = isolated_root / "docs" / "governance" / "new_receipt_row.json"
    rogue.write_text(json.dumps({"milestone": "B03", "result": "PASS"}), encoding="utf-8")
    problems = vmr.verify(isolated_root)
    assert any("NEW_BARE_B_ROW" in p and "B03" in p for p in problems)


def test_composite_keyed_row_is_lawful_where_a_bare_row_is_not(
    isolated_root: pathlib.Path,
) -> None:
    lawful = isolated_root / "docs" / "governance" / "composite_row.json"
    lawful.write_text(
        json.dumps(
            {
                "track_id": "ORIGIN_REPAIR",
                "milestone_id": "B03C",
                "scope_digest": "e27e4fd37d6dbf04159477a9fdb1ffa6f5d2838eb109085f1ccde09980a8ae24",
            }
        ),
        encoding="utf-8",
    )
    problems = vmr.verify(isolated_root)
    assert not any("NEW_BARE_B_ROW" in p for p in problems)


def test_preserved_historical_files_are_allowlisted_not_flagged() -> None:
    problems: list[str] = []
    vmr._check_bare_b_scan(ROOT, problems)
    assert problems == []


def test_ratifying_future_expansion_without_amendment_fails(
    isolated_root: pathlib.Path,
) -> None:
    registry = _load(isolated_root, vmr.REGISTRY_REL)
    for row in registry["payload"]["rows"]:
        if row["row_kind"] == "FUTURE_EXPANSION_DEFERRED":
            row["ratified_by"] = "someone@example.com"
    _rewrap_registry(isolated_root, registry["payload"])
    problems = vmr.verify(isolated_root)
    assert any("PENDING-OWNER" in p for p in problems)


def test_closure_claiming_status_fails(isolated_root: pathlib.Path) -> None:
    registry = _load(isolated_root, vmr.REGISTRY_REL)
    for row in registry["payload"]["rows"]:
        if row["milestone_id"] == "B01C" and row["track_id"] == "ORIGIN_REPAIR":
            row["status"] = "PASSED"
    _rewrap_registry(isolated_root, registry["payload"])
    problems = vmr.verify(isolated_root)
    assert any("closure-claiming" in p for p in problems)


def test_derivation_source_drift_fails(isolated_root: pathlib.Path) -> None:
    plan = isolated_root / vmr.PLAN_BREAKDOWN_REL
    plan.write_text(plan.read_text(encoding="utf-8") + "\n### B99 · invented heading\n", encoding="utf-8")
    problems = vmr.verify(isolated_root)
    assert problems  # regeneration no longer byte-matches: drift is loud, never silent


def test_main_exit_codes(isolated_root: pathlib.Path, capsys) -> None:
    assert vmr.main(["--root", str(isolated_root)]) == 0
    rogue = isolated_root / "docs" / "control" / "rogue_status.json"
    rogue.write_text(json.dumps({"milestone": "B05", "status": "CLOSED"}), encoding="utf-8")
    assert vmr.main(["--root", str(isolated_root)]) == 1

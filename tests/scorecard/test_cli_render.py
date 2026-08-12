"""CLI and rendering boundary tests for the diagnostic scorecard artifact."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from triad_origin.scorecard import build_scorecard_from_dict, render_scorecard_html
from triad_origin.scorecard.model import ScorecardError


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "generate_full_pipeline_scorecard.py"
STATUS_ONLY_EXAMPLE = ROOT / "docs" / "scorecard" / "examples" / "status_only_input.v1.json"


def _withheld_input(*, report_id: str = "scorecard:test:withheld") -> dict[str, object]:
    return {
        "schema": "triad.origin.full_pipeline_scorecard.input.v1",
        "report_id": report_id,
        "as_of_us": 1_000_000,
        "components": [],
        "cohort": {
            "cohort_id": "cohort:empty:1",
            "window_start_us": 0,
            "window_end_us": 999_999,
            "source_watermark": "source:cohort:empty:1",
            "source_cut_digest": "1" * 64,
            "complete": True,
            "candidate_ids": [],
            "zero_proof": {
                "query_digest": "2" * 64,
                "source_cut_digest": "3" * 64,
                "source_completeness": "COMPLETE",
                "watermark": "source:cohort:empty:1",
            },
            "evidence_refs": ["evidence:cohort:empty:1"],
        },
        "posture": {
            "desired": {
                "venue_environment": "OFF",
                "venue_activation": "OFF",
                "paper_activation": "OFF",
                "shadow_activation": "LIVE",
            },
            "observed": None,
            "freshness": "UNKNOWN",
            "reconciliation": "UNRECONCILED",
            "attestation": "MISSING",
            "side_effect_census_complete": None,
            "evidence_refs": ["evidence:posture:missing"],
        },
        "stages": [],
        "edges": [],
        "evaluations": [],
        "terminals": [],
        "metrics": [],
    }


def _run_cli(tmp_path: Path, payload: object, *args: str) -> subprocess.CompletedProcess[str]:
    input_path = tmp_path / "evidence.json"
    content = payload if isinstance(payload, str) else json.dumps(payload)
    input_path.write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(TOOL), str(input_path), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_render_rejects_a_report_tampered_after_digesting() -> None:
    report = build_scorecard_from_dict(_withheld_input())
    report["report_id"] = "scorecard:test:tampered"

    with pytest.raises(ScorecardError, match="content_digest mismatch"):
        render_scorecard_html(report)


def test_render_escapes_caller_supplied_html() -> None:
    hostile_id = '<script>alert("x")</script>&\''
    report = build_scorecard_from_dict(_withheld_input(report_id=hostile_id))

    rendered = render_scorecard_html(report)

    assert hostile_id not in rendered
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;&amp;&#x27;" in rendered


def test_render_is_an_offline_evidence_console_with_canonical_stage_cards() -> None:
    document = _withheld_input()
    document["components"] = [
        {
            "component_id": "triad-kairos",
            "stage": "E03",
            "role": "advisory forecast provider",
            "mapping_status": "OPERATOR_ASSERTED_UNATTESTED",
            "mapping_evidence_refs": [],
            "authority_claims": [],
        },
        {
            "component_id": "unbound:e05:intelligence-coordinator",
            "stage": "E05",
            "role": "fan-out join and calibration only",
            "mapping_status": "UNBOUND",
            "mapping_evidence_refs": [],
            "authority_claims": [],
        },
        {
            "component_id": "triad-logos",
            "stage": "E06",
            "role": "advisory language and knowledge provider",
            "mapping_status": "OPERATOR_ASSERTED_UNATTESTED",
            "mapping_evidence_refs": [],
            "authority_claims": [],
        },
    ]
    rendered = render_scorecard_html(build_scorecard_from_dict(document))

    assert "connect-src &#x27;none&#x27;" not in rendered  # policy is markup, not escaped copy
    assert "connect-src 'none'" in rendered
    assert "script-src 'none'" in rendered
    assert "<script" not in rendered.lower()
    assert "http://" not in rendered
    assert "https://" not in rendered
    assert "<form" not in rendered.lower()
    assert "PROMOTE</" not in rendered
    assert "Kronos" not in rendered
    assert "Kairos · OPERATOR_ASSERTED_UNATTESTED" in rendered
    assert "Logos · OPERATOR_ASSERTED_UNATTESTED" in rendered
    assert "independent coordinator" in rendered
    assert "Kairos and Logos never call each other" in rendered
    assert "language / knowledge advisory · binding not ratified" in rendered
    for stage in [f"E{number:02d}" for number in range(11)]:
        assert rendered.count(f'data-stage-card="{stage}"') == 1


def test_render_derives_headlines_and_exposes_accessible_evidence_tables() -> None:
    report = build_scorecard_from_dict(_withheld_input())
    rendered = render_scorecard_html(report)

    assert f"of {len(report['stage_cells'])} PROVEN" in rendered
    assert f"of {len(report['edge_cells'])} PROVEN" in rendered
    assert "0 · RECEIPT" in rendered
    assert "Conservation result</span>\n      <span class=\"badge UNRECONCILED\"" in rendered
    assert 'class="skip-link"' in rendered
    assert '<nav class="anchor-nav" aria-label="Scorecard sections">' in rendered
    assert rendered.count("<caption>") >= 7
    assert 'scope="col"' in rendered
    assert '<details class="drawer"' in rendered
    assert "Null is not zero" in rendered
    assert "Historical 418-cell backfill" in rendered


def test_cli_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    result = _run_cli(tmp_path, '{"schema":"first","schema":"second"}')

    assert result.returncode == 1
    assert "SCORECARD_INPUT_INVALID" in result.stderr
    assert "duplicate JSON key" in result.stderr
    assert "schema" in result.stderr


def test_cli_returns_one_for_invalid_input(tmp_path: Path) -> None:
    result = _run_cli(tmp_path, [])

    assert result.returncode == 1
    assert "SCORECARD_INPUT_INVALID" in result.stderr
    assert "input root must be an object" in result.stderr


def test_cli_withholds_by_default_with_fail_closed_exit_two(tmp_path: Path) -> None:
    result = _run_cli(tmp_path, _withheld_input())

    assert result.returncode == 2
    assert "SCORECARD_WITHHELD" in result.stderr
    assert json.loads(result.stdout)["publication"]["outcome"] == "WITHHELD"


def test_cli_diagnostic_only_allows_emitted_withheld_report(tmp_path: Path) -> None:
    result = _run_cli(tmp_path, _withheld_input(), "--diagnostic-only")

    assert result.returncode == 0
    assert "SCORECARD_WITHHELD" in result.stderr
    assert json.loads(result.stdout)["publication"]["outcome"] == "WITHHELD"


def test_documented_status_only_example_generates_json_and_adjusted_gui(tmp_path: Path) -> None:
    json_output = tmp_path / "scorecard.json"
    html_output = tmp_path / "scorecard.html"
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            str(STATUS_ONLY_EXAMPLE),
            "--diagnostic-only",
            "--json-output",
            str(json_output),
            "--html-output",
            str(html_output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(json_output.read_text(encoding="utf-8"))["publication"]["outcome"] == "WITHHELD"
    rendered = html_output.read_text(encoding="utf-8")
    assert "TRIAD ORIGIN · E00–E10 · EVIDENCE CONSOLE" in rendered
    assert "Kairos · OPERATOR_ASSERTED_UNATTESTED" in rendered
    assert "Logos · OPERATOR_ASSERTED_UNATTESTED" in rendered

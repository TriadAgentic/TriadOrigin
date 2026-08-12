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

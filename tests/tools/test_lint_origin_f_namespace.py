"""CO-11 — tests for the ORIGIN-F## namespace linter (report-only default, --enforce fatal)."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import lint_origin_f_namespace as linter  # noqa: E402


def _kinds(findings):
    return [(f.kind, f.token) for f in findings]


def test_bare_single_digit_f_is_flagged() -> None:
    findings = linter.lint_text("The F2 filter field gates OI here.", "x.md")
    assert _kinds(findings) == [("BARE_F_SINGLE_DIGIT", "F2")]


def test_origin_two_digit_reference_is_compliant() -> None:
    assert linter.lint_text("Use ORIGIN-F02 and ORIGIN-F23 in cross-estate prose.", "x.md") == []


def test_two_digit_f_form_is_not_flagged_as_bare() -> None:
    assert linter.lint_text("Formulas F00 through F23 are Origin-internal spellings.", "x.md") == []


def test_malformed_origin_single_digit_is_flagged() -> None:
    findings = linter.lint_text("ORIGIN-F2 must be written with two digits.", "x.md")
    assert ("MALFORMED_ORIGIN_REF", "ORIGIN-F2") in _kinds(findings)
    # The bare-F arm must not double-report the same token.
    assert ("BARE_F_SINGLE_DIGIT", "F2") not in _kinds(findings)


def test_fenced_code_blocks_are_exempt() -> None:
    text = "prose line\n```\nF3 inside a fence is data\n```\nafter\n"
    assert linter.lint_text(text, "x.md") == []


def test_inline_code_spans_are_exempt() -> None:
    assert linter.lint_text("The `Dashboard!F5` cell is quoted evidence.", "x.md") == []


def test_identifier_adjacent_tokens_are_not_flagged() -> None:
    assert linter.lint_text("WAVE-F1 and PDF1 and F1x are not bare F refs.", "x.md") == []


def test_line_and_column_are_reported() -> None:
    (finding,) = linter.lint_text("a\nbb F7 cc\n", "doc.md")
    assert (finding.path, finding.line, finding.kind) == ("doc.md", 2, "BARE_F_SINGLE_DIGIT")
    assert finding.column == 4


def test_report_only_default_exits_zero_with_findings(tmp_path: pathlib.Path, capsys) -> None:
    plan = tmp_path / "docs" / "plan"
    plan.mkdir(parents=True)
    (plan / "a.md").write_text("bare F4 here\n", encoding="utf-8")
    assert linter.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "BARE_F_SINGLE_DIGIT" in out
    assert "REPORT-ONLY" in out


def test_enforce_mode_fails_on_findings(tmp_path: pathlib.Path) -> None:
    plan = tmp_path / "docs" / "plan"
    plan.mkdir(parents=True)
    (plan / "a.md").write_text("bare F4 here\n", encoding="utf-8")
    assert linter.main(["--root", str(tmp_path), "--enforce"]) == 1


def test_enforce_mode_passes_on_clean_tree(tmp_path: pathlib.Path) -> None:
    plan = tmp_path / "docs" / "plan"
    plan.mkdir(parents=True)
    (plan / "a.md").write_text("ORIGIN-F14 reacts; estate filters unchanged.\n", encoding="utf-8")
    assert linter.main(["--root", str(tmp_path), "--enforce"]) == 0


def test_real_repo_report_only_run_is_nonfatal() -> None:
    # Pre-existing estate-filter-field rows are preserved findings, never a default failure.
    assert linter.main(["--root", str(ROOT)]) == 0


def test_rule_document_exists_with_pending_signature_slot() -> None:
    doc = (ROOT / "docs" / "plan" / "CO-11-ORIGIN-F-NAMESPACE-RULE.md").read_text(encoding="utf-8")
    assert "PENDING-OWNER" in doc
    assert "PENDING_SIGNATURE" in doc
    assert "ORIGIN-F##" in doc

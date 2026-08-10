"""Structural conformance tests for the B09 operational runbooks (``docs/runbooks/``).

The B09 milestone deliverable owes eleven runbooks
(``docs/plan/01_MILESTONE_BREAKDOWN.md`` §B09 — the compressed checklist line names nine;
the milestone deliverable adds ``incident`` and ``protection`` and governs), and the acceptance
criterion is verbatim: *"runbooks contain owner, trigger, stop, rollback, evidence, and
escalation"*.  These tests assert every runbook exists and carries that six-field shape plus its
baseline-posture header, and that the TESTNET runbook is a *refusal-to-operate / boundary* document
— never a how-to-enable procedure.

This module only READS files under the repository tree; it launches no subprocess, imports no
capability, and mutates nothing.
"""

from __future__ import annotations

import pathlib

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_RUNBOOKS = _REPO_ROOT / "docs" / "runbooks"

# The eleven runbooks the milestone deliverable names (superset of the compressed
# checklist's nine: it adds ``incident`` and ``protection``).
RUNBOOK_FILES = (
    "migration.md",
    "rollback.md",
    "split_brain.md",
    "shadow_degradation.md",
    "paper_isolation.md",
    "testnet.md",
    "incident.md",
    "fill_lineage.md",
    "reconciliation.md",
    "protection.md",
    "disaster_recovery.md",
)

# The six-field content law (00_MASTER_PLAN.md / 01_MILESTONE_BREAKDOWN.md acceptance).
REQUIRED_SECTIONS = ("Owner", "Trigger", "Stop", "Rollback", "Evidence", "Escalation")


def _read(name: str) -> str:
    path = _RUNBOOKS / name
    assert path.is_file(), f"runbook missing: docs/runbooks/{name}"
    return path.read_text(encoding="utf-8")


def _level2_headings(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            out.append(stripped[3:].strip())
    return out


def test_all_eleven_runbooks_exist() -> None:
    assert _RUNBOOKS.is_dir(), "docs/runbooks/ directory is missing"
    for name in RUNBOOK_FILES:
        assert (_RUNBOOKS / name).is_file(), f"runbook missing: docs/runbooks/{name}"


@pytest.mark.parametrize("name", RUNBOOK_FILES)
def test_runbook_carries_the_six_required_sections(name: str) -> None:
    text = _read(name)
    headings = {h.lower() for h in _level2_headings(text)}
    for section in REQUIRED_SECTIONS:
        assert section.lower() in headings, (
            f"docs/runbooks/{name} is missing the required '## {section}' section "
            f"(the six-field content law owner/trigger/stop/rollback/evidence/escalation)"
        )


@pytest.mark.parametrize("name", RUNBOOK_FILES)
def test_runbook_declares_id_and_denied_safe_hold_baseline(name: str) -> None:
    text = _read(name)
    assert "Runbook-ID:" in text, f"docs/runbooks/{name} lacks a Runbook-ID header"
    lowered = text.lower()
    # Every runbook is written for the one baseline posture and names it explicitly.
    assert "activation posture:" in lowered, (
        f"docs/runbooks/{name} lacks an 'Activation posture:' header"
    )
    assert "denied_safe_hold" in lowered, (
        f"docs/runbooks/{name} does not name the DENIED_SAFE_HOLD posture"
    )
    # The exact non-authoritative baseline manifest (OFF/OFF/OFF/LIVE, shadow fixed LIVE).
    for lever in (
        "venue_environment=off",
        "venue_activation=off",
        "paper_activation=off",
        "shadow_activation=live",
    ):
        assert lever in lowered, (
            f"docs/runbooks/{name} does not carry the baseline lever '{lever.upper()}'"
        )


def test_readme_states_the_six_field_content_law() -> None:
    text = _read("README.md").lower()
    assert "owner" in text and "trigger" in text and "stop" in text
    assert "rollback" in text and "evidence" in text and "escalation" in text
    # The index enumerates all eleven runbook files.
    for name in RUNBOOK_FILES:
        assert name in text, f"docs/runbooks/README.md does not list {name}"


# --- The TESTNET runbook is a refusal-to-operate / boundary doc, never a how-to-enable. ---

# ORIGIN NEVER OPERATES TESTNET.  For this estate RC4 makes TESTNET a canonical isolated venue
# environment (open-question E1, DEFAULT_IN_FORCE), so this is NOT the sibling estate's
# "no testnet ever" retirement — but TESTNET carries venue_path=true, so it is estate-owned and
# ORIGIN refuses to operate it, currently OFF under DENIED_SAFE_HOLD.  The runbook must therefore
# be a refusal/boundary document with NO operator how-to-enable content.

_TESTNET_REFUSAL_MARKERS = (
    "refused",
    "denied_safe_hold",
    "estate-owned",
    "origin never operates",
    "not a how-to-enable procedure",
)

# Forbidden operator how-to-enable imperatives: a testnet runbook that told an operator how to
# switch testnet on would breach ORIGIN's refuse-to-operate boundary and the no-venue-how-to law.
_FORBIDDEN_TESTNET_HOWTO = (
    "how to enable testnet",
    "how to activate testnet",
    "steps to enable testnet",
    "steps to activate testnet",
    "to enable testnet,",
    "enable testnet by",
    "turn on testnet",
)


def test_testnet_runbook_is_a_refusal_to_operate_not_a_how_to_enable() -> None:
    lowered = _read("testnet.md").lower()
    for marker in _TESTNET_REFUSAL_MARKERS:
        assert marker in lowered, (
            f"testnet.md is missing the refusal-to-operate marker {marker!r}: "
            f"ORIGIN never operates TESTNET (estate-owned, DENIED_SAFE_HOLD, venue_environment=OFF)"
        )
    for forbidden in _FORBIDDEN_TESTNET_HOWTO:
        assert forbidden not in lowered, (
            f"testnet.md contains a how-to-enable imperative {forbidden!r}: the TESTNET runbook is "
            f"a refusal/boundary doc, never an operator how-to-enable procedure"
        )


def test_testnet_runbook_records_the_sibling_estate_supersession() -> None:
    # It must be honest that RC4 (not "no testnet ever") governs here, and that the sibling
    # estate's rule is a different estate's law left untouched — the E1 framing.
    lowered = _read("testnet.md").lower()
    assert "adr-005" in lowered, "testnet.md must cite the ADR-005 supersession framing"
    assert "sibling" in lowered, "testnet.md must name the sibling-estate boundary (E1)"

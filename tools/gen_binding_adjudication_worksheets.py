#!/usr/bin/env python3
"""CO-07 — Binding adjudication worksheet generator (the MECHANICAL half).

Reads ``docs/control/binding_registry.v2.json`` and emits, for EVERY binding row,
one adjudication worksheet carrying exactly the CO-07 Step-1 fields:

    {binding_id, formula_id, parameter, declared value, unit, gate,
     boundary rule, failure behavior, evidence refs,
     proposed disposition, owner signature slot}

THE LAW (CO-07 / estate governance):
  * Every ``proposed disposition`` is a PROPOSAL ONLY. An agent NEVER adjudicates.
  * Every ``owner signature slot`` is EMPTY (``PENDING_OWNER``). An agent NEVER signs.
  * Worksheets are grouped in FORMULA-COMPLETE groups: a formula activates only when
    its ENTIRE set is proposed ACTIVE. F21's 1-of-10 must never present as active.

Proposed-disposition derivation (deterministic, precedence order):
  1. PAR-170 family (parameter_id == PAR-170)  -> SUPERSEDED  (RC4 supersession pointer)
  2. PAR-036 (F03 DC_REVERSAL, research-decision) -> BLOCKED_ON_RATIFY(PAR-036)
  3. registry status ACTIVE                       -> ACTIVE
  4. registry status BLOCKED (unratified)         -> BLOCKED_ON_RATIFY(<parameter_id>)
  5. registry status BLOCKED_BINDING_V2_MIGRATION -> BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)

Cases 2 + 4 cover the named research-decision rows (F06 span, F08 reducer,
F17 min-depth value, PAR-036). REFUSED is a lawful adjudication target but no
current registry row warrants a *proposed* REFUSED.

Deterministic + offline: stdlib only, no wall clock, no randomness, sorted output.
This tool arms nothing and changes no machine status.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

REGISTRY_PATH_DEFAULT = "docs/control/binding_registry.v2.json"
WORKSHEETS_PATH_DEFAULT = "docs/plan/CO-07-BINDING-ADJUDICATION-WORKSHEETS.md"
MATRIX_PATH_DEFAULT = "docs/plan/CO-07-COMPLETENESS-MATRIX.md"

# ---- disposition token vocabulary (closed) ---------------------------------
DISP_ACTIVE = "ACTIVE"
DISP_SUPERSEDED = "SUPERSEDED"
CANONICAL_TARGETS = ("ACTIVE", "BLOCKED", "SUPERSEDED", "REFUSED")

MIGRATION_TASK = "RC3-TASK-G2-BINDING-V2"
OWNER_SIGNATURE_EMPTY = "PENDING_OWNER"

# RC4 supersession pointer for the PAR-170 family (CO-01 §3 operation table).
PAR_170_SUPERSESSION_POINTER = (
    "RC4: PAR-170/FPB-0078 -> OFI_NORMALIZED_VARIANT_ACTIVATION=OFF "
    "(RC4 control bundle; compiled into RC5_EFFECTIVE_CONSOLIDATION per CO-01)."
)


def _formula_sort_key(formula_id: str) -> int:
    # F00..F23 -> integer order; non-numeric tail falls back to 0-padded string.
    try:
        return int(formula_id[1:])
    except ValueError:  # pragma: no cover - defensive; registry is F##
        return 10_000


@dataclass(frozen=True)
class Worksheet:
    binding_id: str
    formula_id: str
    parameter: str
    declared_value: str
    unit: str
    gate: str
    boundary_rule: str
    failure_behavior: str
    evidence_refs: List[str]
    proposed_disposition: str
    canonical_target: str
    named_refusal: str
    owner_signature_slot: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "formula_id": self.formula_id,
            "parameter": self.parameter,
            "declared_value": self.declared_value,
            "unit": self.unit,
            "gate": self.gate,
            "boundary_rule": self.boundary_rule,
            "failure_behavior": self.failure_behavior,
            "evidence_refs": list(self.evidence_refs),
            "proposed_disposition": self.proposed_disposition,
            "canonical_target": self.canonical_target,
            "named_refusal": self.named_refusal,
            "owner_signature_slot": self.owner_signature_slot,
        }


@dataclass(frozen=True)
class FormulaGroup:
    formula_id: str
    worksheets: List[Worksheet]
    activation_status: str  # "ACTIVE" | "NOT_ACTIVE"
    active_count: int
    total: int
    reason: str


def _evidence_refs(row: Dict[str, Any], registry_digest: str) -> List[str]:
    """The machine-checkable provenance pointers already present in the row."""
    refs = [
        f"source_binding_id={row.get('source_binding_id', '')}",
        f"rc2_source_digest={row.get('rc2_source_digest', '')}",
        f"binding_digest={row.get('binding_digest', '')}",
        f"operation_id={row.get('operation_id', '')}",
        f"activation_scope={row.get('activation_scope', '')}",
        f"consuming_wiring_ids={row.get('consuming_wiring_ids', '')}",
        f"registry_source_bundle_digest={registry_digest}",
    ]
    return refs


def _derive_disposition(row: Dict[str, Any]) -> Dict[str, str]:
    """Return {proposed_disposition, canonical_target, named_refusal}.

    A PROPOSAL only. The owner adjudicates + signs; this function never does.
    """
    pid = row.get("parameter_id", "")
    pname = row.get("parameter_name", "")
    status = row.get("status", "")
    reason = row.get("disposition_reason", "")
    condition = row.get("condition", "")

    # 1. PAR-170 family -> SUPERSEDED (RC4)
    if pid == "PAR-170":
        return {
            "proposed_disposition": DISP_SUPERSEDED,
            "canonical_target": "SUPERSEDED",
            "named_refusal": (
                f"PROPOSED SUPERSEDED: {pname} superseded by {PAR_170_SUPERSESSION_POINTER}"
            ),
        }

    # 2. PAR-036 research decision (a migration row overridden to ratify-blocked)
    if pid == "PAR-036":
        return {
            "proposed_disposition": f"BLOCKED_ON_RATIFY({pid})",
            "canonical_target": "BLOCKED",
            "named_refusal": (
                f"BLOCKED_ON_RATIFY({pid}): {pname} awaits an owner research decision "
                f"(F03 reversal); the RC2 row is also unmigrated by {MIGRATION_TASK}."
            ),
        }

    # 3. ACTIVE per registry status
    if status == "ACTIVE":
        return {
            "proposed_disposition": DISP_ACTIVE,
            "canonical_target": "ACTIVE",
            "named_refusal": (
                f"PROPOSED ACTIVE: {reason}".strip()
                if reason
                else "PROPOSED ACTIVE per registry status."
            ),
        }

    # 4. BLOCKED (unratified) per registry status -> BLOCKED_ON_RATIFY
    if status == "BLOCKED":
        return {
            "proposed_disposition": f"BLOCKED_ON_RATIFY({pid})",
            "canonical_target": "BLOCKED",
            "named_refusal": f"BLOCKED_ON_RATIFY({pid}): {reason}".strip(),
        }

    # 5. BLOCKED_BINDING_V2_MIGRATION per registry status
    if status == "BLOCKED_BINDING_V2_MIGRATION":
        base = reason or "Preserved RC2 row not yet semantically migrated."
        return {
            "proposed_disposition": f"BLOCKED_ON_MIGRATION({MIGRATION_TASK})",
            "canonical_target": "BLOCKED",
            "named_refusal": (
                f"BLOCKED_ON_MIGRATION({MIGRATION_TASK}): {base} ({condition})".strip()
            ),
        }

    # Unknown registry status: fail closed to BLOCKED with a named refusal,
    # never a fabricated ACTIVE.
    return {
        "proposed_disposition": f"BLOCKED_ON_UNKNOWN_STATUS({status})",
        "canonical_target": "BLOCKED",
        "named_refusal": (
            f"BLOCKED_ON_UNKNOWN_STATUS({status}): registry status is not one of "
            "the recognized adjudication inputs; refuse, do not guess."
        ),
    }


def build_worksheet(row: Dict[str, Any], registry_digest: str) -> Worksheet:
    disp = _derive_disposition(row)
    pid = row.get("parameter_id", "")
    pname = row.get("parameter_name", "")
    parameter = f"{pid} ({pname})" if pname else pid
    return Worksheet(
        binding_id=row.get("binding_id", ""),
        formula_id=row.get("formula_id", ""),
        parameter=parameter,
        declared_value=row.get("declared_value", ""),
        unit=row.get("unit", ""),
        gate=row.get("gate", ""),
        boundary_rule=row.get("boundary_rule", ""),
        failure_behavior=row.get("failure_behavior", ""),
        evidence_refs=_evidence_refs(row, registry_digest),
        proposed_disposition=disp["proposed_disposition"],
        canonical_target=disp["canonical_target"],
        named_refusal=disp["named_refusal"],
        owner_signature_slot=OWNER_SIGNATURE_EMPTY,
    )


def build_all(registry: Dict[str, Any]) -> Dict[str, Any]:
    """Pure builder: registry dict -> structured worksheets + groups + summary."""
    rows = registry.get("rows", [])
    registry_digest = registry.get("source_bundle_digest", "")
    worksheets = [build_worksheet(r, registry_digest) for r in rows]

    # Group in FORMULA-COMPLETE groups.
    by_formula: Dict[str, List[Worksheet]] = {}
    for w in worksheets:
        by_formula.setdefault(w.formula_id, []).append(w)

    groups: List[FormulaGroup] = []
    for fid in sorted(by_formula, key=_formula_sort_key):
        ws = sorted(by_formula[fid], key=lambda w: w.binding_id)
        total = len(ws)
        active_count = sum(1 for w in ws if w.canonical_target == "ACTIVE")
        all_active = active_count == total and total > 0
        activation_status = "ACTIVE" if all_active else "NOT_ACTIVE"
        if all_active:
            reason = f"FORMULA-COMPLETE: {active_count}/{total} rows proposed ACTIVE."
        else:
            reason = (
                f"NOT FORMULA-COMPLETE: {active_count}/{total} rows proposed ACTIVE — "
                "the formula MUST NOT present as active until its entire set is ACTIVE."
            )
        groups.append(
            FormulaGroup(
                formula_id=fid,
                worksheets=ws,
                activation_status=activation_status,
                active_count=active_count,
                total=total,
                reason=reason,
            )
        )

    # Summary counts by proposed disposition family.
    disp_family: Dict[str, int] = {}
    for w in worksheets:
        fam = w.proposed_disposition.split("(", 1)[0]
        disp_family[fam] = disp_family.get(fam, 0) + 1

    canonical_counts: Dict[str, int] = {t: 0 for t in CANONICAL_TARGETS}
    for w in worksheets:
        canonical_counts[w.canonical_target] = canonical_counts.get(w.canonical_target, 0) + 1

    return {
        "registry_version": registry.get("registry_version", ""),
        "row_count": registry.get("row_count", len(rows)),
        "actual_row_count": len(rows),
        "source_bundle_digest": registry_digest,
        "registry_status_counts": dict(registry.get("status_counts", {})),
        "worksheets": worksheets,
        "groups": groups,
        "proposed_disposition_family_counts": disp_family,
        "canonical_target_counts": canonical_counts,
        "formulas_formula_complete_active": [
            g.formula_id for g in groups if g.activation_status == "ACTIVE"
        ],
    }


# ---- rendering --------------------------------------------------------------

def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def render_worksheets_md(built: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# CO-07 — Binding Adjudication Worksheets")
    lines.append("")
    lines.append(
        "**Disposition:** `PLAN_LEVEL / PROPOSALS_ONLY / NOT_A_RATIFICATION / "
        "NO_RUNTIME_CHANGE`. Posture unchanged `OFF/OFF/OFF/LIVE`, `DENIED_SAFE_HOLD`."
    )
    lines.append("")
    lines.append(
        "Generated deterministically by `tools/gen_binding_adjudication_worksheets.py` "
        f"from `{REGISTRY_PATH_DEFAULT}` "
        f"(`registry_version={built['registry_version']}`, "
        f"`source_bundle_digest={built['source_bundle_digest']}`). "
        "Do not hand-edit — regenerate from the registry."
    )
    lines.append("")
    lines.append("## The law (read first)")
    lines.append("")
    lines.append(
        "* Every **proposed disposition** below is a **PROPOSAL ONLY**. "
        "An agent NEVER adjudicates a binding row."
    )
    lines.append(
        "* Every **owner signature slot** is **EMPTY (`PENDING_OWNER`)**. "
        "An agent NEVER signs."
    )
    lines.append(
        "* Rows are grouped in **FORMULA-COMPLETE groups**: a formula activates only "
        "when its ENTIRE set is `ACTIVE`. A partially-active formula (e.g. F21's 1-of-10) "
        "MUST NOT present as active."
    )
    lines.append(
        "* Adjudication targets are the closed set `ACTIVE | BLOCKED | SUPERSEDED | "
        "REFUSED` (CO-07 objective). `BLOCKED_ON_RATIFY(...)` / "
        f"`BLOCKED_ON_MIGRATION({MIGRATION_TASK})` are BLOCKED sub-reasons."
    )
    lines.append("")
    lines.append("## Row-count reconciliation (honest note)")
    lines.append("")
    sc = built["registry_status_counts"]
    lines.append(
        f"The registry carries **{built['actual_row_count']} rows** "
        f"(declared `row_count={built['row_count']}`). Status counts: "
        + ", ".join(f"`{k}={v}`" for k, v in sorted(sc.items()))
        + "."
    )
    lines.append(
        "The CO-07 title names \"the 98 migration-blocked rows\"; that is exactly the "
        f"`BLOCKED_BINDING_V2_MIGRATION={sc.get('BLOCKED_BINDING_V2_MIGRATION', 0)}` "
        f"subset. The 4 `BLOCKED` (unratified) + 3 `ACTIVE` rows complete the "
        f"**{built['actual_row_count']}-row bundle** the owner authenticates per Formula "
        "Repair §C.1 (CO-07 Step 5). PAR-025 (RC3-FPB-005, F01) is a `BLOCKED` "
        "(unratified) row not named in the research list; per registry status it is "
        "proposed `BLOCKED_ON_RATIFY(PAR-025)`."
    )
    lines.append("")
    lines.append("## Proposed-disposition tally (proposals, not adjudications)")
    lines.append("")
    for fam in sorted(built["proposed_disposition_family_counts"]):
        lines.append(f"* `{fam}` — {built['proposed_disposition_family_counts'][fam]}")
    lines.append("")
    lines.append(
        "Canonical-target rollup: "
        + ", ".join(
            f"`{t}={built['canonical_target_counts'].get(t, 0)}`" for t in CANONICAL_TARGETS
        )
        + ". No current row warrants a proposed `REFUSED`."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    for g in built["groups"]:
        badge = "FORMULA-COMPLETE · ACTIVE" if g.activation_status == "ACTIVE" else "NOT ACTIVE"
        lines.append(f"## Formula {g.formula_id} — group activation: {badge}")
        lines.append("")
        lines.append(f"*{g.reason}*")
        lines.append("")
        for w in g.worksheets:
            lines.append(f"### {w.binding_id} — {w.formula_id} · {_md_escape(w.parameter)}")
            lines.append("")
            lines.append(f"* **binding_id:** `{w.binding_id}`")
            lines.append(f"* **formula_id:** `{w.formula_id}`")
            lines.append(f"* **parameter:** {_md_escape(w.parameter)}")
            lines.append(f"* **declared value:** `{_md_escape(w.declared_value)}`")
            lines.append(f"* **unit:** `{_md_escape(w.unit)}`")
            lines.append(f"* **gate:** `{_md_escape(w.gate)}`")
            lines.append(f"* **boundary rule:** {_md_escape(w.boundary_rule)}")
            lines.append(f"* **failure behavior:** {_md_escape(w.failure_behavior)}")
            lines.append("* **evidence refs:**")
            for ref in w.evidence_refs:
                lines.append(f"    * `{_md_escape(ref)}`")
            lines.append(
                f"* **proposed disposition (PROPOSAL ONLY):** `{w.proposed_disposition}` "
                f"→ canonical target `{w.canonical_target}`"
            )
            lines.append(f"    * named refusal / basis: {_md_escape(w.named_refusal)}")
            lines.append(
                f"* **owner signature slot:** `{w.owner_signature_slot}` "
                "(empty — owner adjudicates + signs; agent never does)"
            )
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Owner gate (not an agent act)")
    lines.append("")
    lines.append(
        "CO-07 Step 5 — authenticating the exact "
        f"{built['actual_row_count']}-row bundle per Formula Repair §C.1 (wrong count / "
        "duplicate scope / partial set refuses) and driving zero rows left in "
        "`BLOCKED_BINDING_V2_MIGRATION` — is the OWNER's adjudication act after signing "
        "each worksheet. This document supplies the mechanical worksheets only; it "
        "authenticates nothing and signs nothing."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def render_matrix_md(built: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# CO-07 — Per-Formula Completeness Matrix")
    lines.append("")
    lines.append(
        "Generated deterministically by `tools/gen_binding_adjudication_worksheets.py` "
        f"from `{REGISTRY_PATH_DEFAULT}`. A formula's group activates only when its "
        "ENTIRE set of binding rows is proposed `ACTIVE`. Proposals only — no "
        "adjudication, no signature."
    )
    lines.append("")
    lines.append(
        "| formula | rows | proposed ACTIVE | proposed BLOCKED | proposed SUPERSEDED "
        "| proposed REFUSED | group activation |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for g in built["groups"]:
        active = sum(1 for w in g.worksheets if w.canonical_target == "ACTIVE")
        blocked = sum(1 for w in g.worksheets if w.canonical_target == "BLOCKED")
        superseded = sum(1 for w in g.worksheets if w.canonical_target == "SUPERSEDED")
        refused = sum(1 for w in g.worksheets if w.canonical_target == "REFUSED")
        badge = "ACTIVE" if g.activation_status == "ACTIVE" else f"NOT_ACTIVE ({active}/{g.total})"
        lines.append(
            f"| {g.formula_id} | {g.total} | {active} | {blocked} | {superseded} "
            f"| {refused} | {badge} |"
        )
    lines.append("")
    fca = built["formulas_formula_complete_active"]
    if fca:
        lines.append(
            "**Formula-complete ACTIVE groups:** "
            + ", ".join(f"`{f}`" for f in fca)
            + "."
        )
    else:
        lines.append("**Formula-complete ACTIVE groups:** none.")
    lines.append("")
    lines.append(
        "Every other formula has at least one non-ACTIVE row and therefore MUST NOT "
        "present as active. Note F21 in particular: a single ACTIVE row (`RC3-FPB-004`, "
        "MAKER_MAX_BOOK_LEVELS) of 10 — the 1-of-10 that must never read as an active "
        "formula."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def load_registry(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CO-07 binding adjudication worksheet generator")
    ap.add_argument("--registry", default=REGISTRY_PATH_DEFAULT)
    ap.add_argument("--worksheets-out", default=WORKSHEETS_PATH_DEFAULT)
    ap.add_argument("--matrix-out", default=MATRIX_PATH_DEFAULT)
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify on-disk outputs match regeneration; exit 1 on drift (write nothing)",
    )
    args = ap.parse_args(argv)

    registry = load_registry(args.registry)
    built = build_all(registry)
    worksheets_md = render_worksheets_md(built)
    matrix_md = render_matrix_md(built)

    if args.check:
        ok = True
        for path, expected in (
            (args.worksheets_out, worksheets_md),
            (args.matrix_out, matrix_md),
        ):
            p = Path(path)
            actual = p.read_text(encoding="utf-8") if p.exists() else None
            if actual != expected:
                print(f"DRIFT: {path} does not match regeneration")
                ok = False
        if ok:
            print("OK: worksheets + matrix match regeneration")
            return 0
        return 1

    Path(args.worksheets_out).write_text(worksheets_md, encoding="utf-8")
    Path(args.matrix_out).write_text(matrix_md, encoding="utf-8")
    print(f"wrote {args.worksheets_out}")
    print(f"wrote {args.matrix_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

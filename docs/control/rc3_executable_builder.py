#!/usr/bin/env python3
"""Build the standalone TRIAD ORIGIN V7 RC3 master specification/document."""

from __future__ import annotations

import base64
import copy
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RC1_DIR = ROOT / "TRIAD_ORIGIN_V7_SPEC_1.0.0_RC1"
RC2_DIR = ROOT / "TRIAD_ORIGIN_V7_IMPLEMENTATION_CONTROL_PACKAGE_1.0.0_RC2"
CANON = RC2_DIR / "canonical"
SOURCES = ROOT / "project_sources"
OUTPUT = ROOT / "TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_AND_MASTER_DOCUMENT_1.0.0_RC3.html"
VERSION = "1.0.0-RC3"
DATE = "2026-08-09"
STATUS = "RATIFICATION_CANDIDATE_NOT_ARMED"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(value: object) -> str:
    """Deterministic JSON encoding used for embedded machine-authority digests."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_schema_profile(instance: object, schema: dict[str, object], path: str = "$") -> list[str]:
    """Execute the closed JSON-Schema assertion profile used by the RC3 overlay.

    This intentionally supports only the declared deterministic subset and fails on
    unknown assertion keywords, so a schema edit cannot silently become decorative.
    """
    supported = {
        "$schema", "$id", "title", "description", "type", "required", "properties",
        "additionalProperties", "items", "minItems", "maxItems", "uniqueItems",
        "minLength", "pattern", "const", "enum",
    }
    errors: list[str] = []
    unknown = sorted(set(schema) - supported)
    if unknown:
        return [f"{path}: unsupported schema keywords {','.join(unknown)}"]

    expected_type = schema.get("type")
    type_checks = {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
        "null": lambda value: value is None,
    }
    if expected_type is not None:
        accepted_types = [expected_type] if isinstance(expected_type, str) else list(expected_type)
        if any(type_name not in type_checks for type_name in accepted_types):
            errors.append(f"{path}: unsupported declared type {expected_type}")
            return errors
        if not any(type_checks[type_name](instance) for type_name in accepted_types):
            errors.append(f"{path}: expected type {expected_type}, got {type(instance).__name__}")
            return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: value does not equal const")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")

    if isinstance(instance, str):
        if len(instance) < int(schema.get("minLength", 0)):
            errors.append(f"{path}: string shorter than minLength")
        pattern = schema.get("pattern")
        if pattern is not None and re.fullmatch(str(pattern), instance) is None:
            errors.append(f"{path}: string does not match pattern {pattern}")

    if isinstance(instance, list):
        if len(instance) < int(schema.get("minItems", 0)):
            errors.append(f"{path}: array shorter than minItems")
        if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
            errors.append(f"{path}: array longer than maxItems")
        if schema.get("uniqueItems"):
            encoded = [canonical_json(value) for value in instance]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: array items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, value in enumerate(instance):
                errors.extend(validate_schema_profile(value, item_schema, f"{path}[{index}]"))

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in instance:
                errors.extend(validate_schema_profile(instance[key], child_schema, f"{path}.{key}"))
        extra_keys = set(instance) - set(properties)
        additional = schema.get("additionalProperties", True)
        if additional is False and extra_keys:
            errors.append(f"{path}: additional properties not allowed: {','.join(sorted(extra_keys))}")
        elif isinstance(additional, dict):
            for key in sorted(extra_keys):
                errors.extend(validate_schema_profile(instance[key], additional, f"{path}.{key}"))
    return errors


def read_csv(name: str) -> list[dict[str, str]]:
    with (CANON / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def text(value: object) -> str:
    return esc(value).replace("\n", "<br>")


def code_text(value: object) -> str:
    return f'<code>{text(value)}</code>' if str(value) else '<span class="muted">—</span>'


def status_chip(value: str) -> str:
    v = value or "UNKNOWN"
    low = v.lower()
    tone = "neutral"
    if any(x in low for x in ("ratified", "pass", "verified", "ready", "current")):
        tone = "good"
    if any(x in low for x in ("blocked", "not_ratified", "safe_hold", "fail", "denied", "stale")):
        tone = "bad"
    elif any(x in low for x in ("target", "proposed", "candidate", "reported", "snapshot", "future")):
        tone = "warn"
    return f'<span class="chip {tone}">{esc(v)}</span>'


def section(anchor: str, number: str, title: str, body: str, cls: str = "") -> str:
    return f'<section class="chapter {cls}" id="{esc(anchor)}"><h2><span>{esc(number)}</span>{esc(title)}</h2>{body}</section>'


def callout(title: str, body: str, tone: str = "info") -> str:
    return f'<div class="callout {tone}"><strong>{esc(title)}</strong><div>{body}</div></div>'


def simple_table(headers: list[str], rows: list[list[str]], table_id: str = "") -> str:
    hid = f' id="{esc(table_id)}"' if table_id else ""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table{hid}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def detail_list(row: dict[str, str], keys: list[str]) -> str:
    blocks = []
    for key in keys:
        value = row.get(key, "")
        if value == "":
            continue
        blocks.append(f'<div><dt>{esc(key.replace("_", " ").title())}</dt><dd>{text(value)}</dd></div>')
    return '<dl class="record-details">' + "".join(blocks) + "</dl>"


def filter_bar(table_id: str, rows: list[dict[str, str]], facets: list[str]) -> str:
    parts = [
        f'<input type="search" data-query-for="{esc(table_id)}" placeholder="Search this registry…" aria-label="Search {esc(table_id)}">'
    ]
    for facet in facets:
        vals = sorted({r.get(facet, "") for r in rows if r.get(facet, "")})
        options = "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in vals)
        parts.append(
            f'<select data-facet-for="{esc(table_id)}" data-facet="{esc(facet)}" aria-label="Filter {esc(facet)}">'
            f'<option value="">All {esc(facet.replace("_", " "))}</option>{options}</select>'
        )
    parts.extend([
        f'<button type="button" data-reset-for="{esc(table_id)}">Reset</button>',
        f'<button type="button" data-export-for="{esc(table_id)}">Export visible CSV</button>',
        f'<span class="count" data-count-for="{esc(table_id)}">{len(rows)} / {len(rows)}</span>',
    ])
    return '<div class="toolbar no-print">' + "".join(parts) + "</div>"


def data_attrs(row: dict[str, str], facets: list[str]) -> str:
    haystack = " ".join(str(v) for v in row.values()).lower()
    attrs = [f'data-search="{esc(haystack)}"']
    for facet in facets:
        attrs.append(f'data-{esc(facet)}="{esc(row.get(facet, ""))}"')
    return " ".join(attrs)


def task_table(rows: list[dict[str, str]]) -> str:
    facets = ["gate", "domain", "accountable_owner", "priority", "truth_state", "initial_status"]
    rendered = []
    summary_keys = {"id", "gate", "phase", "domain", "node", "task", "accountable_owner", "priority", "truth_state", "initial_status"}
    detail_keys = [k for k in rows[0].keys() if k not in summary_keys]
    for r in rows:
        details = detail_list(r, detail_keys)
        rendered.append(
            f'<tr {data_attrs(r, facets)}><td>{code_text(r["id"])}<br>{status_chip(r["row_class"])}</td>'
            f'<td>{status_chip(r["gate"])}<br><span class="muted">{esc(r["phase"])}</span></td>'
            f'<td>{esc(r["domain"])}<br><span class="muted">{esc(r["node"])}</span></td>'
            f'<td><strong>{esc(r["task"])}</strong><details><summary>Complete instruction, evidence, dependencies, and rollback</summary>{details}</details></td>'
            f'<td>{esc(r["accountable_owner"])}<br>{status_chip(r["priority"])}<br>{status_chip(r["truth_state"])}</td>'
            f'<td>{status_chip(r["initial_status"])}</td></tr>'
        )
    head = "<tr><th>ID / class</th><th>Gate</th><th>Domain / node</th><th>Atomic task</th><th>Owner / priority / truth</th><th>Initial state</th></tr>"
    return filter_bar("tasks", rows, facets) + f'<div class="table-wrap registry-wrap"><table id="tasks"><thead>{head}</thead><tbody>{"".join(rendered)}</tbody></table></div>'


def parameter_table(rows: list[dict[str, str]]) -> str:
    facets = ["category", "status", "accountable_owner", "gate"]
    summary = {"id", "category", "name", "symbol", "declared_value", "unit", "status", "accountable_owner", "phase", "gate"}
    detail_keys = [k for k in rows[0].keys() if k not in summary]
    out = []
    for r in rows:
        out.append(
            f'<tr {data_attrs(r, facets)}><td>{code_text(r["id"])}</td><td>{esc(r["category"])}</td>'
            f'<td><strong>{esc(r["name"])}</strong><br>{code_text(r["symbol"])}</td>'
            f'<td><strong>{esc(r["declared_value"])}</strong><br><span class="muted">{esc(r["unit"])}</span></td>'
            f'<td>{status_chip(r["status"])}<br>{esc(r["accountable_owner"])}<br>{status_chip(r["gate"])}</td>'
            f'<td><details><summary>Scope, exact rule, boundary, failure, source, and review</summary>{detail_list(r, detail_keys)}</details></td></tr>'
        )
    head = "<tr><th>ID</th><th>Category</th><th>Name / symbol</th><th>Declared value / unit</th><th>Status / owner / gate</th><th>Normative detail</th></tr>"
    return filter_bar("parameters", rows, facets) + f'<div class="table-wrap registry-wrap"><table id="parameters"><thead>{head}</thead><tbody>{"".join(out)}</tbody></table></div>'


def formula_table(rows: list[dict[str, str]]) -> str:
    facets = ["gate", "owner", "phase"]
    summary = {"id", "name", "semantic_version", "owner", "phase", "gate", "formula"}
    detail_keys = [k for k in rows[0].keys() if k not in summary]
    out = []
    for r in rows:
        out.append(
            f'<tr {data_attrs(r, facets)}><td>{code_text(r["id"])}<br>{status_chip(r["gate"])}</td>'
            f'<td><strong>{esc(r["name"])}</strong><br>{code_text(r["semantic_version"])}<br><span class="muted">{esc(r["owner"])}</span></td>'
            f'<td><pre class="formula-code">{esc(r["formula"])}</pre></td>'
            f'<td><details><summary>Inputs, units, timing, parameters, lifecycle, invalid behavior, mirror, identity, tests</summary>{detail_list(r, detail_keys)}</details></td></tr>'
        )
    head = "<tr><th>ID / gate</th><th>Name / version / owner</th><th>Normative formula</th><th>Complete semantics</th></tr>"
    return filter_bar("formulas", rows, facets) + f'<div class="table-wrap registry-wrap"><table id="formulas"><thead>{head}</thead><tbody>{"".join(out)}</tbody></table></div>'


def wiring_table(rows: list[dict[str, str]]) -> str:
    facets = ["gate", "phase", "readiness"]
    summary = {"id", "name", "producer", "contract", "consumers", "authority", "gate", "phase", "readiness", "failure_behavior"}
    detail_keys = [k for k in rows[0].keys() if k not in summary]
    out = []
    for r in rows:
        out.append(
            f'<tr {data_attrs(r, facets)}><td>{code_text(r["id"])}<br>{status_chip(r["gate"])}<br>{status_chip(r["readiness"])}</td>'
            f'<td><strong>{esc(r["name"])}</strong><br>{code_text(r["contract"])}</td>'
            f'<td>{esc(r["producer"])}<br><span class="arrow">→</span><br>{text(r["consumers"])}</td>'
            f'<td>{text(r["authority"])}</td><td>{text(r["failure_behavior"])}</td>'
            f'<td><details><summary>Binding, partitioning, ordering, telemetry, rollback, verification</summary>{detail_list(r, detail_keys)}</details></td></tr>'
        )
    head = "<tr><th>ID / gate / readiness</th><th>Edge / contract</th><th>Producer → consumers</th><th>Authority</th><th>Failure behavior</th><th>Complete plumbing</th></tr>"
    return filter_bar("wiring", rows, facets) + f'<div class="table-wrap registry-wrap"><table id="wiring"><thead>{head}</thead><tbody>{"".join(out)}</tbody></table></div>'


def verification_table(rows: list[dict[str, str]]) -> str:
    facets = ["gate", "criticality", "suite", "initial_status", "source"]
    summary = {"verification_id", "gate", "criticality", "suite", "test", "required_result", "initial_status"}
    detail_keys = [k for k in rows[0].keys() if k not in summary]
    out = []
    for r in rows:
        out.append(
            f'<tr {data_attrs(r, facets)}><td>{code_text(r["verification_id"])}<br>{status_chip(r["gate"])}</td>'
            f'<td>{esc(r["suite"])}<br>{status_chip(r["criticality"])}</td><td><strong>{esc(r["test"])}</strong></td>'
            f'<td>{text(r["required_result"])}</td><td>{status_chip(r["initial_status"])}</td>'
            f'<td><details><summary>Stimulus, evidence, source, and linked tasks</summary>{detail_list(r, detail_keys)}</details></td></tr>'
        )
    head = "<tr><th>ID / gate</th><th>Suite / criticality</th><th>Test</th><th>Required result</th><th>Initial state</th><th>Complete definition</th></tr>"
    return filter_bar("verifications", rows, facets) + f'<div class="table-wrap registry-wrap"><table id="verifications"><thead>{head}</thead><tbody>{"".join(out)}</tbody></table></div>'


def generic_registry(table_id: str, rows: list[dict[str, str]], facets: list[str], preferred: list[str] | None = None) -> str:
    if not rows:
        return "<p>No records.</p>"
    headers = preferred or list(rows[0].keys())
    head = "".join(f"<th>{esc(h.replace('_', ' '))}</th>" for h in headers)
    body = []
    for r in rows:
        cells = "".join(f"<td>{text(r.get(h, ''))}</td>" for h in headers)
        body.append(f'<tr {data_attrs(r, facets)}>{cells}</tr>')
    return filter_bar(table_id, rows, facets) + f'<div class="table-wrap registry-wrap"><table id="{esc(table_id)}"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def extract_rc1_main() -> str:
    path = RC1_DIR / "TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_1.0.0_RC1.html"
    source = path.read_text(encoding="utf-8")
    match = re.search(r"<main[^>]*>(.*?)</main>", source, flags=re.S | re.I)
    if not match:
        raise RuntimeError("RC1 main content not found")
    body = match.group(1)
    body = re.sub(
        r'<img\s+class="topology"\s+src="data:image/png;base64,[^"]+"\s+alt="[^"]*"\s*/?>',
        '<div class="callout info"><strong>Topology image deduplicated.</strong><div>See the embedded target-state topology in Chapter 02 of this RC3 document.</div></div>',
        body,
        flags=re.I,
    )
    body = re.sub(
        r'<a\b(?=[^>]*\bhref="(?!#|https?://|mailto:)[^"]+\.html")[^>]*>(.*?)</a>',
        lambda m: f'<span class="muted legacy-link">{m.group(1)}</span>',
        body,
        flags=re.S | re.I,
    )
    return body


def build() -> None:
    tasks = read_csv("task_registry.csv")
    dependencies = read_csv("dependency_edges.csv")
    acceptance = read_csv("acceptance_criteria.csv")
    verifications = read_csv("verification_registry.csv")
    gates = read_csv("gate_registry.csv")
    parameters = read_csv("declared_parameter_registry.csv")
    formulas = read_csv("formula_registry.csv")
    bindings = read_csv("formula_parameter_bindings.csv")
    golden = read_csv("golden_test_vectors.csv")
    wiring = read_csv("wiring_registry.csv")
    crosswalk = read_csv("rc1_crosswalk.csv")
    traceability = read_csv("traceability.csv")
    sources = read_csv("source_registry.csv")
    blocking = [r for r in parameters if r.get("status") == "BLOCKING_OWNER_DECISION"]

    topology_data = "data:image/png;base64," + base64.b64encode(
        (SOURCES / "01-06_TRIAD_MASTER_TOPOLOGY_ILLUSTRATIVE_OVERVIEW_V3-1-.png").read_bytes()
    ).decode("ascii")

    reproducibility_inputs = [
        ROOT / "build_origin_v7_complete_master_rc3.py",
        RC1_DIR / "TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_1.0.0_RC1.html",
        RC2_DIR / "manifest.json",
        CANON / "control_bundle.json",
        *[CANON / name for name in [
            "task_registry.csv", "dependency_edges.csv", "acceptance_criteria.csv",
            "verification_registry.csv", "gate_registry.csv", "declared_parameter_registry.csv",
            "formula_registry.csv", "formula_parameter_bindings.csv", "golden_test_vectors.csv",
            "wiring_registry.csv", "rc1_crosswalk.csv", "traceability.csv", "source_registry.csv",
        ]],
        *sorted((RC2_DIR / "schemas").glob("*.json")),
        SOURCES / "01-06_TRIAD_MASTER_TOPOLOGY_ILLUSTRATIVE_OVERVIEW_V3-1-.png",
        SOURCES / "02-INVESTIGATION-MCP-FOR-LIKO.md",
        SOURCES / "03-MCP-COMPLETE-BOOK.md",
    ]
    reproducibility_manifest = [
        {"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in reproducibility_inputs
    ]
    digest_rows = [[code_text(row["path"]), code_text(row["sha256"]), esc(f'{row["bytes"]:,} bytes')] for row in reproducibility_manifest]

    gate_counts = Counter(r["gate"] for r in tasks)
    gate_rows = []
    for r in gates:
        gate_rows.append([
            status_chip(r["gate"]), esc(r["phase"]), esc(r["name"]), esc(str(gate_counts.get(r["gate"], 0))),
            text(r["entry"]), text(r["exit"]), text(r["automatic_fail"]), code_text(r["receipt"]), text(r["derived_pass_rule"]),
        ])

    blocker_rows = []
    for r in blocking:
        blocker_rows.append([
            code_text(r["id"]), code_text(r["symbol"]), status_chip(r["declared_value"]), esc(r["unit"]),
            esc(r["gate"]), text(r["exact_rule"]), text(r["failure_behavior"]), esc(r["accountable_owner"]),
        ])

    authority_rows = [
        ["E00", "Raw venue/data facts and immutable ingress evidence", "MUST NOT construct structures, size, decide, or trade."],
        ["E01", "Canonical market state, entity resolution, finalized bars/books, watermarks and quality", "MUST NOT infer ORIGIN structures or apply portfolio risk."],
        ["E02-V7 / ORIGIN", "Deterministic features, causal structures, reactions, complete edge hypotheses and withdrawals", "No credentials, orders, position ownership, sizing, or intelligence mutation."],
        ["E03–E06", "Forecasts, specialists, fusion/calibration, language/knowledge treatment", "Excluded from deterministic proof population; may be separately measured later."],
        ["E07", "Eligibility, policy admission, conflict arbitration and one hypothesis per opportunity/risk cell", "MUST NOT determine order quantity or venue command."],
        ["E08", "Portfolio limits, risk reservations, sizing, exposure, leverage and execution authorization", "Sole sizing authority; MUST NOT define market structures or send venue-native orders."],
        ["E09", "Venue orchestration, keys, orders, acknowledgements, fills, positions, protection and reconciliation", "Sole money-fact authority; emergency taker may only reduce verified exposure."],
        ["E10", "Outcomes, attribution, net P&L, performance and governed learning artifacts", "Derives from E09 facts; MUST NOT originate, alter, or infer fills."],
    ]

    correction_rows = [
        ["Topology status", "Target-state illustration", "Never evidence of deployed wiring. Every as-built edge requires a current receipt."],
        ["E02 contract", "feature_set.v1 only", "Add strict structure_atom.v2, structure_transition.v2, reaction_event.v1, edge_candidate.v2 and candidate transition contracts."],
        ["E06 contract", "Not declared", "Declare calibrated_forecast/knowledge treatment contracts or keep E06 outside the deterministic path."],
        ["Sizing", "E07 and E08 both imply sizing", "E08 alone sizes; E07 admits and arbitrates only."],
        ["Execution input", "Decision/risk boxes imply loose handoff", "E09 accepts exact execution_authorization.v2 and emits immutable order/fill/position/protection facts."],
        ["Fill truth", "fill.v1/v2 lineage insufficient", "Keep older contracts immutable; dual-publish strict fill.v3 with symbol, side, position role, account, fees and full lineage."],
        ["Outcome truth", "E10 P&L attribution", "E10 computes from E09 facts and cannot rewrite venue identity or money events."],
        ["Transport", "Bus-style target", "Current hash-chained file ledger remains Phase-0 binding; NATS is future until provisioned and certified."],
    ]

    laws = [
        "Every semantic output must be reproducible from immutable source evidence, exact code, exact contract bytes, exact parameters, and a declared watermark.",
        "Origin time, confirmation time, availability time, publication time, and execution time are separate fields; none may be backdated or inferred from another.",
        "All structure geometry uses integer ticks, quantity uses integer step units, and time uses integer UTC/monotonic units with declared rounding.",
        "A forming bar cannot confirm a structure whose specification requires a finalized bar.",
        "A centered pivot is available only after its right-hand confirmation window closes; historical plotting must not move availability backward.",
        "Structure identity is stable across restarts and geometry revisions; lifecycle state is monotonic and terminal states never reactivate.",
        "Risk thresholds, leverage, stop floors, and portfolio budgets must never enter structure detection geometry.",
        "LONG logic is canonical and SHORT is a mechanically mirrored property unless an asymmetric trial is separately versioned and preregistered.",
        "Missing, stale, gapped, ambiguous, or unknown safety-material inputs produce a named abstention or quarantine, never zero or a guessed default.",
        "Published contract bytes are immutable; breaking semantics or required fields create a new major contract and explicit dual-read/write migration.",
        "Exactly one authoritative producer lease exists per scoped fact family; stale epochs and overlapping money writers are rejected.",
        "ORIGIN emits complete hypotheses but never sizes, holds credentials, submits, amends, cancels, or reconciles venue orders.",
        "E07 admits; E08 sizes and authorizes; E09 acts and records money truth; E10 attributes outcomes. No node may silently absorb another node’s authority.",
        "Normal entries and exits are post-only maker. A taker order is legal only for an audited, position-reducing emergency exit and may never open, add, or reverse exposure.",
        "Unknown submit outcomes and ambiguous positions stop new exposure and trigger reconciliation; retries require the original idempotency identity.",
        "Shadow, simulated, dark, canary, and money populations are distinct and may never be averaged or relabeled.",
        "A safety canary proves safety only. Profitability requires a preregistered, adequately powered, net-of-all-costs prospective money sample.",
        "Every capsule, threshold family, symbol subset, side, regime, and exit variant belongs to an immutable trial family with multiplicity controls.",
        "Promotion changes one scope dimension at a time and requires a signed gate receipt; any changed digest makes dependent evidence stale.",
        "Any NOT_RATIFIED consequential value resolves to SAFE_HOLD or DENY. Implementers have no authority to invent a number.",
        "P0 evidence cannot be waived. A waiver-like status, empty evidence set, open blocker, missing signature, or builder-as-sole-reviewer must be rejected by the receipt evaluator.",
    ]
    laws_html = '<div class="laws">' + "".join(f'<div class="law"><b>{i:02d}</b><span>{esc(v)}</span></div>' for i, v in enumerate(laws, 1)) + "</div>"

    mcp_rows = [
        ["Evidence date", "2026-08-07", "Dated snapshot; not represented as current runtime truth on 2026-08-09."],
        ["Shadow plane", "225,133 scored rows in the investigation snapshot", "Counterfactual resolver population; not live P&L."],
        ["Money plane", "332 fills / 128 decisions / four symbols", "Venue facts and fees, but money WR/EV were not measurable under fill.v1."],
        ["Population overlap", "126 fill-carrying decisions present in bank; zero in scored shadow population", "DISJOINT; never combine denominators."],
        ["Liquidity", "328 maker / 4 taker", "Snapshot reports four maker-law breaches; this is not a current compliance claim."],
        ["fill.v1 gaps", "No side/position role; no symbol", "Entry/exit and instrument attribution cannot be guessed. ORIGIN requires strict fill.v3."],
        ["MCP surface", "207 tools / 23 families; 142 exposed by default", "Eight families dark in the dated configuration."],
        ["Unavailable evidence", "NATS, Prometheus and unbuilt artifact probes", "Honest unavailable is correct; absence blocks corresponding gate evidence."],
        ["Authority", "Read plus two append-only off-bus writes", "propose_action and record_checkup append proposal/checkup evidence only; no MCP operation may reach runtime or money control."],
    ]

    venue_rows = [
        ["Routes", code_text("/public") + " depth/book; " + code_text("/market") + " trades/mark/kline; " + code_text("/private") + " user data", "Unrouted connections receive only public-category streams after legacy retirement."],
        ["Connection lifecycle", "24-hour maximum; ping every 3 minutes; pong required within 10 minutes", "Planned jittered reconnect, overlap without duplicate authority, heartbeat and session identity are mandatory."],
        ["Limits", "10 incoming messages/second; maximum 1,024 streams/connection", "Subscription control must budget messages and shard deterministically."],
        ["Local book bootstrap", "Buffer diff events → REST snapshot → discard stale → bridge U/u → require pu continuity", "Any pu break reinitializes from snapshot; no best-effort continuation."],
        ["Book quantities", "Absolute quantity at price; quantity zero removes level", "Do not accumulate as deltas."],
        ["User truth", "Prefer user-data stream for order/position status during volatility", "REST is reconciliation evidence, not a substitute for private-stream lifecycle."],
        ["Verification", "Official pages last modified 2026-08-08; checked 2026-08-09", "Re-verify at Gate G1 and pin evidence digest/date before deployment."],
    ]

    source_declarations = [
        ["TOPOLOGY_V3_CLASS", "ILLUSTRATIVE_TARGET_SUPERSEDED", "The picture is orientation only; corrected written authority and wiring control."],
        ["MCP_EVIDENCE_AS_OF", "2026-08-07", "Every MCP count and health statement carries this date."],
        ["CURRENT_RUNTIME_STATE", "UNKNOWN_UNTIL_FRESH_ATTESTATION", "No dated report authorizes a current-state claim."],
        ["MCP_AUTHORITY", "READ_PLUS_TWO_APPEND_ONLY_OFF_BUS_WRITES", "propose_action and record_checkup append evidence/proposals only; neither can become a runtime or money-control seam."],
        ["PUBLIC_MCP_AUTH_AS_BUILT", "DEVICE_PAIRING@2026-08-07", "Direct-token mode is a target requirement, not verified as-built behavior."],
        ["DIRECT_TOKEN_AUTH", "TARGET_NOT_VERIFIED", "Must be designed, threat-modeled, tested and independently evidenced before use."],
        ["LAN_MCP_AUTH", "UNAUTHENTICATED@2026-08-07_SECURITY_EXCEPTION", "A 0.0.0.0 unauthenticated bind fails the production security gate unless an independently verified network boundary protects it."],
        ["NATS_STATUS", "NOT_PROVISIONED_AT_AUDIT", "Logical subjects remain transport-neutral; file ledger is the initial binding."],
        ["PROMETHEUS_CRITICAL_COVERAGE", "UNAVAILABLE_AT_AUDIT", "Freshness, clock, watchdog and execution-quality targets were not certified."],
        ["SHADOW_AND_MONEY", "STRICTLY_SEPARATE_PLANES", "No blended numerator, denominator, score or claim."],
        ["MONEY_WR_EV", "NOT_MEASURABLE_UNTIL_STRICT_FILL_LINEAGE", "fill.v1 cannot distinguish economic role and lacks native symbol."],
        ["FILL_V1_V2", "IMMUTABLE", "Do not retrofit strict semantics into permissive deployed versions."],
        ["STRICT_MONEY_CONTRACT", "fill.v3", "Dual-publish from one raw venue fact; incomplete v3 is quarantined."],
        ["E02_AUTHORITY", "FEATURES_STRUCTURES_CANDIDATES_ONLY", "No sizing, credentials, execution or money truth."],
        ["E07_AUTHORITY", "ELIGIBILITY_ARBITRATION_POLICY_NO_FINAL_SIZE", "E07 selects economic intent but not final quantity."],
        ["E08_AUTHORITY", "SOLE_FINAL_SIZING_RISK_RESERVATION", "Unknown exposure/limits denies new or increasing exposure."],
        ["E09_AUTHORITY", "COMMANDS_KEYS_ORDERS_FILLS_POSITIONS_PROTECTION_RECONCILIATION", "Sole money-fact originator."],
        ["E10_AUTHORITY", "DERIVED_OUTCOMES_ATTRIBUTION_ONLY", "Never creates, rewrites, suppresses or relabels a fill."],
        ["LEARNING_MUTATION", "FORBIDDEN", "Learning proposes versioned artifacts; promotion is a separate signed authority event."],
        ["NORMAL_EXECUTION", "MAKER_FIRST_POST_ONLY", "GTX rejection never falls through to taker."],
        ["TAKER_AUTHORITY", "E09_EMERGENCY_VERIFIED_EXPOSURE_REDUCTION_ONLY", "Cannot open, add, reverse or trade an unknown position."],
        ["DARK_FAMILY", "NOT_EQUAL_AVAILABLE", "Built, exposed, reachable, data-backed, healthy and authoritative are distinct states."],
        ["DEPLOYED", "NOT_EQUAL_ARMED", "Deployment and producer authority are separate signed events."],
        ["PROCESS_UP", "NOT_EQUAL_HEALTHY", "Health requires dependency, offset, freshness, watermark and authority evidence."],
        ["MISSING_EVIDENCE", "NOT_EQUAL_ZERO", "Unavailable, timeout, unknown and not-implemented remain distinct honest-null states."],
        ["DEPRECATION", "NOT_EQUAL_REMOVAL", "Drain proof requires zero writers, readers, credentials, state ownership and rollback dependency."],
        ["TOPOLOGY_PHASE_DURATIONS", "ILLUSTRATIVE_NOT_CONTRACTUAL", "Week labels are planning hints, not delivery promises or gate waivers."],
        ["TOPOLOGY_KEY_METRICS", "ILLUSTRATIVE_TARGET_NOT_RATIFIED_AND_UNMEASURED", "No latency, freshness, fill, slippage, availability or replay target is claimed achieved."],
    ]

    rc1_conflicts = [
        ["Experiment axes", "Legacy/ORIGIN and deterministic/intelligence both use control/treatment language.", "Every record carries engine_cohort ∈ {LEGACY_COMPARATOR, ORIGIN_CANDIDATE} and intelligence_arm ∈ {DETERMINISTIC_CONTROL, INTELLIGENCE_TREATMENT}. Never collapse the axes."],
        ["Dark writer lease", "Candidate publication is lease-gated while dark mode asks for no candidate-authority lease.", "Use a technical_writer_lease/epoch for every journal writer. A distinct money_selection_lease is absent in connected-dark mode. Dark ORIGIN may publish evidence but is physically incapable of money selection."],
        ["Contract/topic closure", "Several catalog contracts lack explicit edge bindings; several wiring names lack catalog contracts.", "G0 remains SAFE_HOLD until every contract has schema bytes, writer, readers, storage, ACL, partition, ordering, idempotency, replay, retention, null behavior, rollback and verification."],
        ["Exit reduction", "RC1 test XL06 says every exit is reduceOnly, conflicting with Binance hedge mode.", "Every exit MUST reduce exposure. One-way and hedge payload compilers are separate: use only venue-legal side/positionSide/reduceOnly/closePosition combinations; forbidden combinations reject."],
        ["Protection ARMED", "One state table permits transport Algo ACK/NEW to mean ARMED.", "ARMED requires authoritative private-stream/open-algo reconciliation for the exact account, symbol, side, quantity, trigger and client/economic identity. Submit ACK alone remains REQUESTED."],
        ["Protection liquidity", "Maker-only ordinary exit and triggered protection were not reconciled.", "Triggered protection first issues a bounded post-only maker reduction. Only a separately authorized emergency condition may escalate the verified residual to F22 IOC reduction; cohorts remain separate."],
        ["ADR-013–020", "Eight proposed ADRs are used as normative assumptions elsewhere.", "They are RC3 target requirements but remain SAFE_HOLD at their dependent gate until individually signed: command seam, file-ledger binding, stable structure ID, protected swing, emergency tiers, net-EV objective, canary assignment and fenced production authority."],
        ["Directional-change units", "RC1 mixes price units/ticks and undeclared rational terms.", "F03 errata below controls. All inputs are integer ticks; no division by tick_size after conversion."],
        ["FVG lifecycle", "First contact cannot directly reach midpoint/filled; midpoint lacks expiry/invalidation.", "On each event apply precedence DATA_INVALID→INVALIDATED→EXPIRED→FILLED→MIDPOINT_FILLED→PARTIAL→TOUCHED. Every active nonterminal state can expire/invalidate; one event transitions directly to the highest satisfied state."],
        ["OB lifecycle", "First touch can cross mitigation/break thresholds without a reachable direct transition.", "Apply DATA_INVALID→BROKEN→EXPIRED→MITIGATED→PARTIAL→TOUCHED and transition directly to the highest satisfied state. Original zone remains frozen."],
        ["Swing initialization", "‘two high + two low pairs’ is ambiguous.", "Initialize only after an alternating available sequence contains at least two confirmed highs and two confirmed lows; compare the latest two of each type. Until then state is UNINITIALIZED."],
        ["Candidate identity", "publication_occurrence can change across retry/restart.", "candidate_id hashes capsule version, reaction_id, parameter digest and deterministic variant ordinal. The ordinal is derived from immutable sorted variant keys; retries reuse it."],
        ["Precedence chain", "RC1 document precedence omits Structure Semantics.", "RC3 order is signed decision→RC3 laws/errata→contract schemas→formula/parameter registry→structure semantics→state machines→wiring→runbooks→examples."],
        ["G-1 verification", "RC1 checklist/runbook require G-1 while its promotion matrix begins at G0.", "RC2 G-1 is retained and mandatory. No later gate starts without a current secure as-built baseline receipt."],
        ["P0 waiver", "Historical result UI permits waiver-like outcomes.", "P0 WAIVED is invalid. Receipt schemas and semantic validator must reject it, reject empty evidence and reject unresolved blockers."],
        ["RC1 dependency field", "Inventory IDs and prose are used as dependencies.", "RC1 rows are scope parents only. The RC2 task-to-task DAG controls sequence after the RC3 defects below are repaired."],
        ["Freshness", "Pinned code and dated MCP/venue sources can be mistaken for current deployment truth.", "Every release receipt pins observed_at/expires_at and exact build/config/contract/data/account/venue scope. Stale evidence cannot pass."],
    ]

    rc2_defects = [
        ["RC2-VAL-01", "False-positive semantic validation", "validation_report PASS checks structure but not verification gates or linked task IDs.", "G0+ SAFE_HOLD until an independent semantic validator covers every registry and receipt invariant."],
        ["RC2-VER-02", "Composite invalid gate values", "182 preserved RC1 tests use values such as G2/G3 or G4/G6/G9.", "Replace scalar gate with canonical gates[]; validate every member against G-1,G0…G9."],
        ["RC2-VER-03", "Dangling task links", "17 SEM tests point to nonexistent CTL-G2/G3-03.", "Create explicit valid task-edge mappings; unknown target is a hard validation error."],
        ["RC2-VER-04", "Legacy tests not enforced", "All 408 preserved RC1 tests are absent from task verification_refs, acceptance criteria and traceability.", "Attach every test to at least one required task/criterion and applicable gate. No gate may pass before closure."],
        ["RC2-WBS-05", "Atomicity overstated", "407 scope-closure rows require future child decomposition; 56 gap rows include broad projects.", "Call the 1,088 rows implementation controls. A scope parent cannot PASS while undecomposed required work remains."],
        ["RC2-BIND-06", "Formula bindings under-specified", "103 links lack semantic slot, cardinality, condition, scope, precedence and consuming node/edge.", "Introduce binding.v2 with those fields; mutually exclusive canary/production budgets must never be co-applied."],
        ["RC2-FORM-07", "Formula/vector contradictions", "F00/F01/F03/F11/F13/F19/F20/F21 and GV-005/011/017 conflict or underdefine behavior.", "The RC3 errata table below controls; source rows remain audit history and cannot be implemented verbatim."],
        ["RC2-STRUCT-08", "Structure semantics incomplete", "F06 max_span, F08 protection, F12 quote-notional/zone, TTL bindings, F17 minimum depth and F19 merge law remain incomplete.", "Affected structures/capsules cannot pass G2/G3 until exact declarations and golden/property vectors exist."],
        ["RC2-MAKER-09", "Maker policy drift", "PAR-179 proposes three ticks, while ratified Maker Law allows five order-book levels; ticks are not levels.", "RC3 F21 amendment uses observed same-side book-level ordinals 0–4. PAR-179 is superseded and must not be activated."],
        ["RC2-BOUND-10", "Intelligence leaks into deterministic gate", "PAR-153 forecast latency is terminal for G8 despite E03–E06 exclusion from deterministic proof.", "Move to the intelligence treatment gate; deterministic G8 cannot depend on forecast latency."],
        ["RC2-SCHEMA-11", "Money and domain schemas missing", "RC1 catalog names 30 contracts and RC2 wiring names 25; their union is 35, but only three governance receipt schemas are supplied.", "G0 remains SAFE_HOLD until all 35 union contracts have schema bytes, exact edges, examples, compatibility fixtures and generated-client tests."],
        ["RC2-RECEIPT-12", "Governance schemas permissive", "A syntactically valid PASS can have no evidence, open blockers, empty approvals/signature or missing digests.", "Add JSON Schema conditionals plus semantic transition validator; PASS requires nonempty exact-scope evidence, independent signature and zero blockers."],
        ["RC2-TRACE-13", "Traceability not closed", "Generated/free-text/misclassified requirement links have no requirement registry; release ZIP is not self-regenerating.", "Create requirement and inventory registries; type-check every reference; include generators and pinned inputs in the reproducible release source bundle."],
    ]

    formula_errata = [
        ["F00", "Split event parsing from proposal snapping.", "Venue fact price/quantity must divide the exact metadata tick/step with zero remainder or quarantine. Order quantity floor-to-step belongs only to F20/F22; maker price selection belongs to F21."],
        ["F01", "Remove undeclared venue_closed dependency.", "A trade-built bar finalizes only after UTC bucket end plus watermark/allowed-lateness closure. Exchange-status data is a separately versioned quality input, never inferred from trades."],
        ["F03 / GV-005", "Remove undeclared reversal_bps and k_vol terms.", "Proposed v1 formula: delta_ticks=max(5,ceil_div(ATR14_ticks,4)); freeze at each new provisional extreme; confirm on difference ≥delta. G2 remains blocked until PAR-036 is signed."],
        ["F06", "Declare max_span and cluster slots.", "No equal-level cluster implementation passes G2 until tolerance, max_span, minimum members and pivot type are separately bound, unit-checked and covered by drift-chain/boundary vectors."],
        ["F08", "Complete protected-swing reducer.", "Specify exact eligible swing pairing, pending pullback creation, continuation-BOS promotion, CHOCH precedence, double-BOS handling and restart vectors before G2."],
        ["F11", "Collapse duplicate move declarations.", "Use one proposed parameter: D_ticks=max(5,ceil_div(3×ATR14_before_origin_ticks,2)); PAR-158 controls, PAR-045 is redundant and must be deprecated. Equality passes."],
        ["F12", "Remove undefined body quote-notional tie-break; bind zone and TTL.", "Search at most W preceding finalized bars; select the latest opposing origin by origin time/index, then lexicographically smallest immutable source ID. No candle-body volume estimate is permitted. Zone convention and TTL are required versioned bindings; causal OB needs its own golden vector."],
        ["F13 / GV-011", "Two-close reclaim is controlling.", "After excursion, first qualifying close creates RECLAIM_PENDING; the second consecutive qualifying finalized close confirms. Any nonqualifying close resets count. Ordinal 3 is outside the proposed horizon."],
        ["F17", "Minimum depth is mandatory.", "Tilt is null unless total registered quote depth meets a declared positive minimum. Missing minimum blocks G2; zero denominator is null, never neutral zero."],
        ["F19", "Stable opportunity identity.", "cluster_id=hash(version,params,instrument,side,root_candidate_id), where root is the earliest (availability,candidate_id) at cluster creation. Later members append revisions and never re-root; cross-cluster attachment chooses earliest root deterministically and records aliases."],
        ["F20", "Bind budgets by activation mode and convert rate costs to quote-per-quantity.", "CANARY selects PAR-069 only; PRODUCTION selects PAR-070 only; unavailable selected budget denies. Let r_entry=max(current account maker fee rate,0), r_exit=max(nonnegative current fee rates for every campaign-authorized exit liquidity class), and b=PAR-079/10000. With linear-contract multiplier m, entry/exit price E/S in quote price, entry_notional_per_qty=m×|E| and exit_notional_per_qty=m×|S|: unit_loss_quote_per_qty=m×|E−S|+entry_notional_per_qty×(r_entry+b)+exit_notional_per_qty×(r_exit+b). Use exact rationals, never round cost down, and floor final quantity to step. Unknown rate, conversion, exit class, exposure, stop or selected budget denies."],
        ["GV-017", "Correct the isolated cost vector and its dimensional basis.", "With NAV=10,000, selected B=1 quote, E=100, S=99, m=1, r_entry=r_exit=0 explicitly for this isolated vector, and b=2/10000 per side: entry cost=.02, exit cost=.0198, unit_loss=1.0398 quote/qty, qty_raw=0.961723408…, step=.001→qty=.961. Production uses current nonnegative account fee rates and the exact entry/exit notional bases above."],
        ["F21 / PAR-179", "Use book levels, not three ticks, and require a nonempty feasible set.", "Enumerate same-side observed levels ordinal 0..4. BUY selects the most aggressive bid level inside [zone_low,zone_high] and below best_ask; SELL selects the most aggressive ask level inside the zone and above best_bid. If none exists, refuse. GTX remains final maker guard."],
        ["F22", "Exposure-reduction invariant controls payload shape.", "Quantity≤fresh reconciled residual, post-fill absolute exposure must decrease, sign flip forbidden. One-way and hedge payload compilers are separately certified; reduceOnly is not a universal encoding."],
    ]

    fill_v3_fields = [
        ["Venue scope", "venue, account_id, environment, venue_session_id", "Must be native/attested; account or environment ambiguity quarantines the record and blocks attribution."],
        ["Venue identity", "fill_id, venue_trade_id, venue_order_id, client_order_id", "Venue IDs and internal IDs remain distinct; duplicate venue trade identity is idempotent."],
        ["Economic lineage", "economic_purpose_id, campaign_id, intent_id, decision_id, candidate_id, execution_authorization_id", "Every applicable ID is required natively from the persisted command lineage; no post-hoc fuzzy join."],
        ["Instrument", "canonical_instrument_id, canonical_symbol, venue_symbol, instrument_metadata_revision", "Symbol alias alone is insufficient."],
        ["Position semantics", "side, position_side, position_mode, role", "role enum: ENTRY, ORDINARY_EXIT, PROTECTION, EMERGENCY_REDUCTION, LIQUIDATION. UNKNOWN is not money-complete. Standalone fee/funding corrections are venue_account_event.v2 facts, not fills."],
        ["Economics", "price_ticks, quantity_steps, quote_notional, contract_multiplier_revision, liquidity", "liquidity is MAKER or TAKER from venue fact; quantities and price use exact metadata revisions."],
        ["Costs", "fee_amount, fee_asset, fee_quote_amount, fee_conversion_mark_id, rebate_amount", "Missing fee conversion leaves outcome unresolved; rebates never erase adverse-cost buffers in sizing."],
        ["Clocks", "venue_event_at_us, received_at_us, persisted_at_us", "Preserve all three; publication time cannot substitute for venue time."],
        ["Provenance", "raw_event_digest, contract_manifest_sha256, config_digest, build_digest, producer_epoch", "The normalized record must trace to one immutable raw venue fact and current fenced producer."],
        ["Reconciliation", "reconciliation_status, reconciliation_revision, position_effect_steps", "Money-complete requires venue/account reconciliation and an exact signed position effect."],
    ]

    rc3_task_overrides = [
        ["CTL-G2-03", "PAR-045 and PAR-158 both hard-required", "Remove PAR-045 as redundant. Retain corrected PAR-158 only after its proposed value is signed. Until then G2 cannot pass."],
        ["CTL-G6-03", "PAR-179 hard-required (three ticks)", "PAR-179 is superseded. Replace with RC3-PAR-EXEC-001 / MAKER_MAX_BOOK_LEVELS=5 observed same-side levels, ordinals 0..4. This ratified Maker Law is not measured in ticks."],
        ["CTL-G8-03", "PAR-153 forecast latency hard-required", "Remove from deterministic G8. Forecast latency belongs only to an intelligence-treatment certification path."],
        ["FORM-F18-07 / FORM-F19-07", "Trace to W03–W05 feature/structure edges", "Trace candidate geometry and opportunity clustering to W06 ORIGIN_CANDIDATE edge; retain structure dependencies separately as inputs."],
        ["FORM-F20-07…FORM-F23-07", "Missing actual G6 execution wiring trace", "Bind F20→W11/W13, F21→W14/W15, F22→W13/W14/W15/W18/W19, and F23→W16/W18/W20."],
        ["W06 / W07 / W08", "Treatment/control labels conflate engine and intelligence axes", "Rename W06 ORIGIN_CANDIDATE, W07 LEGACY_COMPARATOR, W08 ENGINE_COHORT_DIVERGENCE. Intelligence-arm comparison is a separate typed edge."],
        ["182 preserved verification rows", "Scalar gate contains composite strings", "Migrate to gates[] and require every listed gate; no slash-delimited pseudo-gate may enter the evaluator."],
        ["17 SEM verification rows", "linked_task_ids includes nonexistent CTL-G2/G3-03", "Replace with exact valid task mappings after semantic ownership review; affected tests remain mandatory and blocking."],
        ["408 preserved RC1 tests", "Disconnected from task/criterion/traceability enforcement", "Create required verification edges before any gate receipt. Reference-only display is insufficient."],
    ]

    catalog_contracts = [
        "market_event.v2", "market_state.v2", "feature_snapshot.v2", "structure_atom.v2",
        "structure_transition.v2", "reaction_event.v1", "edge_candidate.v2",
        "edge_candidate_transition.v1", "decision.v2", "risk_decision.v2",
        "risk_reservation.v1", "execution_authorization.v2", "emergency_exit_authorization.v1",
        "execution_cmd.v2", "order_event.v2", "fill.v3", "venue_account_event.v2",
        "position_event.v2", "protection_event.v2", "outcome.v2", "trial_registration.v1",
        "divergence_record.v1", "producer_lease.v1", "engine_attestation.v1",
        "service_heartbeat.v1", "contract_bundle.manifest.v1", "activation_manifest.v1",
        "compatibility_manifest.v1", "quarantine_record.v1", "replay_receipt.v1",
    ]
    wiring_contracts = sorted({r["contract"] for r in wiring})
    contract_union = sorted(set(catalog_contracts) | set(wiring_contracts))
    catalog_only = sorted(set(catalog_contracts) - set(wiring_contracts))
    wiring_only = sorted(set(wiring_contracts) - set(catalog_contracts))
    contract_closure_rows = [
        ["Catalog ∩ wiring", str(len(set(catalog_contracts) & set(wiring_contracts))), "; ".join(sorted(set(catalog_contracts) & set(wiring_contracts))), "Must have schema plus an exact edge."],
        ["Catalog only", str(len(catalog_only)), "; ".join(catalog_only), "Add explicit producer/consumer/storage/ACL/ordering/replay wiring."],
        ["Wiring only", str(len(wiring_only)), "; ".join(wiring_only), "Add contract catalog entry and field-level schema."],
        ["Union requiring schema closure", str(len(contract_union)), "; ".join(contract_union), "All 35 require signed schema bytes, fixtures, compatibility and generated-client tests before G0."],
    ]

    named_rejection_rows = [
        ["INELIGIBLE_VENUE_ENV_UNVERIFIED", "Any production-connected fill/order/position fact lacks a verified venue environment.", "Reject/quarantine; no eligibility, attribution or money claim."],
        ["VENUE_HEDGE_REDUCE_ONLY_FORBIDDEN", "Binance hedge-position payload contains reduceOnly where the certified compiler forbids it.", "Reject before submission; do not retry with guessed flags."],
        ["VENUE_REDUCE_ONLY_WITH_CLOSE_POSITION_FORBIDDEN", "Payload combines reduceOnly and closePosition.", "Reject before submission; preserve attempted bytes as evidence."],
        ["POSITION_MODE_ACCOUNT_EXCLUSIVITY", "One account mixes one-way and hedge assumptions across symbols, bundles or external/orphan positions.", "Deny the entire affected authority scope until account-wide reconciliation proves one mode."],
        ["TESTNET_VENUE_IN_BUNDLE", "Any testnet venue/account/order/fill appears in a production evidence or activation bundle.", "Refuse the whole bundle; never drop only the offending member."],
    ]

    overlay_parameters = [
        {"id":"RC3-PAR-EXEC-001","name":"MAKER_MAX_BOOK_LEVELS","declared_value":"5","unit":"observed same-side nonempty book levels","status":"RATIFIED_MAKER_LAW","gate":"G6","owner":"E09","exact_rule":"Enumerate ordinals 0,1,2,3,4 from current same-side best; ticks and levels are never interchangeable.","failure_behavior":"No feasible level inside frozen zone -> named maker refusal; no taker fallback."},
        {"id":"RC3-PAR-MONEY-001","name":"FILL_V3_ROLE_ENUM","declared_value":"ENTRY|ORDINARY_EXIT|PROTECTION|EMERGENCY_REDUCTION|LIQUIDATION","unit":"closed enum","status":"DECLARED_RC3","gate":"G0","owner":"Contracts/E09","exact_rule":"Every fill has one native economic role; standalone fee/funding corrections remain venue_account_event.v2 facts.","failure_behavior":"Unknown/missing role quarantines fill.v3 and blocks outcome completion."},
        {"id":"RC3-PAR-CONTRACT-001","name":"DOMAIN_CONTRACT_SCHEMA_UNION_COUNT","declared_value":str(len(contract_union)),"unit":"distinct contract names","status":"DECLARED_RC3_FROM_UNION","gate":"G0","owner":"Contracts","exact_rule":"Union of RC1 30-name catalog and RC2 25-name wiring registry; 20 overlap, 10 catalog-only, 5 wiring-only.","failure_behavior":"Any missing schema/edge keeps G0 SAFE_HOLD."},
        {"id":"RC3-PAR-MCP-001","name":"MCP_OFF_BUS_APPEND_WRITES","declared_value":"propose_action|record_checkup","unit":"closed tool set as of 2026-08-07","status":"VERIFIED_AS_BUILT_2026_08_07","gate":"G-1","owner":"MCP/Security","exact_rule":"Both append evidence/proposal records off bus and execute no runtime or money command.","failure_behavior":"Any additional write verb or bus reachability fails security baseline."},
        {"id":"RC3-PAR-EXP-001","name":"ENGINE_COHORT_ENUM","declared_value":"LEGACY_COMPARATOR|ORIGIN_CANDIDATE","unit":"closed enum","status":"DECLARED_RC3","gate":"G4","owner":"Validation","exact_rule":"Identifies which deterministic engine produced the candidate.","failure_behavior":"Missing/unknown cohort makes paired evidence unusable."},
        {"id":"RC3-PAR-EXP-002","name":"INTELLIGENCE_ARM_ENUM","declared_value":"DETERMINISTIC_CONTROL|INTELLIGENCE_TREATMENT","unit":"closed enum","status":"DECLARED_RC3","gate":"G4","owner":"Validation","exact_rule":"Independent axis identifying whether E03-E06 may affect the hypothesis.","failure_behavior":"Missing/unknown arm makes treatment evidence unusable."},
        {"id":"RC3-PAR-STRUCT-001","name":"EQUAL_LEVEL_MAX_SPAN","declared_value":"NOT_RATIFIED","unit":"integer ticks","status":"BLOCKING_RESEARCH_DECISION","gate":"G2","owner":"Research","exact_rule":"Finite nonnegative integer bound on total member span, separate from anchor tolerance.","failure_behavior":"F06 unavailable; equal-level structures and dependent capsules SAFE_HOLD."},
        {"id":"RC3-PAR-STRUCT-002","name":"BOOK_TILT_MIN_QUOTE_DEPTH","declared_value":"NOT_RATIFIED","unit":"quote notional across declared bands","status":"BLOCKING_RESEARCH_DECISION","gate":"G2","owner":"Research","exact_rule":"Finite positive minimum denominator before F17 tilt may be emitted.","failure_behavior":"F17 returns null; dependent flow capsule SAFE_HOLD."},
        {"id":"RC3-PAR-STRUCT-003","name":"PROTECTED_SWING_REDUCER_VERSION","declared_value":"NOT_RATIFIED","unit":"semantic reducer version","status":"BLOCKING_RESEARCH_DECISION","gate":"G2","owner":"Research/ORIGIN","exact_rule":"Must declare pairing, pending creation, continuation promotion, CHOCH/double-BOS precedence and replacement.","failure_behavior":"F08 remains UNAVAILABLE; no protected-swing-dependent candidate."},
    ]
    overlay_parameter_ownership = {
        "RC3-PAR-EXEC-001": ("E09", ["Validation"]),
        "RC3-PAR-MONEY-001": ("Contracts", ["E09", "E10"]),
        "RC3-PAR-CONTRACT-001": ("Contracts", ["Architecture", "Validation"]),
        "RC3-PAR-MCP-001": ("Security", ["Evidence"]),
        "RC3-PAR-EXP-001": ("Validation", ["Contracts"]),
        "RC3-PAR-EXP-002": ("Validation", ["Contracts"]),
        "RC3-PAR-STRUCT-001": ("Research", ["ORIGIN", "Validation"]),
        "RC3-PAR-STRUCT-002": ("Research", ["ORIGIN", "Validation"]),
        "RC3-PAR-STRUCT-003": ("Research", ["ORIGIN", "Validation"]),
    }
    for overlay_parameter in overlay_parameters:
        accountable_owner, responsible_roles = overlay_parameter_ownership[overlay_parameter["id"]]
        overlay_parameter["owner"] = accountable_owner
        overlay_parameter["accountable_owner"] = accountable_owner
        overlay_parameter["responsible_roles"] = responsible_roles

    overlay_formulas = [
        {"id":"F00","status":"RC3_SUPERSEDES_RC2","formula":"price_ticks=exact_div(venue_price,tick_size); qty_steps=exact_div(venue_qty,step_size); nonzero remainder -> QUARANTINE","dependencies":"instrument_metadata_revision","gate":"G1"},
        {"id":"F01","status":"BLOCKED_PENDING_PAR-025_RATIFICATION","formula":"bucket=[k*delta,(k+1)*delta) UTC; O/H/L/C/base_volume/quote_volume/trade_count derive from accepted trades ordered under the registered tie rule. Let partition_watermark=max_seen_event_time-PAR-025; FINALIZED iff bucket_end<=partition_watermark. Boundary equality passes. Forming, GAP and later data revisions remain distinct; venue_closed is never an input.","dependencies":"timeframe;PAR-025 allowed event lateness;partition watermark;accepted trade source and tie/duplicate policy","gate":"G1"},
        {"id":"F03","status":"BLOCKED_PENDING_PAR-036_RATIFICATION","formula":"delta_ticks=max(5,ceil_div(ATR14_ticks,4)); freeze at each provisional extreme; confirm iff reversal_difference_ticks>=delta_ticks","dependencies":"PAR-036;F02","gate":"G2"},
        {"id":"F05","status":"BLOCKED_MISSING_LINKED_GOLDEN_VECTOR","formula":"upper_t=max(H[t-N:t]); lower_t=min(L[t-N:t]); current observation excluded","dependencies":"N;price_source;complete valid prior window","gate":"G2"},
        {"id":"F06","status":"BLOCKED_PENDING_RC3-PAR-STRUCT-001","formula":"accept p iff abs(p-anchor)<=tolerance and span(members union p)<=max_span; anchor never drifts","dependencies":"tolerance;RC3-PAR-STRUCT-001;min_members;source_pivot_type","gate":"G2"},
        {"id":"F07","status":"BLOCKED_MISSING_LINKED_GOLDEN_VECTOR","formula":"session interval=[start,end) UTC; open=first, high=max, low=min; final high/low only after session watermark","dependencies":"calendar_id/version;observation_source;boundary_rule","gate":"G2"},
        {"id":"F08","status":"BLOCKED_PENDING_RC3-PAR-STRUCT-003_AND_GOLDEN","formula":"NO IMPLEMENTATION AUTHORIZED until exact reducer version is ratified; insufficient state remains UNINITIALIZED","dependencies":"RC3-PAR-STRUCT-003;F03;F09","gate":"G2"},
        {"id":"F11","status":"BLOCKED_PENDING_PAR-158_RATIFICATION","formula":"For each finalized j in [o+1,o+H], Bull: move_j=C_j-O_o; body_ratio_j=abs(C_j-O_j)/max(1,H_j-L_j); close_loc_j=(C_j-L_j)/max(1,H_j-L_j); D_ticks=max(5,ceil_div(3*ATR14_before_origin_ticks,2)). The earliest j qualifies iff move_j>=D_ticks, C_j>O_j, body_ratio_j>=beta and close_loc_j>=lambda; Bear mirrors exactly. PAR-045 is absent; equality at D_ticks, beta and lambda passes; no qualifying bar inside H expires the origin and any path gap invalidates it.","dependencies":"PAR-158;F02;H;beta;lambda;finalized gap-free path","gate":"G2"},
        {"id":"F10","status":"BLOCKED_PENDING_EXACT_TTL_INVALIDATION_BINDING","formula":"RC2 three-bar geometry retained; bind PAR-051 or a ratified successor explicitly and apply terminal precedence before touch","dependencies":"min_gap_ticks;touch_source;ratified TTL;invalidation rule","gate":"G2"},
        {"id":"F12","status":"BLOCKED_PENDING_ZONE_TTL_BINDINGS_AND_GOLDEN","formula":"Search <=W prior finalized bars; choose latest opposing origin, tie min immutable source_id; bull_zone=[L_o,O_o], bear_zone=[O_o,H_o]; confirm only linked same-direction BOS within H_bos","dependencies":"W,H_bos,opposing_predicate,zone_convention,TTL,F11,F09","gate":"G2"},
        {"id":"F13","status":"BLOCKED_PENDING_PARAMETER_RATIFICATION","formula":"After excursion, first qualifying finalized close -> RECLAIM_PENDING; second consecutive qualifying close -> CONFIRMED; any failure resets hold_count=0; ordinal3 outside horizon","dependencies":"PAR-048;PAR-049;PAR-165","gate":"G2"},
        {"id":"F16","status":"BLOCKED_MISSING_LINKED_GOLDEN_VECTOR","formula":"For each sequence-continuous valid best-book update n: e_n=I(Pb_n>=Pb_prev)*Qb_n-I(Pb_n<=Pb_prev)*Qb_prev-I(Pa_n<=Pa_prev)*Qa_n+I(Pa_n>=Pa_prev)*Qa_prev; OFI=sum(e_n) over the exact registered window. Emit only after minimum_updates and the window watermark; a normalized variant is a distinct semantic version and divides by registered average depth only when the declared minimum depth is met. Gap, duplicate ambiguity, crossed/invalid book, expired TTL or zero/insufficient normalization depth yields null, never zero.","dependencies":"window;normalization variant;minimum updates;TTL;valid sequence-continuous absolute-quantity book;minimum normalization depth","gate":"G2"},
        {"id":"F17","status":"BLOCKED_PENDING_RC3-PAR-STRUCT-002","formula":"tilt=(bid_quote_depth-ask_quote_depth)/(bid_quote_depth+ask_quote_depth); emit only if denominator>=declared minimum; zero/insufficient denominator -> null","dependencies":"distance bands;RC3-PAR-STRUCT-002;TTL;valid book","gate":"G2"},
        {"id":"F19","status":"RC3_SUPERSEDES_RC2_IDENTITY","formula":"cluster_id=hash(version,params,instrument,side,root_candidate_id); root fixed at creation by min(availability,candidate_id); later members append revisions and never re-root","dependencies":"cluster_window,overlap_predicate,arbitration_rule","gate":"G3"},
        {"id":"F20","status":"RC3_DIMENSIONAL_AND_SCOPE_OVERRIDE","formula":"Select B by activation_mode: CANARY->PAR-069, PRODUCTION->PAR-070, otherwise DENY. Let r_e=max(current account entry-maker fee rate,0); r_x=max(all nonnegative fee rates across campaign-authorized exit liquidity classes); b=PAR-079/10000; n_e=m*abs(E); n_x=m*abs(S); unit_loss=m*abs(E-S)+n_e*(r_e+b)+n_x*(r_x+b). Require unit_loss>0. qty_budget=floor_to_step(B/unit_loss); qty_final=floor_to_step(min(qty_budget,position_capacity,portfolio_capacity,exposure_capacity,leverage_capacity,concentration_capacity,venue_max_qty)). A missing/stale selected budget, fee rate, conversion, exit class, limit/exposure snapshot, min-notional/filter input or any failed venue filter DENIES; no other activation budget may substitute.","dependencies":"activation_mode;selected budget only;PAR-078 current account fee snapshot;PAR-079;linear contract multiplier revision;entry/stop prices;authorized exit liquidity classes;position/portfolio/exposure/leverage/concentration/venue capacities;min-notional and venue filters","gate":"G6"},
        {"id":"F21","status":"RATIFIED_RC3_OVERRIDE","formula":"Build levels from nonempty same-side observed book levels with ordinals 0..4 only. BUY selects the most aggressive bid level inside the closed frozen zone and strictly below best_ask; SELL selects the most aggressive ask level inside the closed frozen zone and strictly above best_bid. Submit LIMIT GTX/post-only. Reprice only to another feasible ordinal 0..4 inside the same frozen zone, after the registered minimum interval, while reprice_count and TTL remain; apply the registered queue/departure policy. Empty feasible set, stale book, exhausted count/TTL or GTX rejection -> REFUSE/EXPIRE with no taker fallback.","dependencies":"RC3-PAR-EXEC-001;valid current book;current authorization;frozen zone;reprice count;minimum interval;TTL;queue/departure policy","gate":"G6"},
        {"id":"F22","status":"RC3_PAYLOAD_INVARIANT_OVERRIDE","formula":"For long SELL, worst_price=floor_to_tick(best_bid*(1-s_bps/10000)); for short BUY, worst_price=ceil_to_tick(best_ask*(1+s_bps/10000)). Compile an IOC marketable limit with qty=floor_to_step(min(requested_qty,abs(fresh_reconciled_residual))). Every attempt must prove abs(position_after)<abs(position_before) and no sign flip. One-way and hedge payloads compile through separate certified account-mode laws. The registered trigger, maker deadline, retry/tier budget and cooldown bound attempts; unknown/stale position, book, connectivity, authorization or mode blocks automation and escalates.","dependencies":"fresh reconciled position/residual;valid best book;s_bps;emergency authorization;trigger/deadline;retry/tier budget;cooldown;mode-certified compiler","gate":"G6"},
    ]

    formula_field_overrides = {
        "F00": {
            "units_rounding": "Exact decimal/rational division to checked signed integers; no floor, ceil or tolerance at ingress. Any nonzero remainder quarantines the complete source event.",
            "invalid_behavior": "Unknown/stale metadata, overflow or either nonintegral conversion quarantines the complete event; no partial price/quantity output.",
        },
        "F01": {
            "availability_rule": "FINALIZED only after the UTC bucket end and watermark plus allowed-lateness closure; forming or corrected bars never masquerade as the prior revision.",
            "invalid_behavior": "Rejected, duplicated or late trades follow the registered data-revision policy; an empty required bucket is GAP, never a synthetic flat bar.",
        },
        "F11": {"units_rounding": "Ticks are checked integers; D_ticks uses exact integer ceil_div; body and close-location ratios compare by cross multiplication."},
        "F16": {"units_rounding": "Price ticks and quantity steps only; indicator terms and window sums use checked integers; normalized variants use exact rational comparison."},
        "F20": {"units_rounding": "All money and rates use exact decimal/rational arithmetic on declared entry/exit notional bases; every capacity and final quantity rounds down to the venue step."},
        "F21": {"units_rounding": "Observed book-level ordinal is not a tick distance; select an existing integer-tick price and never synthesize an unobserved level."},
        "F22": {"units_rounding": "Worst-price bounds use exact rational math and outward tick rounding; residual quantity always steps down."},
    }
    for formula_override in overlay_formulas:
        formula_override.update({
            "semantic_version": f"triad.origin.v7.rc3.{formula_override['id'].lower()}.v1",
            "inputs": formula_override["dependencies"],
            "units_rounding": "Exact checked integer/rational arithmetic under the controlling instrument and parameter revisions; no binary floating point.",
            "availability_rule": f"Available only when status {formula_override['status']} is closed by current signed evidence and every declared dependency is current for the same scope.",
            "lifecycle_or_output": "The RC2 output type is retained only where compatible; every RC3 semantic change emits the RC3 formula version and immutable input/parameter/source ranges.",
            "invalid_behavior": "Any unmet dependency, invalid source state, ambiguous boundary or overflow returns the formula's named null/quarantine/refusal and keeps dependent gates in SAFE_HOLD.",
            "mirror_rule": "The source directional mirror is retained only where algebraically compatible with this complete RC3 formula; asymmetry requires a separately versioned rule.",
            "identity_material": f"{formula_override['id']} RC3 semantic version + exact source range + instrument/parameter/policy digests + causal clocks",
            "golden_boundary_tests": "Equality, one-unit-short/over, invalid-input, prefix, restart, duplicate and directional-mirror vectors under the linked RC3 gate verification.",
        })
        formula_override.update(formula_field_overrides.get(formula_override["id"], {}))

    overlay_wiring_operations = [
        {"id":"RC3-WOP-001","operation":"COPY_AND_OVERRIDE","wiring_id":"W06","base_wiring_id":"W06","inheritance":"Copy every canonical W06 field, then replace only the fields declared in this operation; inherited fields remain mandatory.","gate":"G3","target_name":"ORIGIN candidate publication","contract":"edge_candidate.v2","target_subject":"edge.candidates.v2.origin_candidate","required_typing":"engine_cohort=ORIGIN_CANDIDATE; intelligence_arm required independently","authority":"technical_writer_lease required; money_selection_lease absent in connected-dark mode","migration":"dual-publish old/new subjects until typed-consumer parity; old treatment alias then drains","verification":"RC3-V-G3-FORMULA-WIRING"},
        {"id":"RC3-WOP-002","operation":"COPY_AND_OVERRIDE","wiring_id":"W07","base_wiring_id":"W07","inheritance":"Copy every canonical W07 field, then replace only the fields declared in this operation; inherited fields remain mandatory.","gate":"G4","target_name":"Legacy comparator candidate publication","contract":"edge_candidate.v2","target_subject":"edge.candidates.v2.legacy_comparator","required_typing":"engine_cohort=LEGACY_COMPARATOR; intelligence_arm required independently","authority":"frozen comparator writer only; no ORIGIN or intelligence alias inference","migration":"dual-read during cohort-field backfill; missing cohort is unusable evidence","verification":"RC3-V-EXPERIMENT-AXES"},
        {"id":"RC3-WOP-003","operation":"COPY_AND_OVERRIDE","wiring_id":"W08","base_wiring_id":"W08","inheritance":"Copy every canonical W08 field, then replace only the fields declared in this operation; inherited fields remain mandatory.","gate":"G4","target_name":"Engine-cohort divergence","contract":"divergence_record.v1","target_subject":"edge.divergence.v1.engine_cohort","required_typing":"comparison_axis=ENGINE_COHORT; join ORIGIN_CANDIDATE versus LEGACY_COMPARATOR","authority":"evidence only; no E07/E08/E09 rights","migration":"preserve source rows; do not relabel ambiguous historical control/treatment evidence","verification":"RC3-V-EXPERIMENT-AXES"},
        {"id":"RC3-WOP-004","operation":"ADD_FULL_ROW","wiring_id":"W08A","base_wiring_id":None,"inheritance":"NONE; every canonical plumbing field is declared below.","phase":"P4","gate":"G4","target_name":"Intelligence-arm divergence","producer":"Edge comparator","contract":"divergence_record.v1","target_subject":"edge.divergence.v1.intelligence_arm","partition_key":"(input_offset_range, opportunity_cluster_id, engine_cohort)","consumers":"Evidence; promotion governance","required_typing":"comparison_axis=INTELLIGENCE_ARM; join DETERMINISTIC_CONTROL versus INTELLIGENCE_TREATMENT within one engine cohort","authority":"evidence only; no learning activation or money rights","ordering_idempotency":"Exact input offsets plus frozen manifests; one classified record per engine-cohort/opportunity/arm pair; immutable record ID.","readiness":"Both arm streams current or explicit MISSING_CONTROL/MISSING_TREATMENT; engine_cohort identical and typed.","failure_behavior":"Unmatched, retimed, cross-cohort or ambiguously typed outputs remain visible and NOT_MEASURABLE; no auto-resolution.","telemetry":"missing/extra/retimed/reidentified/geometry/lifecycle/unexplained counts by engine_cohort and intelligence_arm","rollback":"Stop the comparison window and seal partial evidence; never modify candidates or relabel historical rows.","verification":"RC3-V-EXPERIMENT-AXES","migration":"new typed edge; historical evidence lacking the independent arm field remains unusable"},
    ]

    overlay_formula_wiring_operations = [
        {"id":"RC3-TOP-001","operation":"REPLACE","source_controls":"FORM-F18-07|FORM-F19-07","formula_ids":"F18|F19","remove_wiring_ids":"W03|W04|W05","add_wiring_ids":"W06","status":"DECLARED_EXACT","reason":"Candidate geometry and opportunity clustering produce ORIGIN candidates; structure edges remain causal inputs, not the produced edge."},
        {"id":"RC3-TOP-002","operation":"ADD","source_controls":"FORM-F20-07","formula_ids":"F20","remove_wiring_ids":"","add_wiring_ids":"W11|W13","status":"DECLARED_EXACT","reason":"Sizing is consumed by the risk decision and exact authorization edges."},
        {"id":"RC3-TOP-003","operation":"ADD","source_controls":"FORM-F21-07","formula_ids":"F21","remove_wiring_ids":"","add_wiring_ids":"W14|W15","status":"DECLARED_EXACT","reason":"Maker selection compiles the internal command and is verified against the venue order lifecycle."},
        {"id":"RC3-TOP-004","operation":"ADD","source_controls":"FORM-F22-07","formula_ids":"F22","remove_wiring_ids":"","add_wiring_ids":"W13|W14|W15|W18|W19","status":"DECLARED_EXACT","reason":"Emergency reduction is authorization-, command-, order-, reconciled-position- and protection-scoped."},
        {"id":"RC3-TOP-005","operation":"ADD","source_controls":"FORM-F23-07","formula_ids":"F23","remove_wiring_ids":"","add_wiring_ids":"W16|W18|W20","status":"DECLARED_EXACT","reason":"Outcome arithmetic consumes strict fills and reconciled position facts and produces derived outcomes."},
    ]

    linkage_blockers = [
        {"id":"RC3-LINK-BLOCK-001","population":"182 preserved RC1 verification rows","defect":"slash-delimited composite scalar gates","required_migration":"materialize one canonical gates[] array per row and validate every member","status":"BLOCKING_UNMATERIALIZED_ROW_PATCHES","gate":"G2"},
        {"id":"RC3-LINK-BLOCK-002","population":"17 SEM verification rows","defect":"linked_task_ids points to nonexistent CTL-G2/G3-03","required_migration":"semantic owner must select exact existing task IDs; no inferred blanket replacement is authorized","status":"BLOCKING_OWNER_MAPPING","gate":"G2"},
        {"id":"RC3-LINK-BLOCK-003","population":"408 preserved RC1 verification rows","defect":"not required by an acceptance/task/gate edge","required_migration":"materialize row-level required edges after semantic ownership review; 408/408 coverage is mandatory","status":"BLOCKING_UNMATERIALIZED_ROW_PATCHES","gate":"G2"},
    ]

    binding_v2_required_fields = [
        {"field":"binding_id","rule":"stable unique identifier"},
        {"field":"formula_id / parameter_id","rule":"typed references that must exist in their controlling registries"},
        {"field":"semantic_slot","rule":"named formula input occupied by this binding"},
        {"field":"cardinality","rule":"EXACTLY_ONE, ZERO_OR_ONE, ONE_OR_MORE, or an explicit bounded count"},
        {"field":"condition","rule":"total deterministic predicate; mutually exclusive scopes must be provably disjoint"},
        {"field":"activation_scope","rule":"environment, cohort, arm, account, instrument, capsule and mode as applicable"},
        {"field":"precedence","rule":"explicit ordering or rejection for equal-priority matches"},
        {"field":"consumer","rule":"owning node plus exact wiring IDs"},
        {"field":"unit_contract","rule":"input/output dimensions and exact integer/rational conversion"},
        {"field":"failure_behavior","rule":"named fail-closed/null/quarantine behavior; no implicit default"},
        {"field":"lifecycle_status","rule":"ACTIVE, SUPERSEDED, RETIRED or BLOCKED; source rows never disappear silently"},
        {"field":"disposition_reason","rule":"mandatory for every non-ACTIVE binding"},
        {"field":"superseded_by","rule":"typed binding ID required when lifecycle_status=SUPERSEDED"},
        {"field":"source_binding_id","rule":"base RC2 binding ID for migration, otherwise null for an additive RC3 binding"},
    ]

    overlay_binding_operations = [
        {"id":"RC3-BOP-010","operation":"COPY_AND_OVERRIDE","binding_id":"FPB-0001","source_binding_id":"FPB-0001","formula_id":"F00","parameter_id":"PAR-001","semantic_slot":"ingress_price_wire_integer_ticks","cardinality":"EXACTLY_ONE","condition":"accepted venue price parse under exact metadata revision","activation_scope":"E01;G1;venue/instrument/metadata-revision exact scope","precedence":"AT_INGRESS_BEFORE_CANONICAL_EVENT_PUBLICATION","consumer":"E01","consuming_wiring_ids":"W01","unit_contract":"exact decimal venue price / exact tick_size -> signed int64 ticks; remainder must be zero","lifecycle_status":"ACTIVE","disposition_reason":"RC3 makes the already fail-closed price conversion explicit in binding.v2 at the consuming G1 gate.","superseded_by":None,"declared_value":"price_ticks=exact_div(venue_price,tick_size)","boundary_rule":"Any nonzero remainder, overflow or stale/unknown metadata quarantines the complete source event.","failure_behavior":"QUARANTINE_INGRESS_EVENT; no canonical event, candidate or order."},
        {"id":"RC3-BOP-007","operation":"COPY_AND_OVERRIDE","binding_id":"FPB-0002","source_binding_id":"FPB-0002","formula_id":"F00","parameter_id":"PAR-002","semantic_slot":"ingress_quantity_wire_integer_steps","cardinality":"EXACTLY_ONE","condition":"accepted venue quantity parse under exact metadata revision","activation_scope":"E01;G1;venue/instrument/metadata-revision exact scope","precedence":"AT_INGRESS_BEFORE_ANY_FEATURE_OR_ORDER_LOGIC","consumer":"E01","consuming_wiring_ids":"W01","unit_contract":"signed int64 exact integer steps","lifecycle_status":"ACTIVE","disposition_reason":"RC3 removes downstream order-floor semantics from ingress parsing while retaining the wire type.","superseded_by":None,"declared_value":"signed int64 exact integer steps","boundary_rule":"qty_steps=exact_div(venue_qty,step_size); any nonzero remainder quarantines the complete source event; no floor or tolerance.","failure_behavior":"QUARANTINE_INGRESS_EVENT on remainder, overflow or stale/unknown metadata."},
        {"id":"RC3-BOP-008","operation":"REMOVE","binding_id":"FPB-0009","source_binding_id":"FPB-0009","formula_id":"F01","parameter_id":"PAR-024","semantic_slot":"bar_finalization_predicate","cardinality":"EXACTLY_ONE","condition":"NEVER_AFTER_RC3","activation_scope":"ALL_RC3","precedence":"SUPERSEDED","consumer":"E01","consuming_wiring_ids":"W02","unit_contract":"predicate","lifecycle_status":"SUPERSEDED","disposition_reason":"The venue_closed predicate is noncausal/nonportable and conflicts with RC3 partition-watermark finalization.","superseded_by":"RC3-FPB-005","failure_behavior":"Any active reference to FPB-0009 rejects the effective bundle."},
        {"id":"RC3-BOP-001","operation":"REMOVE","binding_id":"FPB-0020","source_binding_id":"FPB-0020","formula_id":"F11","parameter_id":"PAR-045","semantic_slot":"displacement_min_move","cardinality":"EXACTLY_ONE","condition":"NEVER_AFTER_RC3","activation_scope":"ALL_RC3","precedence":"SUPERSEDED","consumer":"ORIGIN","consuming_wiring_ids":"W04|W05","unit_contract":"ticks","lifecycle_status":"SUPERSEDED","disposition_reason":"Duplicate displacement multiplier conflicts with the single corrected PAR-158 expression.","superseded_by":"FPB-0066","failure_behavior":"Any active reference to FPB-0020 rejects the effective bundle."},
        {"id":"RC3-BOP-002","operation":"REMOVE","binding_id":"FPB-0099","source_binding_id":"FPB-0099","formula_id":"F21","parameter_id":"PAR-179","semantic_slot":"maker_search_bound","cardinality":"EXACTLY_ONE","condition":"NEVER_AFTER_RC3","activation_scope":"ALL_RC3","precedence":"SUPERSEDED","consumer":"E09","consuming_wiring_ids":"W14|W15","unit_contract":"observed book levels, not ticks","lifecycle_status":"SUPERSEDED","disposition_reason":"Three ticks conflicts with the ratified five observed same-side level law.","superseded_by":"RC3-FPB-004","failure_behavior":"Any active reference to FPB-0099 rejects the effective bundle."},
        {"id":"RC3-BOP-003","operation":"ADD","binding_id":"RC3-FPB-001","source_binding_id":None,"formula_id":"F06","parameter_id":"RC3-PAR-STRUCT-001","semantic_slot":"equal_level_max_span","cardinality":"EXACTLY_ONE","condition":"structure_type=EQUAL_LEVEL","activation_scope":"ORIGIN;G2;instrument/timeframe/formula-version exact scope","precedence":"AFTER_TOLERANCE_CHECK_BEFORE_MEMBER_APPEND","consumer":"ORIGIN","consuming_wiring_ids":"W04|W05","unit_contract":"integer ticks","lifecycle_status":"BLOCKED","disposition_reason":"Parameter is NOT_RATIFIED.","superseded_by":None,"failure_behavior":"F06 unavailable and dependent capsules SAFE_HOLD."},
        {"id":"RC3-BOP-004","operation":"ADD","binding_id":"RC3-FPB-002","source_binding_id":None,"formula_id":"F08","parameter_id":"RC3-PAR-STRUCT-003","semantic_slot":"protected_swing_reducer_version","cardinality":"EXACTLY_ONE","condition":"formula_id=F08","activation_scope":"ORIGIN;G2;formula-version exact scope","precedence":"BEFORE_ANY_PROTECTED_SWING_STATE_MUTATION","consumer":"ORIGIN","consuming_wiring_ids":"W04|W05","unit_contract":"semantic reducer version","lifecycle_status":"BLOCKED","disposition_reason":"Reducer version is NOT_RATIFIED.","superseded_by":None,"failure_behavior":"F08 unavailable; state remains UNINITIALIZED/no candidate."},
        {"id":"RC3-BOP-005","operation":"ADD","binding_id":"RC3-FPB-003","source_binding_id":None,"formula_id":"F17","parameter_id":"RC3-PAR-STRUCT-002","semantic_slot":"minimum_total_quote_depth","cardinality":"EXACTLY_ONE","condition":"formula_id=F17","activation_scope":"ORIGIN;G2;instrument/band/formula-version exact scope","precedence":"BEFORE_DENOMINATOR_DIVISION","consumer":"ORIGIN","consuming_wiring_ids":"W03|W04","unit_contract":"quote notional across declared bands","lifecycle_status":"BLOCKED","disposition_reason":"Minimum quote depth is NOT_RATIFIED.","superseded_by":None,"failure_behavior":"F17 returns null; dependent capsule SAFE_HOLD."},
        {"id":"RC3-BOP-006","operation":"ADD","binding_id":"RC3-FPB-004","source_binding_id":None,"formula_id":"F21","parameter_id":"RC3-PAR-EXEC-001","semantic_slot":"maker_max_observed_book_levels","cardinality":"EXACTLY_ONE","condition":"normal maker execution path","activation_scope":"E09;G6;venue/account/instrument/authorization exact scope","precedence":"AFTER_FROZEN_ZONE_BEFORE_GTX_SUBMIT","consumer":"E09","consuming_wiring_ids":"W14|W15","unit_contract":"observed same-side nonempty book levels","lifecycle_status":"ACTIVE","disposition_reason":"Ratified RC3 Maker Law.","superseded_by":None,"failure_behavior":"Empty feasible set refuses; no taker fallback."},
        {"id":"RC3-BOP-009","operation":"ADD","binding_id":"RC3-FPB-005","source_binding_id":None,"formula_id":"F01","parameter_id":"PAR-025","semantic_slot":"partition_watermark_allowed_lateness","cardinality":"EXACTLY_ONE","condition":"F01 partition finalizes only when bucket_end<=partition_watermark where partition_watermark=max_seen_event_time-PAR-025","activation_scope":"E01;G1;venue/instrument/timeframe/partition/formula-version exact scope","precedence":"AFTER_WATERMARK_ADVANCE_BEFORE_FINALIZED_PUBLICATION","consumer":"E01","consuming_wiring_ids":"W02","unit_contract":"milliseconds on UTC event time","lifecycle_status":"BLOCKED","disposition_reason":"PAR-025 remains unratified; no FINALIZED bar can be authorized until signed.","superseded_by":None,"failure_behavior":"Unknown/stale watermark or unratified lateness => no FINALIZED bar; dependent structure SAFE_HOLD."},
    ]

    overlay_parameter_operations = [
        {"id":"RC3-POP-004","operation":"COPY_AND_OVERRIDE","source_parameter_id":"PAR-002","replacement_parameter_id":"PAR-002","effective_scope":"F00 ingress conversion in RC3","source_status_after_apply":"RATIFIED_RC3_OVERRIDE","declared_value":"signed int64 exact integer steps","exact_rule":"qty_steps=exact_div(exact_decimal(venue_qty),exact_decimal(step_size)); remainder must be zero; F00 never floors.","boundary_rule":"Any nonzero remainder, overflow or stale/unknown metadata quarantines the complete venue fact.","failure_behavior":"QUARANTINE venue fact; publish no canonical event, candidate or order.","reason":"Separate exact venue-fact conversion from downstream order-quantity rounding."},
        {"id":"RC3-POP-003","operation":"SUPERSEDE","source_parameter_id":"PAR-024","replacement_parameter_id":"PAR-025","effective_scope":"F01 in RC3","source_status_after_apply":"SUPERSEDED","reason":"The venue_closed predicate is removed; RC3 finalization uses the partition watermark and the separately ratified allowed-lateness parameter."},
        {"id":"RC3-POP-001","operation":"SUPERSEDE","source_parameter_id":"PAR-045","replacement_parameter_id":"PAR-158","effective_scope":"F11 in RC3","source_status_after_apply":"SUPERSEDED","reason":"One displacement minimum-move expression only; equality passes."},
        {"id":"RC3-POP-002","operation":"SUPERSEDE","source_parameter_id":"PAR-179","replacement_parameter_id":"RC3-PAR-EXEC-001","effective_scope":"F21 in RC3","source_status_after_apply":"SUPERSEDED","reason":"Observed book-level ordinals 0..4 replace the incompatible three-tick bound."},
    ]

    overlay_golden_vector_operations = [
        {"id":"RC3-GVOP-001","operation":"REPLACE","source_vector_id":"GV-005","linked_formula":"F03","inputs":"ATR14_ticks=20; provisional extreme frozen; reversal differences 4 and 5 ticks","expected":"delta_ticks=max(5,ceil(20/4))=5; reversal 4 fails and equality reversal 5 passes; no reversal_bps or k_vol term exists","status":"BLOCKED_UNTIL_PAR-036_RATIFIED"},
        {"id":"RC3-GVOP-002","operation":"REPLACE","source_vector_id":"GV-010","linked_formula":"F11","inputs":"ATR14_before_origin_ticks=10; move differences 14 and 15 ticks; use PAR-158 only","expected":"D_ticks=max(5,ceil(3*10/2))=15; 14 fails; 15 passes; PAR-045 absent","status":"BLOCKED_UNTIL_PAR-158_RATIFIED"},
        {"id":"RC3-GVOP-003","operation":"REPLACE","source_vector_id":"GV-011","linked_formula":"F13","inputs":"qualifying finalized closes at ordinals 1 and 2 after excursion; a nonqualifying close resets count","expected":"ordinal1=RECLAIM_PENDING; ordinal2=CONFIRMED only if consecutive; any intervening failure resets; ordinal3 outside proposed horizon","status":"BLOCKED_UNTIL_PAR-048_PAR-049_PAR-165_RATIFIED"},
        {"id":"RC3-GVOP-004","operation":"REPLACE","source_vector_id":"GV-017","linked_formula":"F20","inputs":"B=1 quote; E=100; S=99; m=1; r_entry=r_exit=0; b=2/10000 per side; step=.001","expected":"entry cost=.02; exit cost=.0198; unit_loss=1.0398 quote/qty; qty_raw=0.961723408...; floor_to_step=.961","status":"VALID_ISOLATED_COST_VECTOR"},
    ]

    receipt_v2_requirements = [
        {"schema":"evidence_receipt.v2","required_conditionals":"PASS requires nonempty exact scope, evidence IDs/digests, observed_at/expires_at, producer/build/config/contract/data digests and independent signature","hard_rejections":"empty evidence; stale scope; unresolved blocker; missing digest/signature; builder=reviewer"},
        {"schema":"task_status_event.v2","required_conditionals":"PASS transition requires all typed hard predecessors, acceptance criteria and verifications PASS for identical scope","hard_rejections":"illegal transition; unknown ID/gate; P0 WAIVED; undecomposed required scope; open P0/P1 blocker"},
        {"schema":"gate_receipt.v2","required_conditionals":"PASS requires predecessor receipt, complete required task/test sets, zero blockers, rollback/stop proof, current digests, expiry and independent approval","hard_rejections":"empty scope/evidence/approval; skipped predecessor; mismatch; stale receipt; any P0 waiver"},
        {"schema":"semantic_transition_validator.v1","required_conditionals":"cross-registry referential integrity, gate membership, identity separation and monotonic state transition checks run after JSON Schema validation","hard_rejections":"any structurally valid but semantically incomplete PASS"},
    ]

    overlay_tasks = [
        {"id":"RC3-TASK-GM1-MCP-WRITES","gate":"G-1","owner":"Security/MCP","task":"Enumerate and fence every MCP write surface","depends_on":"fresh tools/list + deployed/source parity","acceptance":"Exactly propose_action and record_checkup are append-only/off-bus, or a newer signed census names all differences; no route reaches bus/runtime/money control.","verification":"RC3-V-MCP-WRITES","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G0-CONTRACT-UNION","gate":"G0","owner":"Contracts","task":"Close all 35 catalog/wiring contract names","depends_on":"G-1 receipt","acceptance":"Every union member has signed field-level schema, writer/readers, edge, storage, ACL, partition, ordering, idempotency, replay, retention, null/failure behavior and compatibility fixtures.","verification":"RC3-V-CONTRACT-UNION","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G0-FILL-V3","gate":"G0","owner":"Contracts/E09/E10","task":"Implement and dual-publish strict fill.v3","depends_on":"RC3-TASK-G0-CONTRACT-UNION","acceptance":"100% required native fields and exact lineage in selected scope; v1/v2 unchanged; incomplete v3 quarantined; v2/v3 reconciliation zero unexplained divergence.","verification":"RC3-V-FILL-V3","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G0-RECEIPT-SCHEMAS-V2","gate":"G0","owner":"Governance/Contracts/Validation","task":"Implement additive strict evidence, task-status and gate-receipt v2 schemas","depends_on":"RC3-TASK-G0-CONTRACT-UNION","acceptance":"Published v2 JSON Schema bytes enforce all expressible nonempty scope/evidence/approval, blocker, digest, signature, expiry, predecessor and P0-waiver conditionals; cross-registry and transition semantics remain the downstream validator task.","verification":"RC3-V-RECEIPT-SCHEMAS-V2","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G0-TYPED-REFERENCE-REGISTRIES","gate":"G0","owner":"Governance/Contracts/Validation","task":"Create typed requirement and inventory registries and migrate free-text references","depends_on":"RC3-TASK-G0-CONTRACT-UNION","acceptance":"All 1,348 REQUIREMENT links resolve to a typed requirement registry; all 86 invalid/free-text INVENTORY links (82 unique references) resolve to typed inventory IDs or an explicit blocking disposition; zero untyped reference reaches a receipt.","verification":"RC3-V-TYPED-REFERENCE-REGISTRIES","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G1-INGRESS-FORMULAS","gate":"G1","owner":"E01/Contracts/Validation","task":"Implement corrected F00/F01 ingress formulas and bindings","depends_on":"G0 receipt;current instrument metadata;watermark policy","acceptance":"RC3-BOP-007/008/009/010 and RC3-POP-003/004 are materialized at G1: both venue price/quantity conversions exact-divide or quarantine, venue_closed is absent, PAR-025 is the sole allowed-lateness input, and UTC bucket/watermark boundary and replay vectors pass.","verification":"RC3-V-G1-FORMULAS","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G2-STRUCTURE-FORMULAS","gate":"G2","owner":"ORIGIN/Research/Validation","task":"Implement RC3 structure-formula overrides and close every G2 blocker","depends_on":"ratified referenced parameters;G1 receipt","acceptance":"F03/F05/F06/F07/F08/F10/F11/F12/F13/F16/F17 all reach IMPLEMENTED_AND_VERIFIED; missing vectors, max span, depth, reducer and TTL bindings are closed; dimension, mirror, prefix and restart tests pass.","verification":"RC3-V-G2-FORMULAS","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G2-BINDING-V2","gate":"G2","owner":"Contracts","task":"Complete binding.v2 migration for the 105-row effective registry","depends_on":"signed G1 receipt;semantic validator;binding.v2 schema","acceptance":"After the three G1 ingress source bindings are concretely handled, migrate every remaining preserved source row; retain FPB-0009/0020/0099 in lifecycle audit only; add RC3-FPB-001 through RC3-FPB-005; and emit exactly 105 active/effective rows with owner-ratified semantic slot, cardinality, condition, activation scope, precedence, consumer/edge, unit contract, lifecycle/disposition and named failure behavior. Zero BLOCKED_NOT_STARTED migration sentinel remains and no mutually exclusive values co-apply.","verification":"RC3-V-BINDING-V2","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G3-CLUSTER-FORMULA","gate":"G3","owner":"ORIGIN/E07/Validation","task":"Implement stable F19 opportunity identity and arbitration","depends_on":"G2 receipt;ratified cluster window/overlap/arbitration","acceptance":"Late members never change cluster_id; cross-cluster attachments follow frozen earliest-root rule; restart/prefix/alias vectors pass.","verification":"RC3-V-G3-FORMULA","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G3-FORMULA-WIRING","gate":"G3","owner":"Contracts","task":"Apply W06 candidate typing and the exact F18/F19 traceability replacement","depends_on":"RC3-TASK-G3-CLUSTER-FORMULA","acceptance":"RC3-WOP-001 and RC3-TOP-001 are materialized exactly: W06 is the typed ORIGIN_CANDIDATE publication edge; FORM-F18-07 and FORM-F19-07 add W06 as their produced edge, remove W03/W04/W05 as produced-edge links, and retain structure edges only as typed causal inputs.","verification":"RC3-V-G3-FORMULA-WIRING","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G4-EXPERIMENT-AXES","gate":"G4","owner":"Validation/Contracts","task":"Separate engine cohort from intelligence arm in candidate and divergence wiring","depends_on":"signed G3 receipt;typed W06/W07/W08 schemas","acceptance":"W06/W07 identify ORIGIN_CANDIDATE versus LEGACY_COMPARATOR; W08 compares only ENGINE_COHORT; W08A compares only INTELLIGENCE_ARM; neither axis is inferred from subject text.","verification":"RC3-V-EXPERIMENT-AXES","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G6-RISK-EXEC-FORMULAS","gate":"G6","owner":"E08","task":"Implement corrected F20/F21/F22 scope, maker and exposure-reduction formulas","depends_on":"signed G5 receipt;current fee/cost inputs;emergency policy;valid account compiler","acceptance":"Compiler fixtures prove CANARY and PRODUCTION branches are exclusive; an unavailable selected G7/G9 budget denies without preventing G6 compiler certification; rate costs convert through exact entry/exit notional bases; five-level maker selection and strict residual-reduction invariants pass.","verification":"RC3-V-G6-FORMULAS;RC3-V-F21-FIVE-LEVEL","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G6-FORMULA-WIRING","gate":"G6","owner":"E08/E09/E10/Contracts/Validation","task":"Apply the exact F20-F23 to W11-W20 traceability operations","depends_on":"RC3-TASK-G6-RISK-EXEC-FORMULAS","acceptance":"RC3-TOP-002 through RC3-TOP-005 are materialized with exact formula/control and W-ID sets; no unrelated edge is added or removed.","verification":"RC3-V-G6-FORMULA-WIRING","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G2-VERIFICATION-LINKS","gate":"G2","owner":"Validation/Governance","task":"Repair all preserved-test gates and enforcement edges","depends_on":"typed requirement/task/test registries","acceptance":"182 composite gates migrated to gates[]; 17 dangling links repaired; all 408 RC1 tests required by at least one typed task/criterion and applicable gate.","verification":"RC3-V-LEGACY-LINKAGE","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G6-MAKER-LAW","gate":"G6","owner":"E09/Validation","task":"Compile and prove five-level maker law","depends_on":"RC3-PAR-EXEC-001;RC3-TASK-G6-RISK-EXEC-FORMULAS","acceptance":"F21 chooses only observed same-side level ordinals 0..4 inside frozen zone; empty set refuses; GTX reject never becomes taker.","verification":"RC3-V-F21-FIVE-LEVEL","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G6-VENUE-GUARDS","gate":"G6","owner":"E09/Validation","task":"Preserve exact account/environment/mode rejection codes","depends_on":"certified one-way and hedge compilers;account reconciliation","acceptance":"All five named failure codes reproduce exactly for every prior attack; legal guards remain accepted.","verification":"RC3-V-VENUE-GUARD-CODES","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G8-DETERMINISTIC-SCOPE","gate":"G8","owner":"Validation/Governance","task":"Remove intelligence-only latency from deterministic economic certification","depends_on":"G7 receipt","acceptance":"Deterministic G8 has no E03-E06 dependency; forecast latency is evaluated only in a separately registered intelligence treatment path.","verification":"RC3-V-G8-SCOPE","status":"NOT_STARTED"},
        {"id":"RC3-TASK-GATE-SEMANTIC-VALIDATOR","gate":"G0","owner":"Governance/Validation","task":"Implement semantic validator beyond JSON/structural validity","depends_on":"all typed registries and receipt schemas","acceptance":"Reject unknown IDs/gates, empty PASS evidence/scope, open blockers, missing digests/signatures, illegal status transitions, builder-reviewer collision and every P0 waiver.","verification":"RC3-V-SEMANTIC-VALIDATOR","status":"NOT_STARTED"},
        {"id":"RC3-TASK-G0-REPRODUCIBLE-SOURCE-BUNDLE","gate":"G0","owner":"Release","task":"Publish a reproducible RC3 source bundle and effective-control artifact","depends_on":"semantic validator","acceptance":"Bundle the generator, every pinned input in reproducibility_input_manifest, overlay schema/applier, effective control bundle and validation report; a clean pinned environment regenerates byte-identical canonical JSON digests and semantically equivalent HTML with zero undeclared input.","verification":"RC3-V-REPRODUCIBLE-SOURCE-BUNDLE","status":"NOT_STARTED"},
    ]

    w08a_decomposition = [
        ("01", "Freeze W08A contract and authority", "Signed divergence_record.v1 schema and registry row declare the intelligence-arm subject, producer, consumers, evidence-only authority, independent arm/cohort fields and negative fixtures."),
        ("02", "Implement W08A producer path", "The sole comparator producer emits stable immutable IDs and exact input/manifests, refuses cross-cohort or ambiguously typed joins and has no candidate or money mutation path."),
        ("03", "Bind W08A transport and durable checkpoint", "The declared logical subject is bound to the certified durable ledger with writer fencing, hash chain, checkpoint, retention and backpressure; uncertified NATS remains unavailable."),
        ("04", "Implement W08A consumer validation and idempotency", "Consumers validate schema/version, arm/cohort types, source digests, exact offset range, producer epoch, order and identity before durable ACK or evidence mutation."),
        ("05", "Implement W08A failure and degraded-state behavior", "Missing, retimed, cross-cohort or ambiguous pairs remain explicit NOT_MEASURABLE evidence; no auto-resolution, candidate rewrite or learning activation occurs."),
        ("06", "Wire W08A observability and readiness", "Telemetry exposes missing/extra/retimed/reidentified/geometry/lifecycle/unexplained counts by engine cohort and intelligence arm; readiness is semantic and current."),
        ("07", "Execute W08A verification corpus", "Contract, exact-offset, duplicate, restart, reorder/gap, permission, incomplete-pair, two-axis and side-effect fixtures pass against the pinned row and build."),
        ("08", "Rehearse W08A cutover and rollback", "Additive cutover proves exact evidence parity; rollback stops the window and seals partial evidence without modifying candidates or relabeling history."),
    ]
    for suffix, task_name, acceptance_text in w08a_decomposition:
        overlay_tasks.append({
            "id": f"RC3-TASK-WIRE-W08A-{suffix}", "gate": "G4", "owner": "Contracts",
            "task": task_name, "depends_on": "typed predecessor populated below",
            "acceptance": acceptance_text, "verification": f"RC3-V-W08A-{suffix}", "status": "NOT_STARTED",
        })

    overlay_task_ownership = {
        "RC3-TASK-GM1-MCP-WRITES": ("Security", ["Evidence"]),
        "RC3-TASK-G0-CONTRACT-UNION": ("Contracts", ["Architecture", "Validation"]),
        "RC3-TASK-G0-FILL-V3": ("Contracts", ["E09", "E10", "Validation"]),
        "RC3-TASK-G0-RECEIPT-SCHEMAS-V2": ("Governance", ["Contracts", "Validation"]),
        "RC3-TASK-G0-TYPED-REFERENCE-REGISTRIES": ("Governance", ["Contracts", "Validation"]),
        "RC3-TASK-G1-INGRESS-FORMULAS": ("E01", ["Contracts", "Validation"]),
        "RC3-TASK-G2-STRUCTURE-FORMULAS": ("Research", ["ORIGIN", "Validation"]),
        "RC3-TASK-G2-BINDING-V2": ("Contracts", ["Research", "Validation"]),
        "RC3-TASK-G3-CLUSTER-FORMULA": ("ORIGIN", ["E07", "Validation"]),
        "RC3-TASK-G3-FORMULA-WIRING": ("Contracts", ["ORIGIN", "Validation"]),
        "RC3-TASK-G4-EXPERIMENT-AXES": ("Validation", ["Contracts"]),
        "RC3-TASK-G6-RISK-EXEC-FORMULAS": ("E08", ["E09", "Validation"]),
        "RC3-TASK-G6-FORMULA-WIRING": ("Contracts", ["E08", "E09", "E10", "Validation"]),
        "RC3-TASK-G2-VERIFICATION-LINKS": ("Validation", ["Governance"]),
        "RC3-TASK-G6-MAKER-LAW": ("E09", ["Validation"]),
        "RC3-TASK-G6-VENUE-GUARDS": ("E09", ["Validation"]),
        "RC3-TASK-G8-DETERMINISTIC-SCOPE": ("Validation", ["Governance"]),
        "RC3-TASK-GATE-SEMANTIC-VALIDATOR": ("Governance", ["Validation"]),
        "RC3-TASK-G0-REPRODUCIBLE-SOURCE-BUNDLE": ("Release", ["Validation", "Security"]),
    }
    for suffix, _task_name, _acceptance_text in w08a_decomposition:
        overlay_task_ownership[f"RC3-TASK-WIRE-W08A-{suffix}"] = ("Contracts", ["Validation", "Evidence"])
    for overlay_task in overlay_tasks:
        accountable_owner, responsible_roles = overlay_task_ownership[overlay_task["id"]]
        overlay_task["owner"] = accountable_owner
        overlay_task["accountable_owner"] = accountable_owner
        overlay_task["responsible_roles"] = responsible_roles

    overlay_dependency_declarations = {
        "RC3-TASK-GM1-MCP-WRITES": {"task_ids": [], "external": ["fresh tools/list", "deployed/source parity"]},
        "RC3-TASK-G0-CONTRACT-UNION": {"task_ids": ["CTL-GM1-06"], "external": []},
        "RC3-TASK-G0-FILL-V3": {"task_ids": ["RC3-TASK-G0-CONTRACT-UNION"], "external": ["raw venue fact fixtures"]},
        "RC3-TASK-G0-RECEIPT-SCHEMAS-V2": {"task_ids": ["RC3-TASK-G0-CONTRACT-UNION"], "external": ["published additive v2 schema namespace"]},
        "RC3-TASK-G0-TYPED-REFERENCE-REGISTRIES": {"task_ids": ["RC3-TASK-G0-CONTRACT-UNION"], "external": ["authoritative requirement owners", "inventory source corpus"]},
        "RC3-TASK-G1-INGRESS-FORMULAS": {"task_ids": ["CTL-G0-06"], "external": ["current instrument metadata", "watermark policy"]},
        "RC3-TASK-G2-STRUCTURE-FORMULAS": {"task_ids": ["RC3-TASK-G2-BINDING-V2"], "external": ["ratified referenced parameters"]},
        "RC3-TASK-G2-BINDING-V2": {"task_ids": ["CTL-G1-06", "RC3-TASK-GATE-SEMANTIC-VALIDATOR"], "external": ["binding.v2 field-level schema"]},
        "RC3-TASK-G3-CLUSTER-FORMULA": {"task_ids": ["CTL-G2-06"], "external": ["ratified cluster window", "overlap predicate", "arbitration rule"]},
        "RC3-TASK-G3-FORMULA-WIRING": {"task_ids": ["RC3-TASK-G3-CLUSTER-FORMULA"], "external": ["typed W06 schema"]},
        "RC3-TASK-G4-EXPERIMENT-AXES": {"task_ids": ["CTL-G3-06", "RC3-TASK-G3-FORMULA-WIRING"], "external": ["typed W06/W07/W08 schemas"]},
        "RC3-TASK-G6-RISK-EXEC-FORMULAS": {"task_ids": ["CTL-G5-06"], "external": ["current account fee snapshot", "ratified G6 cost representation", "emergency policy", "valid account compiler", "branch fixtures for unavailable G7/G9 budgets"]},
        "RC3-TASK-G6-FORMULA-WIRING": {"task_ids": ["RC3-TASK-G6-RISK-EXEC-FORMULAS"], "external": ["typed W11-W20 schemas"]},
        "RC3-TASK-G2-VERIFICATION-LINKS": {"task_ids": ["CTL-G1-06", "RC3-TASK-GATE-SEMANTIC-VALIDATOR"], "external": ["semantic owner map for 17 SEM rows", "row-level map for 408 legacy tests"]},
        "RC3-TASK-G6-MAKER-LAW": {"task_ids": ["RC3-TASK-G6-RISK-EXEC-FORMULAS"], "external": ["RC3-PAR-EXEC-001", "valid order-book fixtures"]},
        "RC3-TASK-G6-VENUE-GUARDS": {"task_ids": ["RC3-TASK-G6-RISK-EXEC-FORMULAS"], "external": ["certified one-way compiler", "certified hedge compiler", "account reconciliation"]},
        "RC3-TASK-G8-DETERMINISTIC-SCOPE": {"task_ids": ["CTL-G7-06"], "external": []},
        "RC3-TASK-GATE-SEMANTIC-VALIDATOR": {"task_ids": ["RC3-TASK-G0-RECEIPT-SCHEMAS-V2", "RC3-TASK-G0-TYPED-REFERENCE-REGISTRIES"], "external": ["all typed registries"]},
        "RC3-TASK-G0-REPRODUCIBLE-SOURCE-BUNDLE": {"task_ids": ["RC3-TASK-GATE-SEMANTIC-VALIDATOR"], "external": ["pinned clean-build runtime and toolchain manifest"]},
    }
    for index, (suffix, _task_name, _acceptance_text) in enumerate(w08a_decomposition):
        predecessors = ["CTL-G4-01", "RC3-TASK-G4-EXPERIMENT-AXES"] if index == 0 else [f"RC3-TASK-WIRE-W08A-{w08a_decomposition[index-1][0]}"]
        overlay_dependency_declarations[f"RC3-TASK-WIRE-W08A-{suffix}"] = {"task_ids": predecessors, "external": []}
    overlay_prerequisites = []
    for overlay_task in overlay_tasks:
        declaration = overlay_dependency_declarations[overlay_task["id"]]
        overlay_task["depends_on_task_ids"] = declaration["task_ids"]
        prerequisite_ids = []
        for requirement in declaration["external"]:
            prerequisite_id = f"RC3-PREREQ-{len(overlay_prerequisites)+1:03d}"
            prerequisite_ids.append(prerequisite_id)
            lowered = requirement.lower()
            if "parameter" in lowered or "ratified" in lowered or "policy" in lowered or "budget" in lowered:
                prerequisite_type = "SIGNED_POLICY_OR_PARAMETER_EVIDENCE"
            elif "schema" in lowered or "registry" in lowered or "compiler" in lowered:
                prerequisite_type = "DIGEST_BOUND_ARTIFACT"
            elif "fixture" in lowered:
                prerequisite_type = "TEST_FIXTURE_BUNDLE"
            else:
                prerequisite_type = "SCOPED_CURRENT_EVIDENCE"
            overlay_prerequisites.append({
                "id": prerequisite_id,
                "task_id": overlay_task["id"],
                "gate": overlay_task["gate"],
                "accountable_owner": overlay_task["accountable_owner"],
                "type": prerequisite_type,
                "requirement": requirement,
                "scope_rule": "Exact same build/config/contract/data/venue/account/campaign scope as the consuming task, where applicable.",
                "closure_rule": "Status becomes SATISFIED only with a nonempty immutable evidence_id, SHA-256, observed_at, expires_at and independent reviewer; otherwise it remains OPEN.",
                "status": "OPEN",
                "evidence_id": None,
                "evidence_sha256": None,
            })
        overlay_task["external_prerequisite_ids"] = prerequisite_ids
        overlay_task["depends_on"] = ";".join([*overlay_task["depends_on_task_ids"], *prerequisite_ids]) or "NONE"
        overlay_task["acceptance_id"] = "RC3-AC-" + overlay_task["id"].removeprefix("RC3-TASK-")
    for linkage_blocker in linkage_blockers:
        linkage_blocker["status"] = "OPEN_BLOCKER"
        linkage_blocker["resolution_task_id"] = "RC3-TASK-G2-VERIFICATION-LINKS"
        linkage_blocker["resolution_acceptance_id"] = "RC3-AC-G2-VERIFICATION-LINKS"
        linkage_blocker["resolution_verification_id"] = "RC3-V-LEGACY-LINKAGE"
        linkage_blocker["closure_rule"] = "Append a signed RESOLVED event only after the referenced task, acceptance criterion and verification PASS for the complete population; never mutate this finding in place."
        linkage_blocker["terminal_status_on_valid_closure"] = "RESOLVED_BY_SIGNED_EVENT"

    overlay_dag = [
        {"operation":"ADD","predecessor":"RC3-TASK-GM1-MCP-WRITES","successor":"CTL-GM1-03","reason":"The fresh MCP write-surface census is a hard G-1 predecessor."},
        {"operation":"REMOVE","predecessor":"PAR-045","successor":"CTL-G2-03","reason":"Duplicate displacement multiplier superseded by corrected PAR-158 expression."},
        {"operation":"ADD","predecessor":"RC3-TASK-G1-INGRESS-FORMULAS","successor":"CTL-G1-03","reason":"Corrected parsing and bar finalization are hard G1 predecessors."},
        {"operation":"ADD","predecessor":"RC3-TASK-G2-STRUCTURE-FORMULAS","successor":"CTL-G2-03","reason":"Corrected structure formulas and missing vectors are hard G2 predecessors."},
        {"operation":"ADD","predecessor":"RC3-TASK-G2-VERIFICATION-LINKS","successor":"CTL-G2-03","reason":"Legacy semantic tests must be enforceably connected."},
        {"operation":"ADD","predecessor":"RC3-TASK-G3-CLUSTER-FORMULA","successor":"CTL-G3-03","reason":"Stable opportunity identity is a hard G3 predecessor."},
        {"operation":"ADD","predecessor":"RC3-TASK-G3-FORMULA-WIRING","successor":"CTL-G3-03","reason":"Correct formula-to-produced-edge traceability is a hard G3 predecessor."},
        {"operation":"ADD","predecessor":"RC3-TASK-G4-EXPERIMENT-AXES","successor":"CTL-G4-03","reason":"The two independent experiment axes and their typed wiring are hard G4 predecessors."},
        {"operation":"ADD","predecessor":"RC3-TASK-WIRE-W08A-08","successor":"CTL-G4-03","reason":"All eight W08A atomic plumbing controls are hard G4 predecessors."},
        {"operation":"REMOVE","predecessor":"PAR-179","successor":"CTL-G6-03","reason":"Three ticks conflicts with five book levels."},
        {"operation":"ADD","predecessor":"RC3-TASK-G6-MAKER-LAW","successor":"CTL-G6-03","reason":"Five-level maker compiler and tests are mandatory."},
        {"operation":"ADD","predecessor":"RC3-TASK-G6-RISK-EXEC-FORMULAS","successor":"CTL-G6-03","reason":"Corrected risk/execution formulas are mandatory."},
        {"operation":"ADD","predecessor":"RC3-TASK-G6-FORMULA-WIRING","successor":"CTL-G6-03","reason":"Exact F20-F23 execution/outcome wiring traceability is mandatory."},
        {"operation":"ADD","predecessor":"RC3-TASK-G6-VENUE-GUARDS","successor":"CTL-G6-03","reason":"Exact mode/environment guard outcomes are mandatory."},
        {"operation":"REMOVE","predecessor":"PAR-153","successor":"CTL-G8-03","reason":"Forecast latency is outside deterministic proof population."},
        {"operation":"ADD","predecessor":"RC3-TASK-G8-DETERMINISTIC-SCOPE","successor":"CTL-G8-03","reason":"Deterministic scope isolation is mandatory."},
        {"operation":"ADD","predecessor":"RC3-TASK-G0-CONTRACT-UNION","successor":"CTL-G0-03","reason":"All 35 schemas/edges must close before G0."},
        {"operation":"ADD","predecessor":"RC3-TASK-G0-FILL-V3","successor":"CTL-G0-03","reason":"Strict money lineage is a G0 blocker."},
        {"operation":"ADD","predecessor":"RC3-TASK-G0-RECEIPT-SCHEMAS-V2","successor":"CTL-G0-03","reason":"Permissive RC2 receipts cannot authorize a G0 PASS."},
        {"operation":"ADD","predecessor":"RC3-TASK-G0-TYPED-REFERENCE-REGISTRIES","successor":"CTL-G0-03","reason":"Untyped requirement/inventory references cannot authorize a receipt."},
        {"operation":"ADD","predecessor":"RC3-TASK-G2-BINDING-V2","successor":"CTL-G2-03","reason":"All formula inputs must have typed, scoped and exclusive binding semantics before G2."},
        {"operation":"ADD","predecessor":"RC3-TASK-GATE-SEMANTIC-VALIDATOR","successor":"CTL-G0-03","reason":"Structural validation alone cannot issue a gate receipt."},
        {"operation":"ADD","predecessor":"RC3-TASK-G0-REPRODUCIBLE-SOURCE-BUNDLE","successor":"CTL-G0-03","reason":"The exact generator, inputs, overlay/applier and effective control digest are mandatory release evidence."},
    ]
    for overlay_task in overlay_tasks:
        for predecessor_id in overlay_task["depends_on_task_ids"]:
            overlay_dag.append({"operation":"ADD","predecessor":predecessor_id,"successor":overlay_task["id"],"reason":"Typed inter-task predecessor declared by the RC3 overlay."})
    source_dependency_by_pair = {
        (dependency["predecessor_task_id"], dependency["successor_task_id"]): dependency
        for dependency in dependencies
    }
    dependency_registry_sha256 = sha256(CANON / "dependency_edges.csv")
    for operation_index, dependency_operation in enumerate(overlay_dag, start=1):
        dependency_operation["edge_id"] = f"RC3-DEP-{operation_index:03d}"
        dependency_operation["predecessor_task_id"] = dependency_operation["predecessor"]
        dependency_operation["successor_task_id"] = dependency_operation["successor"]
        dependency_operation["dependency_type"] = "FINISH_START"
        dependency_operation["hard_or_soft"] = "HARD"
        dependency_operation["condition"] = "Predecessor PASSED with current nonexpired evidence for the identical applicable scope."
        dependency_operation["lag"] = "0"
        dependency_operation["external_dependency_id"] = ""
        dependency_operation["base_dependency_registry_sha256"] = dependency_registry_sha256
        if dependency_operation["operation"] == "REMOVE":
            source_dependency = source_dependency_by_pair.get((dependency_operation["predecessor"], dependency_operation["successor"]))
            if source_dependency is None:
                raise RuntimeError(f'Missing source dependency for REMOVE {dependency_operation["predecessor"]}->{dependency_operation["successor"]}')
            dependency_operation["source_edge_id"] = source_dependency["edge_id"]
        else:
            dependency_operation["source_edge_id"] = None

    overlay_verifications = [
        {"id":"RC3-V-MCP-WRITES","gate":"G-1","test":"Enumerate tools and exercise both append-only writes in isolated evidence stores","required":"No bus/runtime/money side effect; any additional write is enumerated and refused pending review."},
        {"id":"RC3-V-CONTRACT-UNION","gate":"G0","test":"Set/field/edge closure over all 35 contract names","required":"Union count 35; no schema-only, wiring-only, ownerless or untested contract remains."},
        {"id":"RC3-V-FILL-V3","gate":"G0","test":"Dual-publication and lineage conservation","required":"Every v3 fill traces to one raw venue fact and reconciles quantity/fees/position effect; incomplete inputs quarantine."},
        {"id":"RC3-V-RECEIPT-SCHEMAS-V2","gate":"G0","test":"JSON-Schema conditional positive/negative corpus for evidence_receipt.v2, task_status_event.v2 and gate_receipt.v2","required":"Every expressible empty scope/evidence/approval, open blocker, missing digest/signature/expiry/predecessor and P0-waiver mutation rejects; valid populated fixtures pass schema validation."},
        {"id":"RC3-V-TYPED-REFERENCE-REGISTRIES","gate":"G0","test":"Full reference-resolution and type-integrity query over requirement and inventory links","required":"1,348/1,348 REQUIREMENT links and 86/86 invalid/free-text INVENTORY links resolve to typed IDs or explicit blocking dispositions; zero unknown typed reference."},
        {"id":"RC3-V-G1-FORMULAS","gate":"G1","test":"Apply RC3-BOP-007/008/009/010 and RC3-POP-003/004, then run boundary, quarantine, watermark, restart and duplicate suites for F00/F01","required":"FPB-0001/0002 are concrete binding.v2 exact-divide conversions at G1; FPB-0009/PAR-024 are inactive audit history; RC3-FPB-005 binds F01 to PAR-025 and remains blocked until ratification; parsing/finalization outputs and named refusals are byte-identical."},
        {"id":"RC3-V-G2-FORMULAS","gate":"G2","test":"Golden, dimensional, prefix, restart, mirror and invalid-input suites for the G2 formula overrides","required":"Every G2 formula reaches IMPLEMENTED_AND_VERIFIED; blocked declarations remain unavailable and cannot be bypassed."},
        {"id":"RC3-V-BINDING-V2","gate":"G2","test":"Apply RC3-BOP-001…010, then run exact-count, source-snapshot/lifecycle, field-completeness, referential-integrity, unit, scope, cardinality, precedence and overlap suites","required":"Effective count is 105; the G1 ingress bindings remain concrete; FPB-0009/FPB-0020/FPB-0099 are absent from the active set but retained in lifecycle audit with typed replacements; five RC3 bindings exist; 0/105 rows are BLOCKED_NOT_STARTED migration sentinels at PASS; no missing semantic slot/consumer and no condition set can co-apply mutually exclusive values."},
        {"id":"RC3-V-G3-FORMULA","gate":"G3","test":"Prefix, restart, late-member, cross-cluster and alias suites for F19","required":"Opportunity identity never re-roots after creation and every attachment is deterministic."},
        {"id":"RC3-V-G3-FORMULA-WIRING","gate":"G3","test":"Exact-set and typed-wiring comparison for RC3-WOP-001 plus RC3-TOP-001","required":"W06 is typed ORIGIN_CANDIDATE with independent intelligence_arm; F18/F19 produced-edge set is exactly W06; W03/W04/W05 remain only typed causal-input dependencies."},
        {"id":"RC3-V-EXPERIMENT-AXES","gate":"G4","test":"Two-axis factorial fixtures across W06/W07/W08/W08A","required":"Engine cohort and intelligence arm are independently typed, joined and reported; no control/treatment alias is ambiguous."},
        {"id":"RC3-V-G6-FORMULAS","gate":"G6","test":"Activation-scope, sizing, maker, account-mode and exposure-reduction suites for F20/F21/F22","required":"Exclusive budgets, valid current inputs, fail-closed maker selection and strict residual reduction all hold."},
        {"id":"RC3-V-G6-FORMULA-WIRING","gate":"G6","test":"Exact-set comparison for RC3-TOP-002 through RC3-TOP-005 against materialized traceability rows","required":"F20→W11/W13; F21→W14/W15; F22→W13/W14/W15/W18/W19; F23→W16/W18/W20, with no undeclared mutation."},
        {"id":"RC3-V-LEGACY-LINKAGE","gate":"G2","test":"Registry referential-integrity and coverage query","required":"Zero composite gate strings, zero dangling IDs, 408/408 legacy tests linked to required task/criterion/gate edges."},
        {"id":"RC3-V-F21-FIVE-LEVEL","gate":"G6","test":"Sparse book, unequal tick gaps, zone boundary, empty feasible set, GTX race and mirror vectors","required":"Only ordinal 0..4 observed levels; no tick-count substitution; empty/race refuses with no taker fallback."},
        {"id":"RC3-V-VENUE-GUARD-CODES","gate":"G6","test":"Replay prior venue/account/environment attacks","required":"Exact five named rejection codes; legal one-way and hedge closes pass their separate compilers."},
        {"id":"RC3-V-G8-SCOPE","gate":"G8","test":"Dependency reachability from deterministic G8 receipt","required":"No E03-E06/forecast latency path reaches deterministic G8; treatment track remains separately typed."},
        {"id":"RC3-V-SEMANTIC-VALIDATOR","gate":"G0","test":"Adversarial receipts and registry mutations","required":"Every unknown ID/gate, empty PASS, open blocker, missing digest/signature, illegal transition, identity collision and P0 waiver rejects."},
        {"id":"RC3-V-REPRODUCIBLE-SOURCE-BUNDLE","gate":"G0","test":"Rebuild twice in a clean pinned environment and compare canonical JSON/input/output digests plus undeclared-read audit","required":"Generator and every input digest match the manifest; effective control JSON is byte-identical; HTML semantic payloads/digests match; undeclared input count is zero."},
    ]
    for suffix, task_name, acceptance_text in w08a_decomposition:
        overlay_verifications.append({
            "id": f"RC3-V-W08A-{suffix}", "gate": "G4",
            "test": f"W08A atomic control {suffix}: {task_name}",
            "required": acceptance_text,
        })

    overlay_acceptance = [
        {
            "criterion_id": overlay_task["acceptance_id"],
            "task_id": overlay_task["id"],
            "gate": overlay_task["gate"],
            "criterion": overlay_task["acceptance"],
            "verification_ids": overlay_task["verification"].split(";"),
            "required": "YES",
            "initial_result": "NOT_RUN",
        }
        for overlay_task in overlay_tasks
    ]

    overlay_traceability = []
    for overlay_task in overlay_tasks:
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "TASK",
            "source_id": overlay_task["id"],
            "target_type": "ACCEPTANCE_CRITERION",
            "target_id": overlay_task["acceptance_id"],
            "relationship": "REQUIRES",
            "gate": overlay_task["gate"],
            "required": "YES",
        })
        for verification_id in overlay_task["verification"].split(";"):
            overlay_traceability.append({
                "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
                "source_type": "ACCEPTANCE_CRITERION",
                "source_id": overlay_task["acceptance_id"],
                "target_type": "VERIFICATION",
                "target_id": verification_id,
                "relationship": "PROVED_BY",
                "gate": overlay_task["gate"],
                "required": "YES",
            })

    overlay_formula_task_map = {
        "RC3-TASK-G1-INGRESS-FORMULAS": ["F00", "F01"],
        "RC3-TASK-G2-STRUCTURE-FORMULAS": ["F03", "F05", "F06", "F07", "F08", "F10", "F11", "F12", "F13", "F16", "F17"],
        "RC3-TASK-G3-CLUSTER-FORMULA": ["F19"],
        "RC3-TASK-G6-RISK-EXEC-FORMULAS": ["F20", "F21", "F22"],
        "RC3-TASK-G6-MAKER-LAW": ["F21"],
    }
    overlay_task_by_id = {overlay_task["id"]: overlay_task for overlay_task in overlay_tasks}
    for task_id, formula_ids in overlay_formula_task_map.items():
        for formula_id in formula_ids:
            overlay_traceability.append({
                "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
                "source_type": "TASK",
                "source_id": task_id,
                "target_type": "FORMULA_OVERRIDE",
                "target_id": formula_id,
                "relationship": "IMPLEMENTS",
                "gate": overlay_task_by_id[task_id]["gate"],
                "required": "YES",
            })
    for wiring_operation in overlay_wiring_operations:
        wiring_task = "RC3-TASK-G3-FORMULA-WIRING" if wiring_operation["id"] == "RC3-WOP-001" else "RC3-TASK-G4-EXPERIMENT-AXES"
        wiring_gate = overlay_task_by_id[wiring_task]["gate"]
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "TASK",
            "source_id": wiring_task,
            "target_type": "WIRING_OPERATION",
            "target_id": wiring_operation["id"],
            "relationship": "IMPLEMENTS",
            "gate": wiring_gate,
            "required": "YES",
        })
    for suffix, _task_name, _acceptance_text in w08a_decomposition:
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "TASK",
            "source_id": f"RC3-TASK-WIRE-W08A-{suffix}",
            "target_type": "WIRING_OPERATION",
            "target_id": "RC3-WOP-004",
            "relationship": "DECOMPOSES_AND_IMPLEMENTS",
            "gate": "G4",
            "required": "YES",
        })
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "TASK",
            "source_id": f"RC3-TASK-WIRE-W08A-{suffix}",
            "target_type": "WIRING_EDGE",
            "target_id": "W08A",
            "relationship": "IMPLEMENTS",
            "gate": "G4",
            "required": "YES",
        })
    for formula_wiring_operation in overlay_formula_wiring_operations:
        formula_wiring_task = "RC3-TASK-G3-FORMULA-WIRING" if formula_wiring_operation["id"] == "RC3-TOP-001" else "RC3-TASK-G6-FORMULA-WIRING"
        formula_wiring_gate = overlay_task_by_id[formula_wiring_task]["gate"]
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "TASK",
            "source_id": formula_wiring_task,
            "target_type": "FORMULA_WIRING_OPERATION",
            "target_id": formula_wiring_operation["id"],
            "relationship": "IMPLEMENTS",
            "gate": formula_wiring_gate,
            "required": "YES",
        })
    overlay_parameter_task_map = {
        "RC3-PAR-EXEC-001": ["RC3-TASK-G6-MAKER-LAW"],
        "RC3-PAR-MONEY-001": ["RC3-TASK-G0-FILL-V3"],
        "RC3-PAR-CONTRACT-001": ["RC3-TASK-G0-CONTRACT-UNION"],
        "RC3-PAR-MCP-001": ["RC3-TASK-GM1-MCP-WRITES"],
        "RC3-PAR-EXP-001": ["RC3-TASK-G4-EXPERIMENT-AXES"],
        "RC3-PAR-EXP-002": ["RC3-TASK-G4-EXPERIMENT-AXES"],
        "RC3-PAR-STRUCT-001": ["RC3-TASK-G2-BINDING-V2", "RC3-TASK-G2-STRUCTURE-FORMULAS"],
        "RC3-PAR-STRUCT-002": ["RC3-TASK-G2-BINDING-V2", "RC3-TASK-G2-STRUCTURE-FORMULAS"],
        "RC3-PAR-STRUCT-003": ["RC3-TASK-G2-BINDING-V2", "RC3-TASK-G2-STRUCTURE-FORMULAS"],
    }
    overlay_parameter_by_id = {parameter["id"]: parameter for parameter in overlay_parameters}
    for parameter_id, task_ids_for_parameter in overlay_parameter_task_map.items():
        for task_id in task_ids_for_parameter:
            parameter = overlay_parameter_by_id[parameter_id]
            overlay_traceability.append({
                "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
                "source_type": "PARAMETER",
                "source_id": parameter_id,
                "target_type": "TASK",
                "target_id": task_id,
                "relationship": "BLOCKS_UNTIL_RATIFIED" if parameter["status"].startswith("BLOCKING_") else "REQUIRED_INPUT_TO",
                "gate": parameter["gate"],
                "required": "YES",
            })
    for prerequisite in overlay_prerequisites:
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "PREREQUISITE",
            "source_id": prerequisite["id"],
            "target_type": "TASK",
            "target_id": prerequisite["task_id"],
            "relationship": "BLOCKS_UNTIL_SATISFIED",
            "gate": prerequisite["gate"],
            "required": "YES",
        })
    for linkage_blocker in linkage_blockers:
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "LINKAGE_BLOCKER",
            "source_id": linkage_blocker["id"],
            "target_type": "TASK",
            "target_id": linkage_blocker["resolution_task_id"],
            "relationship": "BLOCKS_UNTIL_RESOLVED",
            "gate": linkage_blocker["gate"],
            "required": "YES",
        })
    for binding_operation in overlay_binding_operations:
        binding_operation_task = (
            "RC3-TASK-G1-INGRESS-FORMULAS"
            if binding_operation["formula_id"] in {"F00", "F01"}
            else "RC3-TASK-G2-BINDING-V2"
        )
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "BINDING_OPERATION",
            "source_id": binding_operation["id"],
            "target_type": "TASK",
            "target_id": binding_operation_task,
            "relationship": "MATERIALIZED_BY",
            "gate": overlay_task_by_id[binding_operation_task]["gate"],
            "required": "YES",
        })
    for parameter_operation in overlay_parameter_operations:
        parameter_operation_task = {
            "PAR-002": "RC3-TASK-G1-INGRESS-FORMULAS",
            "PAR-024": "RC3-TASK-G1-INGRESS-FORMULAS",
            "PAR-045": "RC3-TASK-G2-BINDING-V2",
            "PAR-179": "RC3-TASK-G6-MAKER-LAW",
        }[parameter_operation["source_parameter_id"]]
        parameter_operation_gate = overlay_task_by_id[parameter_operation_task]["gate"]
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "PARAMETER_OPERATION",
            "source_id": parameter_operation["id"],
            "target_type": "TASK",
            "target_id": parameter_operation_task,
            "relationship": "MATERIALIZED_BY",
            "gate": parameter_operation_gate,
            "required": "YES",
        })
    for vector_operation in overlay_golden_vector_operations:
        vector_task = "RC3-TASK-G6-RISK-EXEC-FORMULAS" if vector_operation["source_vector_id"] == "GV-017" else "RC3-TASK-G2-STRUCTURE-FORMULAS"
        vector_gate = overlay_task_by_id[vector_task]["gate"]
        overlay_traceability.append({
            "id": f'RC3-TRACE-{len(overlay_traceability)+1:03d}',
            "source_type": "GOLDEN_VECTOR_OPERATION",
            "source_id": vector_operation["id"],
            "target_type": "TASK",
            "target_id": vector_task,
            "relationship": "VERIFIED_BY_TASK",
            "gate": vector_gate,
            "required": "YES",
        })

    affected_registry_files = [
        "task_registry.csv", "dependency_edges.csv", "acceptance_criteria.csv", "verification_registry.csv",
        "declared_parameter_registry.csv", "formula_registry.csv", "formula_parameter_bindings.csv",
        "golden_test_vectors.csv", "wiring_registry.csv", "traceability.csv", "rc1_crosswalk.csv",
        "source_registry.csv", "gate_registry.csv",
    ]
    overlay_applies_to = {
        "match_policy": "ALL_LISTED_SHA256_MUST_MATCH_EXACTLY_OR_REFUSE",
        "base_version": "1.0.0-RC2",
        "manifest": {"path": str((RC2_DIR / "manifest.json").relative_to(ROOT)), "sha256": sha256(RC2_DIR / "manifest.json")},
        "control_bundle": {"path": str((CANON / "control_bundle.json").relative_to(ROOT)), "sha256": sha256(CANON / "control_bundle.json")},
        "affected_registries": {
            name: sha256(CANON / name) for name in affected_registry_files
        },
    }
    nonempty_string_schema = {"type": "string", "minLength": 1}
    optional_string_schema = {"type": ["string", "null"]}
    sha256_schema = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    digest_reference_schema = {
        "type": "object", "required": ["path", "sha256"],
        "properties": {"path": nonempty_string_schema, "sha256": sha256_schema},
        "additionalProperties": False,
    }
    gate_schema = {"type": "string", "enum": [gate_record["gate"] for gate_record in gates]}
    overlay_schema_definition = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:triad:origin:v7:master-overlay:v1",
        "title": "TRIAD ORIGIN V7 RC3 normative overlay",
        "type": "object",
        "required": [
            "schema", "version", "issued_at", "status", "authority", "applies_to", "overlay_schema_sha256", "applier_contract", "reproducibility_input_manifest",
            "parameters", "formula_overrides", "tasks", "dag_edge_operations", "verifications",
            "acceptance_criteria", "traceability_edges", "wiring_edge_operations",
            "formula_wiring_traceability_operations", "parameter_operations", "binding_operations",
            "golden_vector_operations", "external_prerequisites", "unresolved_linkage_blockers",
            "binding_v2_required_fields", "receipt_v2_requirements", "contract_union",
            "catalog_only_contracts", "wiring_only_contracts", "named_rejections",
        ],
        "properties": {
            "schema": {"const": "triad.origin.v7.master_overlay.v1"},
            "version": {"const": VERSION},
            "issued_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
            "status": {"const": STATUS},
            "authority": {"type": "string", "minLength": 1},
            "overlay_schema_sha256": sha256_schema,
            "applies_to": {
                "type": "object",
                "required": ["match_policy", "base_version", "manifest", "control_bundle", "affected_registries"],
                "properties": {
                    "match_policy": {"const": "ALL_LISTED_SHA256_MUST_MATCH_EXACTLY_OR_REFUSE"},
                    "base_version": {"const": "1.0.0-RC2"},
                    "manifest": digest_reference_schema,
                    "control_bundle": digest_reference_schema,
                    "affected_registries": {"type": "object", "additionalProperties": sha256_schema},
                },
                "additionalProperties": False,
            },
            "applier_contract": {
                "type": "object", "required": ["version", "canonical_json", "preconditions", "ordered_steps", "failure_behavior"],
                "properties": {
                    "version": nonempty_string_schema, "canonical_json": nonempty_string_schema,
                    "preconditions": {"type": "array", "minItems": 1, "items": nonempty_string_schema},
                    "ordered_steps": {"type": "array", "minItems": 1, "items": nonempty_string_schema},
                    "failure_behavior": nonempty_string_schema,
                }, "additionalProperties": False,
            },
            "reproducibility_input_manifest": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["path", "sha256", "bytes"], "properties": {"path": nonempty_string_schema, "sha256": sha256_schema, "bytes": {"type": "integer"}}, "additionalProperties": False}},
            "parameters": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "gate", "status", "accountable_owner", "responsible_roles", "declared_value", "unit", "exact_rule", "failure_behavior"], "properties": {"id": nonempty_string_schema, "gate": gate_schema, "status": nonempty_string_schema, "accountable_owner": nonempty_string_schema, "responsible_roles": {"type": "array", "minItems": 1, "items": nonempty_string_schema}, "declared_value": nonempty_string_schema, "unit": nonempty_string_schema, "exact_rule": nonempty_string_schema, "failure_behavior": nonempty_string_schema}, "additionalProperties": True}},
            "formula_overrides": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "status", "formula", "dependencies", "gate", "semantic_version", "inputs", "units_rounding", "availability_rule", "lifecycle_or_output", "invalid_behavior", "mirror_rule", "identity_material", "golden_boundary_tests"], "properties": {"id": {"type": "string", "pattern": "^F[0-9]{2}$"}, "status": nonempty_string_schema, "formula": nonempty_string_schema, "dependencies": nonempty_string_schema, "gate": gate_schema, "semantic_version": nonempty_string_schema, "inputs": nonempty_string_schema, "units_rounding": nonempty_string_schema, "availability_rule": nonempty_string_schema, "lifecycle_or_output": nonempty_string_schema, "invalid_behavior": nonempty_string_schema, "mirror_rule": nonempty_string_schema, "identity_material": nonempty_string_schema, "golden_boundary_tests": nonempty_string_schema}, "additionalProperties": False}},
            "tasks": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "gate", "accountable_owner", "responsible_roles", "task", "depends_on_task_ids", "external_prerequisite_ids", "acceptance_id", "acceptance", "verification", "status"], "properties": {"id": nonempty_string_schema, "gate": gate_schema, "owner": nonempty_string_schema, "accountable_owner": nonempty_string_schema, "responsible_roles": {"type": "array", "minItems": 1, "items": nonempty_string_schema}, "task": nonempty_string_schema, "depends_on": nonempty_string_schema, "depends_on_task_ids": {"type": "array", "items": nonempty_string_schema}, "external_prerequisite_ids": {"type": "array", "items": nonempty_string_schema}, "acceptance_id": nonempty_string_schema, "acceptance": nonempty_string_schema, "verification": nonempty_string_schema, "status": nonempty_string_schema}, "additionalProperties": False}},
            "dag_edge_operations": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["edge_id", "operation", "predecessor", "successor", "predecessor_task_id", "successor_task_id", "dependency_type", "hard_or_soft", "condition", "lag", "external_dependency_id", "source_edge_id", "base_dependency_registry_sha256", "reason"], "properties": {"edge_id": nonempty_string_schema, "operation": {"type": "string", "enum": ["ADD", "REMOVE"]}, "predecessor": nonempty_string_schema, "successor": nonempty_string_schema, "predecessor_task_id": nonempty_string_schema, "successor_task_id": nonempty_string_schema, "dependency_type": {"const": "FINISH_START"}, "hard_or_soft": {"const": "HARD"}, "condition": nonempty_string_schema, "lag": {"type": "string"}, "external_dependency_id": {"type": "string"}, "source_edge_id": optional_string_schema, "base_dependency_registry_sha256": sha256_schema, "reason": nonempty_string_schema}, "additionalProperties": False}},
            "verifications": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "gate", "test", "required"], "properties": {"id": nonempty_string_schema, "gate": gate_schema, "test": nonempty_string_schema, "required": nonempty_string_schema}, "additionalProperties": False}},
            "acceptance_criteria": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["criterion_id", "task_id", "gate", "criterion", "verification_ids", "required", "initial_result"], "properties": {"criterion_id": nonempty_string_schema, "task_id": nonempty_string_schema, "gate": gate_schema, "criterion": nonempty_string_schema, "verification_ids": {"type": "array", "minItems": 1, "items": nonempty_string_schema}, "required": {"const": "YES"}, "initial_result": {"const": "NOT_RUN"}}, "additionalProperties": False}},
            "traceability_edges": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "source_type", "source_id", "target_type", "target_id", "relationship", "gate", "required"], "properties": {"id": nonempty_string_schema, "source_type": nonempty_string_schema, "source_id": nonempty_string_schema, "target_type": nonempty_string_schema, "target_id": nonempty_string_schema, "relationship": nonempty_string_schema, "gate": gate_schema, "required": {"const": "YES"}}, "additionalProperties": False}},
            "wiring_edge_operations": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "operation", "wiring_id", "base_wiring_id", "inheritance", "gate", "target_name", "contract", "target_subject", "required_typing", "authority", "migration", "verification"], "properties": {"id": nonempty_string_schema, "operation": {"type": "string", "enum": ["COPY_AND_OVERRIDE", "ADD_FULL_ROW"]}, "wiring_id": nonempty_string_schema, "base_wiring_id": optional_string_schema, "inheritance": nonempty_string_schema, "phase": nonempty_string_schema, "gate": gate_schema, "target_name": nonempty_string_schema, "producer": nonempty_string_schema, "contract": nonempty_string_schema, "target_subject": nonempty_string_schema, "partition_key": nonempty_string_schema, "consumers": nonempty_string_schema, "required_typing": nonempty_string_schema, "authority": nonempty_string_schema, "ordering_idempotency": nonempty_string_schema, "readiness": nonempty_string_schema, "failure_behavior": nonempty_string_schema, "telemetry": nonempty_string_schema, "rollback": nonempty_string_schema, "verification": nonempty_string_schema, "migration": nonempty_string_schema}, "additionalProperties": False}},
            "formula_wiring_traceability_operations": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "operation", "source_controls", "formula_ids", "remove_wiring_ids", "add_wiring_ids", "status", "reason"], "properties": {"id": nonempty_string_schema, "operation": {"type": "string", "enum": ["ADD", "REPLACE"]}, "source_controls": nonempty_string_schema, "formula_ids": nonempty_string_schema, "remove_wiring_ids": {"type": "string"}, "add_wiring_ids": nonempty_string_schema, "status": nonempty_string_schema, "reason": nonempty_string_schema}, "additionalProperties": False}},
            "parameter_operations": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "operation", "source_parameter_id", "replacement_parameter_id", "effective_scope", "source_status_after_apply", "reason"], "properties": {"id": nonempty_string_schema, "operation": {"type": "string", "enum": ["SUPERSEDE", "COPY_AND_OVERRIDE"]}, "source_parameter_id": nonempty_string_schema, "replacement_parameter_id": nonempty_string_schema, "effective_scope": nonempty_string_schema, "source_status_after_apply": nonempty_string_schema, "declared_value": nonempty_string_schema, "exact_rule": nonempty_string_schema, "boundary_rule": nonempty_string_schema, "failure_behavior": nonempty_string_schema, "reason": nonempty_string_schema}, "additionalProperties": False}},
            "binding_operations": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "operation", "binding_id", "source_binding_id", "formula_id", "parameter_id", "semantic_slot", "cardinality", "condition", "activation_scope", "precedence", "consumer", "consuming_wiring_ids", "unit_contract", "lifecycle_status", "disposition_reason", "superseded_by", "failure_behavior"], "properties": {"id": nonempty_string_schema, "operation": {"type": "string", "enum": ["REMOVE", "ADD", "COPY_AND_OVERRIDE"]}, "binding_id": nonempty_string_schema, "source_binding_id": optional_string_schema, "formula_id": {"type": "string", "pattern": "^F[0-9]{2}$"}, "parameter_id": nonempty_string_schema, "semantic_slot": nonempty_string_schema, "cardinality": {"type": "string", "enum": ["EXACTLY_ONE", "ZERO_OR_ONE", "ONE_OR_MORE"]}, "condition": nonempty_string_schema, "activation_scope": nonempty_string_schema, "precedence": nonempty_string_schema, "consumer": nonempty_string_schema, "consuming_wiring_ids": nonempty_string_schema, "unit_contract": nonempty_string_schema, "lifecycle_status": {"type": "string", "enum": ["ACTIVE", "SUPERSEDED", "RETIRED", "BLOCKED"]}, "disposition_reason": nonempty_string_schema, "superseded_by": optional_string_schema, "declared_value": nonempty_string_schema, "boundary_rule": nonempty_string_schema, "failure_behavior": nonempty_string_schema}, "additionalProperties": False}},
            "golden_vector_operations": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "operation", "source_vector_id", "linked_formula", "inputs", "expected", "status"], "properties": {"id": nonempty_string_schema, "operation": {"const": "REPLACE"}, "source_vector_id": nonempty_string_schema, "linked_formula": {"type": "string", "pattern": "^F[0-9]{2}$"}, "inputs": nonempty_string_schema, "expected": nonempty_string_schema, "status": nonempty_string_schema}, "additionalProperties": False}},
            "external_prerequisites": {"type": "array", "items": {"type": "object", "required": ["id", "task_id", "gate", "accountable_owner", "type", "requirement", "scope_rule", "closure_rule", "status", "evidence_id", "evidence_sha256"], "properties": {"id": nonempty_string_schema, "task_id": nonempty_string_schema, "gate": gate_schema, "accountable_owner": nonempty_string_schema, "type": nonempty_string_schema, "requirement": nonempty_string_schema, "scope_rule": nonempty_string_schema, "closure_rule": nonempty_string_schema, "status": nonempty_string_schema, "evidence_id": optional_string_schema, "evidence_sha256": optional_string_schema}, "additionalProperties": False}},
            "unresolved_linkage_blockers": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["id", "population", "defect", "required_migration", "status", "gate", "resolution_task_id", "resolution_acceptance_id", "resolution_verification_id", "closure_rule", "terminal_status_on_valid_closure"], "properties": {"id": nonempty_string_schema, "population": nonempty_string_schema, "defect": nonempty_string_schema, "required_migration": nonempty_string_schema, "status": nonempty_string_schema, "gate": gate_schema, "resolution_task_id": nonempty_string_schema, "resolution_acceptance_id": nonempty_string_schema, "resolution_verification_id": nonempty_string_schema, "closure_rule": nonempty_string_schema, "terminal_status_on_valid_closure": nonempty_string_schema}, "additionalProperties": False}},
            "binding_v2_required_fields": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["field", "rule"], "properties": {"field": nonempty_string_schema, "rule": nonempty_string_schema}, "additionalProperties": False}},
            "receipt_v2_requirements": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["schema", "required_conditionals", "hard_rejections"], "properties": {"schema": nonempty_string_schema, "required_conditionals": nonempty_string_schema, "hard_rejections": nonempty_string_schema}, "additionalProperties": False}},
            "contract_union": {"type": "array", "minItems": 1, "uniqueItems": True, "items": nonempty_string_schema},
            "catalog_only_contracts": {"type": "array", "uniqueItems": True, "items": nonempty_string_schema},
            "wiring_only_contracts": {"type": "array", "uniqueItems": True, "items": nonempty_string_schema},
            "named_rejections": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["code", "trigger", "behavior"], "properties": {"code": nonempty_string_schema, "trigger": nonempty_string_schema, "behavior": nonempty_string_schema}, "additionalProperties": False}},
        },
        "additionalProperties": False,
    }
    overlay_schema_sha256 = hashlib.sha256(canonical_json(overlay_schema_definition).encode("utf-8")).hexdigest()
    overlay_applier_contract = {
        "version": "triad.origin.v7.overlay_applier.v1",
        "canonical_json": "UTF-8; object keys sorted lexicographically; no insignificant whitespace; ensure_ascii=false",
        "preconditions": [
            "Validate the overlay against the schema whose canonical SHA-256 is overlay_schema_sha256.",
            "Require exact match of manifest, control-bundle and every affected-registry SHA-256 in applies_to.",
            "Reject unknown IDs, duplicate IDs, noncanonical gates/owners, ambiguous operations or unresolved operation targets.",
        ],
        "ordered_steps": [
            "Copy the base control bundle without mutation.",
            "Apply parameter and binding supersessions by exact source ID; retain lifecycle audit fields.",
            "Apply formula and golden-vector replacements by exact ID.",
            "Propagate each complete formula override into all 119 preserved FORMULA_ATOMIC tasks, criteria and verifications; retain source snapshots as audit-only fields.",
            "Apply wiring COPY_AND_OVERRIDE operations and ADD_FULL_ROW operations.",
            "Propagate W06/W07/W08 effective rows into all 24 preserved WIRING_ATOMIC tasks and materialize the eight W08A atomic controls.",
            "Apply formula-to-wiring traceability removals/additions by exact task and W-ID sets.",
            "Apply dependency REMOVEs by source_edge_id/base digest, then full canonical ADD edge rows.",
            "Recompute task.depends_on from the effective HARD dependency registry and task.wiring_refs from required effective WIRING_EDGE traceability.",
            "Append RC3 tasks, acceptance criteria, verifications, prerequisites and typed traceability.",
            "Run schema, referential-integrity, canonical-owner/gate, DAG cycle/reachability, exact-count and blocker checks.",
            "Emit the effective bundle and manifest; any open prerequisite/blocker preserves SAFE_HOLD and forbids a gate PASS.",
        ],
        "failure_behavior": "REFUSE_WITHOUT_PARTIAL_OUTPUT; base bundle remains unchanged; emit named validation errors.",
    }

    rc3_overlay = {
        "schema": "triad.origin.v7.master_overlay.v1",
        "version": VERSION,
        "issued_at": DATE,
        "status": STATUS,
        "authority": "NORMATIVE_OVER_RC1_RC2_CONFLICTS; DOES_NOT_ARM",
        "applies_to": overlay_applies_to,
        "overlay_schema_sha256": overlay_schema_sha256,
        "applier_contract": overlay_applier_contract,
        "reproducibility_input_manifest": reproducibility_manifest,
        "parameters": overlay_parameters,
        "formula_overrides": overlay_formulas,
        "tasks": overlay_tasks,
        "dag_edge_operations": overlay_dag,
        "verifications": overlay_verifications,
        "acceptance_criteria": overlay_acceptance,
        "traceability_edges": overlay_traceability,
        "wiring_edge_operations": overlay_wiring_operations,
        "formula_wiring_traceability_operations": overlay_formula_wiring_operations,
        "parameter_operations": overlay_parameter_operations,
        "binding_operations": overlay_binding_operations,
        "golden_vector_operations": overlay_golden_vector_operations,
        "external_prerequisites": overlay_prerequisites,
        "unresolved_linkage_blockers": linkage_blockers,
        "binding_v2_required_fields": binding_v2_required_fields,
        "receipt_v2_requirements": receipt_v2_requirements,
        "contract_union": contract_union,
        "catalog_only_contracts": catalog_only,
        "wiring_only_contracts": wiring_only,
        "named_rejections": [{"code":r[0],"trigger":r[1],"behavior":r[2]} for r in named_rejection_rows],
    }
    overlay_schema_errors = validate_schema_profile(rc3_overlay, overlay_schema_definition)
    if overlay_schema_errors:
        raise RuntimeError("RC3 overlay schema validation failed: " + "; ".join(overlay_schema_errors[:25]))

    # Materialize an overlay-aware effective control bundle inside the standalone HTML.
    base_control_bundle = json.loads((CANON / "control_bundle.json").read_text(encoding="utf-8"))
    effective_control_bundle = copy.deepcopy(base_control_bundle)
    base_rc2_metadata = copy.deepcopy(effective_control_bundle.get("metadata", {}))
    gate_phase = {gate_record["gate"]: gate_record["phase"] for gate_record in gates}
    overlay_canonical = canonical_json(rc3_overlay)
    overlay_sha256 = hashlib.sha256(overlay_canonical.encode("utf-8")).hexdigest()
    composition_sha256 = hashlib.sha256(
        (overlay_applies_to["control_bundle"]["sha256"] + overlay_sha256 + overlay_applier_contract["version"]).encode("utf-8")
    ).hexdigest()
    effective_control_bundle["schema"] = "triad.implementation_control_bundle.effective.v1"
    effective_control_bundle["metadata"] = {
        **base_rc2_metadata,
        "version": VERSION,
        "date": DATE,
        "issued_at": DATE,
        "status": STATUS,
        "base_rc2_metadata": base_rc2_metadata,
        "base_control_bundle_sha256": overlay_applies_to["control_bundle"]["sha256"],
        "rc3_overlay_sha256": overlay_sha256,
        "overlay_schema_sha256": overlay_schema_sha256,
        "applier_version": overlay_applier_contract["version"],
        "composition_sha256": composition_sha256,
        "activation_authority": "DENIED; OPEN BLOCKERS AND NOT_STARTED CONTROLS",
    }

    task_columns = list(effective_control_bundle["tasks"][0].keys())
    for overlay_task in overlay_tasks:
        task_formula_refs = [
            trace_edge["target_id"] for trace_edge in overlay_traceability
            if trace_edge["source_type"] == "TASK" and trace_edge["source_id"] == overlay_task["id"] and trace_edge["target_type"] == "FORMULA_OVERRIDE"
        ]
        task_operation_refs = [
            trace_edge["target_id"] for trace_edge in overlay_traceability
            if trace_edge["source_type"] == "TASK" and trace_edge["source_id"] == overlay_task["id"] and trace_edge["target_type"] in {"WIRING_OPERATION", "FORMULA_WIRING_OPERATION"}
        ]
        effective_task = {column: "" for column in task_columns}
        is_w08a_atomic = overlay_task["id"].startswith("RC3-TASK-WIRE-W08A-")
        effective_task.update({
            "id": overlay_task["id"],
            "row_class": "WIRING_ATOMIC_RC3" if is_w08a_atomic else "ATOMIC_RC3_OVERLAY_CONTROL",
            "parent_id": "W08A" if is_w08a_atomic else "RC3-NORMATIVE-OVERLAY",
            "phase": gate_phase[overlay_task["gate"]],
            "gate": overlay_task["gate"],
            "domain": "RC3_REMEDIATION",
            "node": "Edge comparator" if is_w08a_atomic else overlay_task["accountable_owner"],
            "workstream": "Intelligence-arm divergence plumbing" if is_w08a_atomic else "RC3 effective-control materialization",
            "priority": "P0",
            "critical_path": "YES",
            "truth_state": "NORMATIVE_TARGET_NOT_IMPLEMENTED",
            "task": overlay_task["task"],
            "implementation_instruction": overlay_task["task"],
            "accountable_owner": overlay_task["accountable_owner"],
            "responsible_roles": ";".join(overlay_task["responsible_roles"]),
            "approvers": "Governance;Validation",
            "depends_on": ";".join(overlay_task["depends_on_task_ids"]),
            "inventory_refs": ";".join(overlay_task["external_prerequisite_ids"]),
            "requirement_refs": overlay_task["acceptance_id"],
            "wiring_refs": "W08A" if is_w08a_atomic else "",
            "formula_refs": ";".join(task_formula_refs),
            "verification_refs": overlay_task["verification"],
            "acceptance_evidence": overlay_task["acceptance_id"],
            "rollback_or_stop": "SAFE_HOLD; reject partial overlay output; preserve immutable RC2 base bytes.",
            "initial_status": overlay_task["status"],
            "notes": "Generated from triad.origin.v7.master_overlay.v1; prerequisite IDs are mandatory typed blockers.",
        })
        effective_task["external_prerequisite_ids"] = overlay_task["external_prerequisite_ids"]
        effective_task["operation_refs"] = task_operation_refs
        effective_control_bundle["tasks"].append(effective_task)

    removed_dependency_ids = {
        dependency_operation["source_edge_id"] for dependency_operation in overlay_dag
        if dependency_operation["operation"] == "REMOVE"
    }
    effective_control_bundle["dependencies"] = [
        dependency for dependency in effective_control_bundle["dependencies"]
        if dependency["edge_id"] not in removed_dependency_ids
    ]
    for dependency_operation in overlay_dag:
        if dependency_operation["operation"] != "ADD":
            continue
        effective_control_bundle["dependencies"].append({
            "edge_id": dependency_operation["edge_id"],
            "predecessor_task_id": dependency_operation["predecessor_task_id"],
            "successor_task_id": dependency_operation["successor_task_id"],
            "dependency_type": dependency_operation["dependency_type"],
            "hard_or_soft": dependency_operation["hard_or_soft"],
            "condition": dependency_operation["condition"],
            "lag": dependency_operation["lag"],
            "external_dependency_id": dependency_operation["external_dependency_id"],
        })

    for acceptance_record in overlay_acceptance:
        effective_control_bundle["criteria"].append({
            "criterion_id": acceptance_record["criterion_id"],
            "task_id": acceptance_record["task_id"],
            "criterion": acceptance_record["criterion"],
            "verification_method": "Execute every typed verification ID and independently review immutable evidence.",
            "expected_result": acceptance_record["criterion"],
            "verification_id": ";".join(acceptance_record["verification_ids"]),
            "evidence_type": "SIGNED_MACHINE_READABLE_RECEIPT_V2",
            "criticality": "P0",
            "required": acceptance_record["required"],
            "initial_result": acceptance_record["initial_result"],
            "evidence_id": "",
        })

    for verification_record in overlay_verifications:
        linked_overlay_tasks = [
            overlay_task["id"] for overlay_task in overlay_tasks
            if verification_record["id"] in overlay_task["verification"].split(";")
        ]
        effective_control_bundle["verifications"].append({
            "verification_id": verification_record["id"],
            "source": "RC3_NORMATIVE_OVERLAY",
            "gate": verification_record["gate"],
            "criticality": "P0",
            "linked_task_ids": ";".join(linked_overlay_tasks),
            "suite": "RC3 semantic and falsification suite",
            "test": verification_record["test"],
            "stimulus": "Exact fixtures, mutations and failure injections declared by the linked acceptance criterion.",
            "required_result": verification_record["required"],
            "evidence": "Signed immutable receipt with fixture/result/log/build/config/input digests and independent reviewer.",
            "initial_status": "NOT_RUN",
        })

    parameter_operation_by_source = {operation["source_parameter_id"]: operation for operation in overlay_parameter_operations}
    for parameter_record in effective_control_bundle["parameters"]:
        if parameter_record["id"] in parameter_operation_by_source:
            operation = parameter_operation_by_source[parameter_record["id"]]
            parameter_record["rc2_source_record"] = copy.deepcopy(parameter_record)
            parameter_record["status"] = operation["source_status_after_apply"]
            parameter_record["disposition_reason"] = operation["reason"]
            if operation["operation"] == "SUPERSEDE":
                parameter_record["superseded_by"] = operation["replacement_parameter_id"]
            elif operation["operation"] == "COPY_AND_OVERRIDE":
                for field in ["declared_value", "exact_rule", "boundary_rule", "failure_behavior"]:
                    parameter_record[field] = operation[field]
                parameter_record["source_basis"] = "RC3 normative overlay; RC2 source preserved in rc2_source_record"
            else:
                raise RuntimeError(f"Unknown parameter operation {operation['operation']}")
    for overlay_parameter in overlay_parameters:
        formula_refs_for_parameter = sorted({
            operation["formula_id"] for operation in overlay_binding_operations
            if operation["parameter_id"] == overlay_parameter["id"] and operation["operation"] == "ADD"
        })
        effective_control_bundle["parameters"].append({
            "id": overlay_parameter["id"],
            "category": "RC3 overlay",
            "name": overlay_parameter["name"],
            "symbol": overlay_parameter["name"],
            "declared_value": overlay_parameter["declared_value"],
            "unit": overlay_parameter["unit"],
            "value_type": "RC3 exact declaration",
            "status": overlay_parameter["status"],
            "accountable_owner": overlay_parameter["accountable_owner"],
            "phase": gate_phase[overlay_parameter["gate"]],
            "gate": overlay_parameter["gate"],
            "scope": "Exact scope of every typed consuming task/binding.",
            "exact_rule": overlay_parameter["exact_rule"],
            "boundary_rule": "Use the exact declared value/type; no implicit conversion or default.",
            "failure_behavior": overlay_parameter["failure_behavior"],
            "source_basis": "RC3 normative overlay",
            "formula_refs": ";".join(formula_refs_for_parameter),
            "review_trigger": "Any semantic or value change",
            "responsible_roles": overlay_parameter["responsible_roles"],
        })

    formula_override_by_id = {formula_override["id"]: formula_override for formula_override in overlay_formulas}
    for formula_record in effective_control_bundle["formulas"]:
        formula_override = formula_override_by_id.get(formula_record["id"])
        if formula_override is None:
            continue
        formula_record["rc2_source_record"] = copy.deepcopy(formula_record)
        formula_record["rc2_source_formula"] = formula_record["formula"]
        formula_record["semantic_version"] = formula_override["semantic_version"]
        formula_record["inputs"] = formula_override["inputs"]
        formula_record["formula"] = formula_override["formula"]
        formula_record["units_rounding"] = formula_override["units_rounding"]
        formula_record["availability"] = formula_override["availability_rule"]
        formula_record["parameters"] = formula_override["dependencies"]
        formula_record["lifecycle_or_output"] = formula_override["lifecycle_or_output"]
        formula_record["invalid_behavior"] = formula_override["invalid_behavior"]
        formula_record["mirror_rule"] = formula_override["mirror_rule"]
        formula_record["identity_material"] = formula_override["identity_material"]
        formula_record["golden_boundary_tests"] = formula_override["golden_boundary_tests"]
        formula_record["rc3_status"] = formula_override["status"]
        formula_record["source_basis"] = "RC3 normative overlay; RC2 source preserved in rc2_source_formula"

    wiring_by_id = {wiring_record["id"]: wiring_record for wiring_record in effective_control_bundle["wiring"]}
    for wiring_operation in overlay_wiring_operations:
        if wiring_operation["operation"] == "COPY_AND_OVERRIDE":
            wiring_record = wiring_by_id[wiring_operation["base_wiring_id"]]
            wiring_record["rc2_source_row"] = copy.deepcopy(wiring_record)
            wiring_record["name"] = wiring_operation["target_name"]
            wiring_record["logical_binding"] = wiring_operation["target_subject"]
            wiring_record["authority"] = wiring_operation["authority"]
            wiring_record["verification"] = wiring_operation["verification"]
            wiring_record["required_typing"] = wiring_operation["required_typing"]
            wiring_record["migration"] = wiring_operation["migration"]
        elif wiring_operation["operation"] == "ADD_FULL_ROW":
            effective_control_bundle["wiring"].append({
                "id": wiring_operation["wiring_id"], "phase": wiring_operation["phase"], "gate": wiring_operation["gate"],
                "name": wiring_operation["target_name"], "producer": wiring_operation["producer"], "contract": wiring_operation["contract"],
                "logical_binding": wiring_operation["target_subject"], "partition_key": wiring_operation["partition_key"],
                "consumers": wiring_operation["consumers"], "authority": wiring_operation["authority"],
                "ordering_idempotency": wiring_operation["ordering_idempotency"], "readiness": wiring_operation["readiness"],
                "failure_behavior": wiring_operation["failure_behavior"], "telemetry": wiring_operation["telemetry"],
                "rollback": wiring_operation["rollback"], "verification": wiring_operation["verification"],
                "required_typing": wiring_operation["required_typing"], "migration": wiring_operation["migration"],
            })
        else:
            raise RuntimeError(f'Unknown wiring operation {wiring_operation["operation"]}')

    def merge_semicolon_refs(existing: str, additions: list[str]) -> str:
        merged = [value for value in existing.split(";") if value]
        for value in additions:
            if value and value not in merged:
                merged.append(value)
        return ";".join(merged)

    criterion_by_task_id = {record["task_id"]: record for record in effective_control_bundle["criteria"]}
    effective_verification_by_id = {
        record["verification_id"]: record for record in effective_control_bundle["verifications"]
    }
    overlay_verification_effective_by_id = {
        record["verification_id"]: record for record in effective_control_bundle["verifications"]
        if record.get("source") == "RC3_NORMATIVE_OVERLAY"
    }
    patched_task_verifications: dict[str, list[str]] = {}

    def patch_preserved_task(
        task_record: dict[str, object], controlling_label: str, controlling_instruction: str,
        verification_ids: list[str], criterion_requirement: str,
    ) -> None:
        task_id = str(task_record["id"])
        task_record["rc2_source_task"] = task_record.get("task", "")
        task_record["rc2_source_implementation_instruction"] = task_record.get("implementation_instruction", "")
        task_record["rc2_source_acceptance_evidence"] = task_record.get("acceptance_evidence", "")
        task_record["task"] = f"{task_record.get('task', task_id)} — {controlling_label}"
        task_record["implementation_instruction"] = controlling_instruction
        original_verification_ids = [value for value in str(task_record.get("verification_refs", "")).split(";") if value]
        task_record["verification_refs"] = merge_semicolon_refs(str(task_record.get("verification_refs", "")), verification_ids)
        task_record["acceptance_evidence"] = criterion_requirement
        task_record["notes"] = (
            "RC3 controlling semantics are materialized in the live fields. rc2_source_* fields are immutable audit history "
            "and MUST NOT be executed where incompatible."
        )
        patched_task_verifications[task_id] = verification_ids

        criterion_record = criterion_by_task_id[task_id]
        criterion_record["rc2_source_criterion"] = criterion_record.get("criterion", "")
        criterion_record["rc2_source_expected_result"] = criterion_record.get("expected_result", "")
        criterion_record["rc2_source_verification_id"] = criterion_record.get("verification_id", "")
        criterion_record["criterion"] = criterion_requirement
        criterion_record["expected_result"] = criterion_requirement
        criterion_record["verification_id"] = merge_semicolon_refs(str(criterion_record.get("verification_id", "")), verification_ids)
        criterion_record["verification_method"] = "Execute every linked source and RC3 verification against the effective record; independently review immutable receipt.v2 evidence."
        criterion_record["evidence_type"] = "SIGNED_MACHINE_READABLE_RECEIPT_V2"

        for source_verification_id in original_verification_ids:
            verification_record = effective_verification_by_id.get(source_verification_id)
            if verification_record is None:
                raise RuntimeError(f"Missing source verification {source_verification_id} for {task_id}")
            if "rc2_source_record" not in verification_record:
                verification_record["rc2_source_record"] = copy.deepcopy(verification_record)
            verification_record["test"] = f"Run the preserved suite against {controlling_label}; RC2 embedded semantic fragments are audit-only. {verification_record.get('test', '')}"
            verification_record["required_result"] = f"The effective RC3 record and {', '.join(verification_ids)} control every conflict. {verification_record.get('required_result', '')}"

        for verification_id in verification_ids:
            overlay_verification_record = overlay_verification_effective_by_id[verification_id]
            overlay_verification_record["linked_task_ids"] = merge_semicolon_refs(
                str(overlay_verification_record.get("linked_task_ids", "")), [task_id]
            )

    formula_rc3_verifications = {
        "F00": ["RC3-V-G1-FORMULAS"], "F01": ["RC3-V-G1-FORMULAS"],
        "F03": ["RC3-V-G2-FORMULAS"], "F05": ["RC3-V-G2-FORMULAS"],
        "F06": ["RC3-V-G2-FORMULAS"], "F07": ["RC3-V-G2-FORMULAS"],
        "F08": ["RC3-V-G2-FORMULAS"], "F10": ["RC3-V-G2-FORMULAS"],
        "F11": ["RC3-V-G2-FORMULAS"], "F12": ["RC3-V-G2-FORMULAS"],
        "F13": ["RC3-V-G2-FORMULAS"], "F16": ["RC3-V-G2-FORMULAS"],
        "F17": ["RC3-V-G2-FORMULAS"], "F19": ["RC3-V-G3-FORMULA"],
        "F20": ["RC3-V-G6-FORMULAS"], "F21": ["RC3-V-G6-FORMULAS", "RC3-V-F21-FIVE-LEVEL"],
        "F22": ["RC3-V-G6-FORMULAS"],
    }
    patched_formula_task_count = 0
    for task_record in effective_control_bundle["tasks"]:
        if task_record.get("row_class") != "FORMULA_ATOMIC":
            continue
        formula_ids = [value for value in str(task_record.get("formula_refs", "")).split(";") if value in formula_override_by_id]
        if not formula_ids:
            continue
        if len(formula_ids) != 1:
            raise RuntimeError(f"Ambiguous overridden formula task {task_record['id']}: {formula_ids}")
        formula_id = formula_ids[0]
        formula_override = formula_override_by_id[formula_id]
        source_stage = str(task_record.get("implementation_instruction", "")).split(" Formula:", 1)[0].strip()
        controlling_instruction = (
            f"{source_stage} RC3 CONTROLLING COMPLETE RECORD {formula_id} ({formula_override['semantic_version']}): "
            f"{formula_override['formula']} Units/rounding: {formula_override['units_rounding']} "
            f"Readiness/status: {formula_override['status']}; dependencies: {formula_override['dependencies']}. "
            f"Availability: {formula_override['availability_rule']} Invalid behavior: {formula_override['invalid_behavior']} "
            "The preserved RC2 instruction applies only where compatible with this complete record."
        )
        criterion_requirement = (
            f"Implement and prove the complete {formula_id} RC3 record {formula_override['semantic_version']} exactly; "
            f"status/readiness is {formula_override['status']}; every linked RC3 verification must PASS. "
            "The preserved RC2 criterion remains additive only where it does not conflict."
        )
        patch_preserved_task(
            task_record, f"RC3-controlled {formula_id}", controlling_instruction,
            formula_rc3_verifications[formula_id], criterion_requirement,
        )
        patched_formula_task_count += 1
    if patched_formula_task_count != 119:
        raise RuntimeError(f"Expected 119 preserved formula tasks to patch, got {patched_formula_task_count}")

    wiring_operation_by_base_id = {
        operation["base_wiring_id"]: operation for operation in overlay_wiring_operations
        if operation["operation"] == "COPY_AND_OVERRIDE"
    }
    effective_wiring_by_id = {record["id"]: record for record in effective_control_bundle["wiring"]}
    patched_wiring_task_count = 0
    for task_record in effective_control_bundle["tasks"]:
        parent_id = str(task_record.get("parent_id", ""))
        if task_record.get("row_class") != "WIRING_ATOMIC" or parent_id not in wiring_operation_by_base_id:
            continue
        operation = wiring_operation_by_base_id[parent_id]
        wiring_record = effective_wiring_by_id[parent_id]
        full_row_fields = [
            "producer", "contract", "logical_binding", "partition_key", "consumers", "authority",
            "ordering_idempotency", "readiness", "failure_behavior", "telemetry", "rollback",
            "required_typing", "migration",
        ]
        complete_row = "; ".join(f"{field}={wiring_record.get(field, '')}" for field in full_row_fields)
        controlling_instruction = (
            f"Complete atomic stage '{task_record.get('task', '')}' against RC3 controlling wiring operation {operation['id']} "
            f"and the full effective {parent_id} row: {complete_row}. The preserved RC2 subject, control/treatment alias, "
            "authority, failure and readiness fragments are audit-only and MUST NOT control implementation."
        )
        criterion_requirement = (
            f"This atomic stage materializes the complete effective {parent_id} row under {operation['id']}; "
            f"{operation['verification']} and the preserved stage verification must PASS with receipt.v2 evidence."
        )
        task_record["workstream"] = str(wiring_record.get("name", parent_id))
        patch_preserved_task(
            task_record, f"RC3-controlled {parent_id}", controlling_instruction,
            [operation["verification"]], criterion_requirement,
        )
        patched_wiring_task_count += 1
    if patched_wiring_task_count != 24:
        raise RuntimeError(f"Expected 24 preserved W06/W07/W08 tasks to patch, got {patched_wiring_task_count}")

    golden_operation_by_source = {operation["source_vector_id"]: operation for operation in overlay_golden_vector_operations}
    for vector_record in effective_control_bundle["golden_vectors"]:
        vector_operation = golden_operation_by_source.get(vector_record["id"])
        if vector_operation is None:
            continue
        vector_record["rc2_source_vector"] = copy.deepcopy(vector_record)
        vector_record["inputs"] = vector_operation["inputs"]
        vector_record["operation"] = "Apply the corrected RC3 formula exactly."
        vector_record["expected"] = vector_operation["expected"]
        vector_record["boundary"] = vector_operation["status"]
        vector_record["linked"] = vector_operation["linked_formula"]

    source_binding_by_id = {
        binding_record["binding_id"]: binding_record
        for binding_record in effective_control_bundle["formula_parameter_bindings"]
    }
    for binding_operation in overlay_binding_operations:
        source_binding_id = binding_operation["source_binding_id"]
        if source_binding_id is None:
            continue
        source_binding = source_binding_by_id.get(source_binding_id)
        if source_binding is None:
            raise RuntimeError(f"Unknown binding operation source {source_binding_id}")
        if (source_binding["formula_id"], source_binding["parameter_id"]) != (
            binding_operation["formula_id"], binding_operation["parameter_id"]
        ):
            raise RuntimeError(f"Binding source identity mismatch for {binding_operation['id']}")

    removed_binding_ids = {
        operation["source_binding_id"] for operation in overlay_binding_operations
        if operation["operation"] == "REMOVE"
    }
    binding_supersession_audit = [
        {
            "operation_id": operation["id"], "effective_status": operation["lifecycle_status"],
            "source_row": copy.deepcopy(source_binding_by_id[operation["source_binding_id"]]),
            "operation": copy.deepcopy(operation),
        }
        for operation in overlay_binding_operations if operation["operation"] == "REMOVE"
    ]
    effective_control_bundle["formula_parameter_bindings"] = [
        binding_record for binding_record in effective_control_bundle["formula_parameter_bindings"]
        if binding_record["binding_id"] not in removed_binding_ids
    ]
    retained_binding_by_id = {
        binding_record["binding_id"]: binding_record
        for binding_record in effective_control_bundle["formula_parameter_bindings"]
    }
    copy_override_binding_ids = {
        operation["source_binding_id"] for operation in overlay_binding_operations
        if operation["operation"] == "COPY_AND_OVERRIDE"
    }
    formula_owner_by_id = {record["id"]: record["owner"] for record in effective_control_bundle["formulas"]}
    binding_v2_unmigrated_ids: list[str] = []
    for binding_record in effective_control_bundle["formula_parameter_bindings"]:
        if binding_record["binding_id"] in copy_override_binding_ids:
            continue
        binding_record["rc2_source_binding"] = copy.deepcopy(binding_record)
        binding_record.update({
            "source_binding_id": binding_record["binding_id"],
            "semantic_slot": f"UNRESOLVED_BLOCKING:{binding_record['binding_id']}",
            "cardinality": "UNRESOLVED_BLOCKING",
            "condition": "NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES",
            "activation_scope": "NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW",
            "precedence": "BLOCKED_PENDING_BINDING_V2_MIGRATION",
            "consumer": f"UNRESOLVED_BLOCKING; source_formula_owner={formula_owner_by_id[binding_record['formula_id']]}",
            "consuming_wiring_ids": "UNRESOLVED_BLOCKING",
            "unit_contract": f"source_unit={binding_record.get('unit', '')}; exact conversion/slot contract UNRESOLVED",
            "lifecycle_status": "BLOCKED",
            "disposition_reason": "Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred.",
            "superseded_by": None,
            "migration_state": "BLOCKED_NOT_STARTED",
            "status": "BLOCKED_BINDING_V2_MIGRATION",
            "failure_behavior": f"SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: {binding_record.get('failure_behavior', '')}",
        })
        binding_v2_unmigrated_ids.append(binding_record["binding_id"])
    for binding_operation in overlay_binding_operations:
        if binding_operation["operation"] != "COPY_AND_OVERRIDE":
            continue
        binding_record = retained_binding_by_id[binding_operation["source_binding_id"]]
        binding_record["rc2_source_binding"] = copy.deepcopy(binding_record)
        binding_record.update({
            "formula_id": binding_operation["formula_id"], "parameter_id": binding_operation["parameter_id"],
            "declared_value": binding_operation["declared_value"], "status": binding_operation["lifecycle_status"],
            "gate": formula_override_by_id[binding_operation["formula_id"]]["gate"],
            "boundary_rule": binding_operation["boundary_rule"], "failure_behavior": binding_operation["failure_behavior"],
            **{
                key: binding_operation[key] for key in [
                    "source_binding_id", "semantic_slot", "cardinality", "condition", "activation_scope",
                    "precedence", "consumer", "consuming_wiring_ids", "unit_contract", "lifecycle_status",
                    "disposition_reason", "superseded_by",
                ]
            },
            "operation_id": binding_operation["id"],
        })
    source_parameter_lookup = {parameter_record["id"]: parameter_record for parameter_record in effective_control_bundle["parameters"]}
    for binding_operation in overlay_binding_operations:
        if binding_operation["operation"] != "ADD":
            continue
        if any(
            binding_record["binding_id"] == binding_operation["binding_id"]
            for binding_record in effective_control_bundle["formula_parameter_bindings"]
        ):
            raise RuntimeError(f"Duplicate additive binding {binding_operation['binding_id']}")
        parameter_record = source_parameter_lookup[binding_operation["parameter_id"]]
        effective_control_bundle["formula_parameter_bindings"].append({
            "binding_id": binding_operation["binding_id"], "formula_id": binding_operation["formula_id"],
            "parameter_id": binding_operation["parameter_id"], "parameter_name": parameter_record["name"],
            "declared_value": parameter_record["declared_value"], "unit": parameter_record["unit"],
            "status": binding_operation["lifecycle_status"], "gate": formula_override_by_id[binding_operation["formula_id"]]["gate"],
            "boundary_rule": binding_operation["precedence"], "failure_behavior": binding_operation["failure_behavior"],
            **{key: value for key, value in binding_operation.items() if key not in {"id", "operation"}},
        })
    effective_control_bundle["binding_supersession_audit"] = binding_supersession_audit

    formula_ids_by_parameter: dict[str, list[str]] = defaultdict(list)
    for binding_record in effective_control_bundle["formula_parameter_bindings"]:
        parameter_formula_ids = formula_ids_by_parameter[binding_record["parameter_id"]]
        if binding_record["formula_id"] not in parameter_formula_ids:
            parameter_formula_ids.append(binding_record["formula_id"])
    for parameter_record in effective_control_bundle["parameters"]:
        parameter_record["formula_refs"] = ";".join(formula_ids_by_parameter.get(parameter_record["id"], []))

    effective_traceability = copy.deepcopy(traceability)
    next_effective_trace = 1
    for traceability_operation in overlay_formula_wiring_operations:
        source_controls = traceability_operation["source_controls"].split("|")
        remove_wiring_ids = {value for value in traceability_operation["remove_wiring_ids"].split("|") if value}
        effective_traceability = [
            trace_record for trace_record in effective_traceability
            if not (
                trace_record["task_id"] in source_controls and trace_record["reference_type"] == "WIRING_EDGE"
                and trace_record["reference_id"] in remove_wiring_ids
            )
        ]
        for source_control in source_controls:
            for wiring_id in [value for value in traceability_operation["add_wiring_ids"].split("|") if value]:
                if any(
                    trace_record["task_id"] == source_control and trace_record["reference_type"] == "WIRING_EDGE"
                    and trace_record["reference_id"] == wiring_id for trace_record in effective_traceability
                ):
                    continue
                effective_traceability.append({
                    "trace_id": f"RC3-EFF-TRACE-{next_effective_trace:04d}", "task_id": source_control,
                    "reference_type": "WIRING_EDGE", "reference_id": wiring_id,
                    "relationship": "IMPLEMENTS", "required": "YES",
                })
                next_effective_trace += 1
    acceptance_task_by_id = {record["criterion_id"]: record["task_id"] for record in overlay_acceptance}
    for overlay_trace in overlay_traceability:
        if overlay_trace["source_type"] == "TASK":
            task_id = overlay_trace["source_id"]
            reference_type = overlay_trace["target_type"]
            reference_id = overlay_trace["target_id"]
        elif overlay_trace["target_type"] == "TASK":
            task_id = overlay_trace["target_id"]
            reference_type = overlay_trace["source_type"]
            reference_id = overlay_trace["source_id"]
        elif overlay_trace["source_type"] == "ACCEPTANCE_CRITERION":
            task_id = acceptance_task_by_id[overlay_trace["source_id"]]
            reference_type = overlay_trace["target_type"]
            reference_id = overlay_trace["target_id"]
        else:
            continue
        effective_traceability.append({
            "trace_id": f"RC3-EFF-TRACE-{next_effective_trace:04d}", "task_id": task_id,
            "reference_type": reference_type, "reference_id": reference_id,
            "relationship": overlay_trace["relationship"], "required": overlay_trace["required"],
        })
        next_effective_trace += 1
    for task_id, verification_ids in sorted(patched_task_verifications.items()):
        for verification_id in verification_ids:
            effective_traceability.append({
                "trace_id": f"RC3-EFF-TRACE-{next_effective_trace:04d}", "task_id": task_id,
                "reference_type": "VERIFICATION", "reference_id": verification_id,
                "relationship": "VERIFIED_BY", "required": "YES",
            })
            next_effective_trace += 1

    wiring_ids_by_task: dict[str, list[str]] = defaultdict(list)
    for trace_record in effective_traceability:
        if trace_record["reference_type"] != "WIRING_EDGE" or trace_record["required"] != "YES":
            continue
        task_wiring_ids = wiring_ids_by_task[trace_record["task_id"]]
        if trace_record["reference_id"] not in task_wiring_ids:
            task_wiring_ids.append(trace_record["reference_id"])
    for task_record in effective_control_bundle["tasks"]:
        task_record["wiring_refs"] = ";".join(wiring_ids_by_task.get(task_record["id"], []))

    incoming_hard_predecessors: dict[str, list[str]] = defaultdict(list)
    for dependency_record in effective_control_bundle["dependencies"]:
        if dependency_record["hard_or_soft"] != "HARD":
            continue
        predecessors = incoming_hard_predecessors[dependency_record["successor_task_id"]]
        if dependency_record["predecessor_task_id"] not in predecessors:
            predecessors.append(dependency_record["predecessor_task_id"])
    for task_record in effective_control_bundle["tasks"]:
        predecessors = incoming_hard_predecessors.get(task_record["id"], [])
        task_record["depends_on"] = "ROOT" if task_record["id"] == "CTL-GM1-01" and not predecessors else ";".join(predecessors)

    effective_control_bundle["traceability"] = effective_traceability
    effective_control_bundle["rc3_extensions"] = {
        "external_prerequisites": overlay_prerequisites,
        "unresolved_linkage_blockers": linkage_blockers,
        "contract_union": contract_union,
        "named_rejections": [{"code": row[0], "trigger": row[1], "behavior": row[2]} for row in named_rejection_rows],
        "receipt_v2_requirements": receipt_v2_requirements,
        "binding_v2_required_fields": binding_v2_required_fields,
        "binding_supersession_audit": binding_supersession_audit,
    }

    effective_task_ids = [task_record["id"] for task_record in effective_control_bundle["tasks"]]
    canonical_owner_set = {task_record["accountable_owner"] for task_record in tasks}
    canonical_gate_set = {gate_record["gate"] for gate_record in gates}
    validation_errors = []
    if len(effective_task_ids) != len(set(effective_task_ids)):
        validation_errors.append("DUPLICATE_EFFECTIVE_TASK_ID")
    if effective_control_bundle["metadata"].get("date") != DATE or effective_control_bundle["metadata"].get("issued_at") != DATE or effective_control_bundle["metadata"].get("base_rc2_metadata") != base_rc2_metadata:
        validation_errors.append("EFFECTIVE_METADATA_PROVENANCE_MISMATCH")
    if any(task_record["accountable_owner"] not in canonical_owner_set for task_record in overlay_tasks):
        validation_errors.append("NONCANONICAL_OVERLAY_OWNER")
    if any(task_record["gate"] not in canonical_gate_set for task_record in overlay_tasks):
        validation_errors.append("NONCANONICAL_OVERLAY_GATE")
    effective_task_id_set = set(effective_task_ids)
    effective_adjacency = defaultdict(set)
    effective_indegree = Counter()
    for dependency_record in effective_control_bundle["dependencies"]:
        predecessor = dependency_record["predecessor_task_id"]
        successor = dependency_record["successor_task_id"]
        if dependency_record["edge_id"].startswith("RC3-") and (predecessor not in effective_task_id_set or successor not in effective_task_id_set):
            validation_errors.append(f"UNKNOWN_RC3_DEPENDENCY_ENDPOINT:{dependency_record['edge_id']}")
        if predecessor in effective_task_id_set and successor in effective_task_id_set and successor not in effective_adjacency[predecessor]:
            effective_adjacency[predecessor].add(successor)
            effective_indegree[successor] += 1
    effective_nodes = set(effective_task_id_set)
    ready = deque(node for node in effective_nodes if effective_indegree[node] == 0)
    visited_count = 0
    while ready:
        node = ready.popleft()
        visited_count += 1
        for successor in effective_adjacency.get(node, set()):
            effective_indegree[successor] -= 1
            if effective_indegree[successor] == 0:
                ready.append(successor)
    if visited_count != len(effective_nodes):
        validation_errors.append("EFFECTIVE_DAG_CYCLE")
    verification_gate_by_id = {verification_record["id"]: verification_record["gate"] for verification_record in overlay_verifications}
    for overlay_task in overlay_tasks:
        for verification_id in overlay_task["verification"].split(";"):
            if verification_id not in verification_gate_by_id:
                validation_errors.append(f"UNKNOWN_OVERLAY_VERIFICATION:{overlay_task['id']}:{verification_id}")
            elif verification_gate_by_id[verification_id] != overlay_task["gate"]:
                validation_errors.append(f"OVERLAY_VERIFICATION_GATE_MISMATCH:{overlay_task['id']}:{verification_id}")
        if sum(acceptance_record["task_id"] == overlay_task["id"] for acceptance_record in overlay_acceptance) != 1:
            validation_errors.append(f"OVERLAY_ACCEPTANCE_CARDINALITY:{overlay_task['id']}")
        gate_evaluator_id = "CTL-GM1-03" if overlay_task["gate"] == "G-1" else f"CTL-{overlay_task['gate']}-03"
        frontier = deque([overlay_task["id"]])
        reachable = {overlay_task["id"]}
        while frontier and gate_evaluator_id not in reachable:
            for successor in effective_adjacency.get(frontier.popleft(), set()):
                if successor not in reachable:
                    reachable.add(successor)
                    frontier.append(successor)
        if gate_evaluator_id not in reachable:
            validation_errors.append(f"OVERLAY_TASK_NOT_GATE_BLOCKING:{overlay_task['id']}:{gate_evaluator_id}")
    predecessor_receipt_by_gate = {
        "G0": "CTL-GM1-06", "G1": "CTL-G0-06", "G2": "CTL-G1-06", "G3": "CTL-G2-06",
        "G4": "CTL-G3-06", "G5": "CTL-G4-06", "G6": "CTL-G5-06", "G7": "CTL-G6-06",
        "G8": "CTL-G7-06", "G9": "CTL-G8-06",
    }
    for overlay_task in overlay_tasks:
        predecessor_receipt = predecessor_receipt_by_gate.get(overlay_task["gate"])
        if predecessor_receipt is None:
            continue
        frontier = deque([predecessor_receipt])
        reachable = {predecessor_receipt}
        while frontier and overlay_task["id"] not in reachable:
            for successor in effective_adjacency.get(frontier.popleft(), set()):
                if successor not in reachable:
                    reachable.add(successor)
                    frontier.append(successor)
        if overlay_task["id"] not in reachable:
            validation_errors.append(f"MISSING_PREDECESSOR_RECEIPT_PATH:{predecessor_receipt}:{overlay_task['id']}")
    traced_parameter_ids = {trace_edge["source_id"] for trace_edge in overlay_traceability if trace_edge["source_type"] == "PARAMETER"}
    if traced_parameter_ids != {parameter["id"] for parameter in overlay_parameters}:
        validation_errors.append("OVERLAY_PARAMETER_TRACEABILITY_INCOMPLETE")
    traced_blocker_ids = {trace_edge["source_id"] for trace_edge in overlay_traceability if trace_edge["source_type"] == "LINKAGE_BLOCKER"}
    if traced_blocker_ids != {blocker["id"] for blocker in linkage_blockers}:
        validation_errors.append("LINKAGE_BLOCKER_TRACEABILITY_INCOMPLETE")
    traced_prerequisite_ids = {trace_edge["source_id"] for trace_edge in overlay_traceability if trace_edge["source_type"] == "PREREQUISITE"}
    if traced_prerequisite_ids != {prerequisite["id"] for prerequisite in overlay_prerequisites}:
        validation_errors.append("PREREQUISITE_TRACEABILITY_INCOMPLETE")
    traced_operation_ids = {trace_edge["source_id"] for trace_edge in overlay_traceability if trace_edge["source_type"].endswith("_OPERATION")}
    expected_operation_ids = {
        *[operation["id"] for operation in overlay_binding_operations],
        *[operation["id"] for operation in overlay_parameter_operations],
        *[operation["id"] for operation in overlay_golden_vector_operations],
    }
    if not expected_operation_ids.issubset(traced_operation_ids):
        validation_errors.append("PARAMETER_BINDING_VECTOR_OPERATION_TRACEABILITY_INCOMPLETE")
    traced_target_operation_ids = {
        trace_edge["target_id"] for trace_edge in overlay_traceability
        if trace_edge["target_type"] in {"WIRING_OPERATION", "FORMULA_WIRING_OPERATION"}
    }
    expected_target_operation_ids = {
        *[operation["id"] for operation in overlay_wiring_operations],
        *[operation["id"] for operation in overlay_formula_wiring_operations],
    }
    if traced_target_operation_ids != expected_target_operation_ids:
        validation_errors.append("WIRING_OPERATION_TRACEABILITY_INCOMPLETE")
    if any(parameter["accountable_owner"] not in canonical_owner_set for parameter in overlay_parameters):
        validation_errors.append("NONCANONICAL_OVERLAY_PARAMETER_OWNER")
    dependency_predecessors_by_task: dict[str, list[str]] = defaultdict(list)
    for dependency_record in effective_control_bundle["dependencies"]:
        if dependency_record["hard_or_soft"] == "HARD" and dependency_record["predecessor_task_id"] not in dependency_predecessors_by_task[dependency_record["successor_task_id"]]:
            dependency_predecessors_by_task[dependency_record["successor_task_id"]].append(dependency_record["predecessor_task_id"])
    for task_record in effective_control_bundle["tasks"]:
        expected_depends_on = "ROOT" if task_record["id"] == "CTL-GM1-01" and not dependency_predecessors_by_task.get(task_record["id"]) else ";".join(dependency_predecessors_by_task.get(task_record["id"], []))
        if task_record.get("depends_on", "") != expected_depends_on:
            validation_errors.append(f"TASK_DEPENDENCY_DENORMALIZATION_MISMATCH:{task_record['id']}")
            break
    formula_atomic_override_tasks = [
        task_record for task_record in effective_control_bundle["tasks"]
        if task_record.get("row_class") == "FORMULA_ATOMIC"
        and any(ref in formula_override_by_id for ref in str(task_record.get("formula_refs", "")).split(";"))
    ]
    if len(formula_atomic_override_tasks) != 119 or any("RC3 CONTROLLING COMPLETE RECORD" not in task_record.get("implementation_instruction", "") for task_record in formula_atomic_override_tasks):
        validation_errors.append("PRESERVED_FORMULA_TASK_OVERRIDE_INCOMPLETE")
    preserved_wiring_override_tasks = [
        task_record for task_record in effective_control_bundle["tasks"]
        if task_record.get("row_class") == "WIRING_ATOMIC" and task_record.get("parent_id") in {"W06", "W07", "W08"}
    ]
    if len(preserved_wiring_override_tasks) != 24 or any("full effective" not in task_record.get("implementation_instruction", "") for task_record in preserved_wiring_override_tasks):
        validation_errors.append("PRESERVED_WIRING_TASK_OVERRIDE_INCOMPLETE")
    if sum(task_record["id"].startswith("RC3-TASK-WIRE-W08A-") for task_record in effective_control_bundle["tasks"]) != 8:
        validation_errors.append("W08A_ATOMIC_DECOMPOSITION_INCOMPLETE")
    effective_formula_by_id = {record["id"]: record for record in effective_control_bundle["formulas"]}
    for formula_override in overlay_formulas:
        effective_formula = effective_formula_by_id[formula_override["id"]]
        for field in ["semantic_version", "inputs", "formula", "units_rounding", "invalid_behavior", "mirror_rule", "identity_material", "golden_boundary_tests"]:
            if effective_formula[field] != formula_override[field]:
                validation_errors.append(f"FORMULA_OVERRIDE_FIELD_MISMATCH:{formula_override['id']}:{field}")
    active_binding_by_id = {record["binding_id"]: record for record in effective_control_bundle["formula_parameter_bindings"]}
    if any(binding_id in active_binding_by_id for binding_id in {"FPB-0009", "FPB-0020", "FPB-0099"}):
        validation_errors.append("SUPERSEDED_BINDING_STILL_ACTIVE")
    if "exact_div" not in active_binding_by_id.get("FPB-0002", {}).get("boundary_rule", "") or "floor" in active_binding_by_id.get("FPB-0002", {}).get("boundary_rule", "").lower().replace("no floor", ""):
        validation_errors.append("FPB_0002_INGRESS_SEMANTICS_NOT_CORRECTED")
    if "RC3-FPB-005" not in active_binding_by_id or active_binding_by_id["RC3-FPB-005"].get("parameter_id") != "PAR-025":
        validation_errors.append("F01_WATERMARK_BINDING_MISSING")
    if any(
        binding_record.get("gate") != effective_formula_by_id[binding_record["formula_id"]]["gate"]
        for binding_record in effective_control_bundle["formula_parameter_bindings"]
        if binding_record.get("formula_id") in effective_formula_by_id
        and (binding_record["binding_id"] == "FPB-0002" or binding_record["binding_id"].startswith("RC3-FPB-"))
    ):
        validation_errors.append("RC3_FORMULA_BINDING_GATE_MISMATCH")
    if len(binding_supersession_audit) != 3 or {row["source_row"]["binding_id"] for row in binding_supersession_audit} != {"FPB-0009", "FPB-0020", "FPB-0099"}:
        validation_errors.append("BINDING_LIFECYCLE_AUDIT_INCOMPLETE")
    binding_v2_fields = {
        "binding_id", "formula_id", "parameter_id", "semantic_slot", "cardinality", "condition",
        "activation_scope", "precedence", "consumer", "consuming_wiring_ids", "unit_contract",
        "failure_behavior", "lifecycle_status", "disposition_reason", "source_binding_id", "superseded_by",
    }
    if any(
        not binding_v2_fields.issubset(binding_record)
        or any(binding_record[field] == "" for field in binding_v2_fields if field not in {"source_binding_id", "superseded_by"})
        for binding_record in effective_control_bundle["formula_parameter_bindings"]
    ):
        validation_errors.append("BINDING_V2_FIELD_COVERAGE_INCOMPLETE")
    if len(binding_v2_unmigrated_ids) != 98 or any(active_binding_by_id[binding_id].get("migration_state") != "BLOCKED_NOT_STARTED" for binding_id in binding_v2_unmigrated_ids):
        validation_errors.append("BINDING_V2_UNMIGRATED_SENTINEL_COUNT_MISMATCH")
    gate_rank = {"G-1": -1, **{f"G{index}": index for index in range(10)}}
    if any(gate_rank[effective_formula_by_id[active_binding_by_id[binding_id]["formula_id"]]["gate"]] < gate_rank["G2"] for binding_id in binding_v2_unmigrated_ids):
        validation_errors.append("PRE_G2_FORMULA_BLOCKED_BY_G2_BINDING_MIGRATION")
    effective_parameter_by_id = {record["id"]: record for record in effective_control_bundle["parameters"]}
    if "floor" in effective_parameter_by_id["PAR-002"]["boundary_rule"].lower() or "QUARANTINE" not in effective_parameter_by_id["PAR-002"]["failure_behavior"]:
        validation_errors.append("PAR002_INGRESS_PARAMETER_NOT_CORRECTED")
    if effective_parameter_by_id["PAR-025"].get("formula_refs") != "F01" or effective_parameter_by_id["PAR-024"].get("formula_refs"):
        validation_errors.append("PARAMETER_FORMULA_REFERENCE_DENORMALIZATION_MISMATCH")
    gv005 = next(record for record in effective_control_bundle["golden_vectors"] if record["id"] == "GV-005")
    if "differences 4 and 5" not in gv005["inputs"] or "4 fails" not in gv005["expected"] or "5 passes" not in gv005["expected"]:
        validation_errors.append("GV005_BOUNDARY_FALSIFIER_INCOMPLETE")
    if len(effective_control_bundle["formula_parameter_bindings"]) != 105:
        validation_errors.append("EFFECTIVE_BINDING_COUNT_NOT_105")
    if len(effective_control_bundle["wiring"]) != 27:
        validation_errors.append("EFFECTIVE_WIRING_COUNT_NOT_27")
    open_blocker_count = len(linkage_blockers) + sum(1 for parameter in overlay_parameters if parameter["status"].startswith("BLOCKING_"))
    open_prerequisite_count = sum(1 for prerequisite in overlay_prerequisites if prerequisite["status"] != "SATISFIED")
    effective_validation_report = {
        "schema": "triad.origin.v7.effective_validation_report.v1",
        "status": "PASS_COMPOSITION_SAFE_HOLD" if not validation_errors else "FAIL",
        "generated_at": DATE,
        "base_control_bundle_sha256": overlay_applies_to["control_bundle"]["sha256"],
        "overlay_sha256": overlay_sha256,
        "composition_sha256": composition_sha256,
        "checks": {
            "base_digest_preconditions": "PASS",
            "effective_metadata_provenance": "PASS" if "EFFECTIVE_METADATA_PROVENANCE_MISMATCH" not in validation_errors else "FAIL",
            "overlay_required_structure": "PASS" if not overlay_schema_errors else "FAIL",
            "overlay_schema_profile": "EXECUTED_CLOSED_PROFILE",
            "canonical_owner_and_gate": "PASS" if "NONCANONICAL_OVERLAY_OWNER" not in validation_errors and "NONCANONICAL_OVERLAY_GATE" not in validation_errors else "FAIL",
            "effective_id_uniqueness": "PASS" if "DUPLICATE_EFFECTIVE_TASK_ID" not in validation_errors else "FAIL",
            "effective_dag_acyclic": "PASS" if "EFFECTIVE_DAG_CYCLE" not in validation_errors else "FAIL",
            "overlay_task_gate_reachability": "PASS" if not any(error.startswith("OVERLAY_TASK_NOT_GATE_BLOCKING") for error in validation_errors) else "FAIL",
            "signed_predecessor_receipt_paths": "PASS" if not any(error.startswith("MISSING_PREDECESSOR_RECEIPT_PATH") for error in validation_errors) else "FAIL",
            "overlay_task_acceptance_verification_closure": "PASS" if not any(error.startswith(("UNKNOWN_OVERLAY_VERIFICATION", "OVERLAY_VERIFICATION_GATE_MISMATCH", "OVERLAY_ACCEPTANCE_CARDINALITY")) for error in validation_errors) else "FAIL",
            "parameter_prerequisite_blocker_traceability": "PASS" if not any(error.endswith("TRACEABILITY_INCOMPLETE") for error in validation_errors) else "FAIL",
            "effective_binding_count": len(effective_control_bundle["formula_parameter_bindings"]),
            "binding_v2_field_coverage": "105/105",
            "binding_v2_unmigrated_source_rows": len(binding_v2_unmigrated_ids),
            "binding_v2_migration_status": "BLOCKED_NOT_STARTED" if binding_v2_unmigrated_ids else "COMPLETE",
            "effective_wiring_count": len(effective_control_bundle["wiring"]),
            "open_blockers": open_blocker_count,
            "open_external_prerequisites": open_prerequisite_count,
            "all_overlay_tasks_initial_status": "NOT_STARTED",
        },
        "errors": validation_errors,
        "activation_result": "DENIED_SAFE_HOLD",
    }
    if validation_errors:
        raise RuntimeError("Effective-control validation failed: " + "; ".join(validation_errors))
    effective_control_bundle["validation_report"] = effective_validation_report
    base_rc2_summary = copy.deepcopy(effective_control_bundle.get("summary", {}))
    effective_control_bundle["summary"] = {
        "status": effective_validation_report["status"],
        "activation_result": effective_validation_report["activation_result"],
        "base_rc2_source_summary": base_rc2_summary,
        "effective_task_count": len(effective_control_bundle["tasks"]),
        "effective_dependency_count": len(effective_control_bundle["dependencies"]),
        "effective_acceptance_count": len(effective_control_bundle["criteria"]),
        "effective_verification_count": len(effective_control_bundle["verifications"]),
        "effective_parameter_record_count": len(effective_control_bundle["parameters"]),
        "effective_formula_count": len(effective_control_bundle["formulas"]),
        "effective_binding_count": len(effective_control_bundle["formula_parameter_bindings"]),
        "binding_v2_unmigrated_source_row_count": len(binding_v2_unmigrated_ids),
        "effective_golden_vector_count": len(effective_control_bundle["golden_vectors"]),
        "effective_wiring_count": len(effective_control_bundle["wiring"]),
        "effective_traceability_count": len(effective_control_bundle["traceability"]),
    }
    effective_bundle_canonical = canonical_json(effective_control_bundle)
    effective_bundle_sha256 = hashlib.sha256(effective_bundle_canonical.encode("utf-8")).hexdigest()
    effective_bundle_manifest = {
        "schema": "triad.origin.v7.effective_bundle_manifest.v1",
        "version": VERSION,
        "base_control_bundle_sha256": overlay_applies_to["control_bundle"]["sha256"],
        "overlay_sha256": overlay_sha256,
        "overlay_schema_sha256": overlay_schema_sha256,
        "applier_version": overlay_applier_contract["version"],
        "composition_sha256": composition_sha256,
        "effective_bundle_sha256": effective_bundle_sha256,
        "effective_counts": effective_control_bundle["summary"],
        "validation_status": effective_validation_report["status"],
        "activation_result": effective_validation_report["activation_result"],
    }
    overlay_base_digest_rows = [
        ["RC2 manifest", overlay_applies_to["manifest"]["path"], code_text(overlay_applies_to["manifest"]["sha256"])],
        ["RC2 control bundle", overlay_applies_to["control_bundle"]["path"], code_text(overlay_applies_to["control_bundle"]["sha256"])],
        *[["Affected registry", registry_name, code_text(registry_digest)] for registry_name, registry_digest in overlay_applies_to["affected_registries"].items()],
    ]
    effective_manifest_rows = [[key, text(value)] for key, value in effective_bundle_manifest.items() if key != "effective_counts"]
    effective_count_rows = [[key, text(value)] for key, value in effective_control_bundle["summary"].items() if key.startswith("effective_")]
    validation_check_rows = [[key, text(value)] for key, value in effective_validation_report["checks"].items()]
    applier_steps_html = "<ol>" + "".join(f"<li>{esc(step)}</li>" for step in overlay_applier_contract["ordered_steps"]) + "</ol>"

    css = r"""
:root{--bg:#050c12;--panel:#0b1822;--panel2:#0f2230;--ink:#e9f4fa;--muted:#97aebb;--line:#244655;--cyan:#49dbf5;--green:#64dfa1;--amber:#ffc857;--red:#ff6b78;--violet:#bf9cff;--shadow:0 14px 40px rgba(0,0,0,.28);--radius:14px}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:72px}body{margin:0;background:linear-gradient(180deg,#03080c,#07131c 32rem,#061019);color:var(--ink);font:14.5px/1.58 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}a{color:var(--cyan);text-decoration:none}a:hover{text-decoration:underline}code,.mono{font-family:"SFMono-Regular",Consolas,monospace;color:#c2f3ff;overflow-wrap:anywhere}code{background:#06131b;border:1px solid #1e4150;padding:.08rem .3rem;border-radius:5px}pre{white-space:pre-wrap;overflow-wrap:anywhere}.topline{height:4px;background:linear-gradient(90deg,var(--cyan),var(--green),var(--amber),var(--violet))}.mast{position:sticky;top:0;z-index:30;background:rgba(3,10,15,.95);border-bottom:1px solid #173543;backdrop-filter:blur(12px)}.mast-inner{max-width:1800px;margin:auto;padding:10px 18px;display:flex;gap:14px;align-items:center}.brand{min-width:255px}.brand b{letter-spacing:.08em}.brand small{display:block;color:var(--muted)}.quicknav{display:flex;gap:7px;overflow:auto}.quicknav a{white-space:nowrap;border:1px solid #244452;border-radius:999px;padding:6px 9px;font-size:11px;color:#c3d8e2}.hero{padding:68px 0 40px;border-bottom:1px solid #193947;background:radial-gradient(circle at 82% 5%,rgba(73,219,245,.17),transparent 34%),radial-gradient(circle at 9% 20%,rgba(100,223,161,.09),transparent 30%)}.container,.wrap{width:min(1720px,calc(100% - 38px));margin:auto}.eyebrow{color:var(--cyan);font-weight:850;text-transform:uppercase;letter-spacing:.15em;font-size:12px}.hero h1{font-size:clamp(2.2rem,5.6vw,5.7rem);line-height:.92;letter-spacing:-.055em;margin:.22em 0}.hero h1 em{font-style:normal;color:var(--cyan)}.lead{max-width:1080px;color:#c2d7e2;font-size:clamp(1rem,1.6vw,1.25rem)}.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}.chip{display:inline-flex;align-items:center;border:1px solid #315665;background:#081720;color:#c4dbe5;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:800;overflow-wrap:anywhere}.chip.good{color:var(--green);border-color:#2d7255}.chip.warn{color:var(--amber);border-color:#775f2c}.chip.bad{color:var(--red);border-color:#773842}.layout{max-width:1800px;margin:auto;display:grid;grid-template-columns:265px minmax(0,1fr);gap:22px;padding:26px 18px 80px}.side{position:sticky;top:72px;align-self:start;max-height:calc(100vh - 90px);overflow:auto;background:#07141d;border:1px solid var(--line);border-radius:14px;padding:13px}.side strong{display:block;color:var(--cyan);margin:4px 5px 8px}.side a{display:block;padding:6px 7px;border-radius:7px;color:#b9d0db;font-size:12px}.side a:hover{background:#10232f;text-decoration:none}.content{min-width:0}.chapter{content-visibility:auto;contain-intrinsic-size:1000px;margin:0 0 40px;scroll-margin-top:82px}.chapter>h2,.section>h2{font-size:clamp(1.45rem,2.4vw,2.4rem);line-height:1.15;border-bottom:1px solid #245063;padding-bottom:10px;margin:0 0 17px}.chapter>h2>span,.section>h2 .num{font:700 .62em "SFMono-Regular",Consolas,monospace;color:var(--cyan);margin-right:10px}.chapter h3,.section h3{margin:26px 0 10px;color:#e2f9ff}.chapter h4,.section h4{color:#cce3ed}.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:13px}.card{grid-column:span 4;background:linear-gradient(180deg,#0d1d28,#091720);border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow)}.card.wide{grid-column:span 6}.card.full{grid-column:1/-1}.metric b,.kpi{display:block;color:var(--cyan);font-size:2rem;line-height:1;font-weight:900}.metric span{color:var(--muted)}.callout{display:grid;grid-template-columns:minmax(145px,220px) minmax(0,1fr);gap:15px;border:1px solid #275063;border-left:5px solid var(--cyan);background:#0a1a24;border-radius:10px;padding:14px 16px;margin:16px 0}.callout.good{border-left-color:var(--green)}.callout.warn{border-left-color:var(--amber)}.callout.danger,.callout.bad{border-left-color:var(--red)}.callout.purple{border-left-color:var(--violet)}.callout strong{color:#fff}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px;background:#07141d;margin:12px 0 22px;max-width:100%}.registry-wrap{max-height:76vh}table{border-collapse:collapse;width:100%;min-width:900px}th{position:sticky;top:0;z-index:4;background:#112a38;color:#d7f7ff;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;text-align:left}th,td{border-bottom:1px solid #1a3947;padding:9px 10px;vertical-align:top}tbody tr:hover{background:#0d202b}td{max-width:760px}details{margin-top:6px;border:1px solid #1f4353;border-radius:8px;background:#081720;padding:7px}summary{cursor:pointer;color:#c7edfa;font-weight:750}.record-details{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px;margin:10px 0 0}.record-details>div{background:#0c202b;border-radius:7px;padding:8px;min-width:0}.record-details dt{text-transform:uppercase;letter-spacing:.05em;color:var(--cyan);font-size:10px;font-weight:800}.record-details dd{margin:3px 0 0;overflow-wrap:anywhere}.formula-code,.formula{margin:0;background:#06131b;border:1px solid #254c5d;border-radius:8px;padding:10px;color:#d5f7ff;font:12px/1.5 "SFMono-Regular",Consolas,monospace;min-width:320px}.toolbar{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.toolbar input,.toolbar select,.toolbar button{background:#071720;color:var(--ink);border:1px solid #2d5363;border-radius:8px;padding:8px 10px;font:inherit}.toolbar input{min-width:260px;flex:1}.toolbar button{cursor:pointer;color:var(--cyan)}.toolbar .count{padding:8px;color:var(--muted)}.laws{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.law{display:grid;grid-template-columns:34px 1fr;gap:10px;align-items:start;background:#091923;border:1px solid #214553;border-radius:9px;padding:10px}.law b{display:grid;place-items:center;background:#123246;color:var(--cyan);border-radius:7px;height:28px}.topology{display:block;width:min(1100px,100%);height:auto;margin:auto;border:1px solid #2a5b6e;border-radius:14px;background:#02070b;box-shadow:var(--shadow)}.diagram{background:#061018;border:1px solid #214858;border-radius:14px;padding:14px 16px;margin:18px 0;overflow:auto}.flow{display:flex;gap:9px;flex-wrap:wrap}.flow .node{flex:1 1 160px;border:1px solid #25566b;background:#0a1c27;border-radius:10px;padding:11px}.flow .node b{display:block;color:var(--cyan)}.status{display:inline-flex;border:1px solid #315366;border-radius:999px;padding:3px 8px;font-size:11px}.pill{display:inline-block;border:1px solid #315366;border-radius:999px;padding:2px 7px;font-size:11px}.small,.muted{color:var(--muted);font-size:.9em}.nowrap{white-space:nowrap}.arrow{color:var(--cyan);font-size:18px}.legacy-baseline{border:1px solid #284a58;border-radius:16px;padding:20px;background:rgba(6,16,23,.5)}.legacy-baseline>.wrap{width:100%}.legacy-link{border-bottom:1px dotted #47616d}.source-code{max-height:520px;overflow:auto;background:#06121a;border:1px solid var(--line);border-radius:10px;padding:14px;color:#d6edf6}.schema-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}.schema-grid article{min-width:0}.footer{border-top:1px solid #193846;background:#030a0f;padding:30px 20px 50px;color:var(--muted)}.backtop{position:fixed;right:18px;bottom:18px;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:#0b2633;border:1px solid var(--cyan);color:var(--cyan);z-index:20}.hide{display:none!important}.print-only{display:none}
@media(max-width:1050px){.layout{grid-template-columns:1fr}.side{position:static;max-height:none;columns:2}.grid .card,.card.wide{grid-column:1/-1}.laws{grid-template-columns:1fr}.mast-inner{display:block}.brand{margin-bottom:7px}}
@media(max-width:650px){.container,.wrap{width:min(100% - 20px,1720px)}.layout{padding:14px 10px 60px}.side{columns:1}.hero{padding:42px 0 28px}.callout{grid-template-columns:1fr}.toolbar input{min-width:100%}.legacy-baseline{padding:10px}.record-details{grid-template-columns:1fr}}
@media print{body{background:#fff;color:#111;font-size:8.5pt}.mast,.side,.toolbar,.backtop,.no-print{display:none!important}.layout{display:block;max-width:none;padding:0}.container,.wrap{width:100%}.hero{padding:8mm 0 5mm;background:none}.hero h1{font-size:27pt}.chapter{content-visibility:visible;contain:none}.chapter>h2,.section>h2{color:#111;border-color:#777}.card,.callout,.table-wrap,.legacy-baseline,details,.law,.diagram,.formula-code,.formula{box-shadow:none;background:#fff;color:#111;border-color:#999}table{min-width:0;font-size:6.5pt}th{position:static;background:#ddd;color:#111}.muted,.small{color:#444}.topology{box-shadow:none;max-height:245mm;object-fit:contain}details>*{display:block}.print-only{display:block}.registry-wrap{max-height:none;overflow:visible}.source-code{max-height:none}.chip,.status,.pill,code{color:#111;background:#fff;border-color:#777}}
"""

    overlay_gate_counts = Counter(overlay_task["gate"] for overlay_task in overlay_tasks)
    effective_gate_rows = []
    for gate_record in gates:
        gate_id = gate_record["gate"]
        source_count = gate_counts.get(gate_id, 0)
        overlay_count = overlay_gate_counts.get(gate_id, 0)
        effective_gate_rows.append([
            status_chip(gate_id), esc(gate_record["phase"]), esc(gate_record["name"]),
            esc(str(source_count)), esc(str(overlay_count)), esc(str(source_count + overlay_count)),
            text(gate_record["entry"]), text(gate_record["exit"]), text(gate_record["automatic_fail"]),
            code_text(gate_record["receipt"]), text(gate_record["derived_pass_rule"]),
        ])

    metrics = [
        ("1", "authoritative standalone HTML"),
        (f"{len(tasks):,} + {len(overlay_tasks)}", "RC2 source controls + RC3 controls"),
        (f"{len(dependencies):,} + {len(overlay_dag)} ops", "RC2 source DAG + RC3 patch"),
        (f"{len(acceptance):,} + {len(overlay_acceptance)}", "RC2 source + RC3 acceptance"),
        (f"{len(verifications):,} + {len(overlay_verifications)}", "RC2 source + RC3 verifications"),
        (f"{len(parameters):,} + {len(overlay_parameters)}", "RC2 source + RC3 parameters"),
        (f"{len(formulas)} + {len(overlay_formulas)}", "RC2 source formulas + RC3 overrides"),
        (f"{len(wiring)} + {len(overlay_wiring_operations)} ops", "RC2 source wiring + RC3 patch"),
        (f"{len(traceability):,} + {len(overlay_traceability)}", "RC2 source + RC3 typed trace edges"),
        (f"{len(blocking)} + {sum(1 for p in overlay_parameters if p['status'].startswith('BLOCKING_'))}", "owner blockers + RC3 research sentinels"),
    ]
    metric_html = "".join(f'<div class="card metric"><b>{esc(a)}</b><span>{esc(b)}</span></div>' for a, b in metrics)

    source_links = "".join(
        f'<li><a href="{esc(r["url"])}">{esc(r["title"])}</a> — {status_chip(r["status"])} — {esc(r["use"])}</li>'
        for r in sources if r.get("url", "").startswith("http")
    )

    schemas = []
    for p in sorted((RC2_DIR / "schemas").glob("*.json")):
        schemas.append(f'<article><h3>{esc(p.name)}</h3><pre class="source-code"><code>{esc(p.read_text(encoding="utf-8"))}</code></pre></article>')

    body = []
    body.append(section("document-control", "00", "Document control, authority, and precedence", f"""
    {callout("Controlling status", f'This is the consolidated master build constitution for TRIAD ORIGIN V7. It is {status_chip(STATUS)}. It authorizes specification and implementation work only; it does not prove profitability, certify the current estate, arm an account, or authorize live deployment.', "danger")}
    <div class="grid">{metric_html}</div>
    <h3>Purpose</h3><p>This document combines the RC1 architecture/semantic baseline and the RC2 operational implementation-control registries into one self-contained source. It is deliberately large: an implementer must not need to infer formulas, ownership, plumbing, dependencies, acceptance evidence, or failure behavior from a picture or a short work order.</p>
    <h3>Normative precedence</h3>
    {simple_table(["Rank","Authority","Effect"], [
        ["1", "Authenticated owner decision scoped to exact build/config/contract/venue/account/canary", "Can ratify a currently blocked business variable; cannot silently weaken constitutional invariants."],
        ["2", f"This RC3 master document ({VERSION})", "Controls conflicts in narrative architecture, ownership, safety, and interpretation."],
        ["3", "RC3 correction/refusal ledger", "Overrides known RC1/RC2 conflicts. Affected paths remain SAFE_HOLD until corrected canonical bytes and evidence exist."],
        ["4", "Embedded RC2 canonical registries and schemas", "Operational source data for tasks, dependencies, proposals, wiring and tests, subject to RC3 errata and real status labels."],
        ["5", "Incorporated RC1 master specification", "Normative where RC3/RC2 does not supersede it; RC1 broad checklist rows are traceability parents, not atomic completion proof."],
        ["6", "Topology image and dated MCP books", "Illustrative target and reported evidence only; neither proves current as-built truth."],
        ["7", "Examples, comments, dashboards, generated clients, prior reports", "Non-authoritative. May never override a contract, formula, gate, or signed decision."],
    ])}
    <h3>Supersession map</h3>
    {simple_table(["Area","RC1 role","RC2/RC3 controlling rule"], [
        ["Architecture, causal semantics, contracts, states, migration", "Retained normative baseline", "RC3 corrections and the exact RC2 declarations override any conflict."],
        ["407 implementation rows", "Scope and traceability parents", "RC2 contains 1,088 implementation controls, including 407 meta-level scope-closure rows. Unfinished work must be decomposed before a parent can pass."],
        ["408 verification rows", "Mandatory historical baseline", "All 408 must be connected to enforceable tasks/criteria. Their present disconnected state is an RC3 blocker, not permission to ignore them."],
        ["Symbolic detector/risk variables", "No legacy inheritance", "RC2 declared parameter registry supplies the exact value or NOT_RATIFIED→SAFE_HOLD."],
        ["Wiring overview", "Logical target", f"RC2 supplies {len(wiring)} source rows; the {len(overlay_wiring_operations)} RC3 wiring operations and {len(overlay_formula_wiring_operations)} formula-to-wiring operations control conflicts and must be materialized before evaluation."],
    ])}
    <h3>Normative language</h3><p><b>MUST / MUST NOT / SHALL</b> are release-blocking. <b>SHOULD / SHOULD NOT</b> require a signed, scoped, expiring exception with a compensating control. <b>MAY</b> is optional. <b>TBD / NOT_RATIFIED / UNKNOWN</b> grants no discretion and forces the declared fail-closed behavior.</p>
    <h3>Incorporated-source integrity</h3>{simple_table(["Artifact","SHA-256","Size"], digest_rows)}
    """))

    body.append(section("executive-decision", "01", "Executive decision and system boundary", f"""
    <div class="grid">
      <article class="card wide"><div class="kpi">BUILD</div><h3>TRIAD ORIGIN V7</h3><p>A clean deterministic E02 replacement called <b>TRIAD ORIGIN V7 — Deterministic Causal Edge Core</b>. Retain the TRIAD chassis; do not build a seventh E00–E10 monolith.</p></article>
      <article class="card wide"><div class="kpi">PROVE</div><h3>Deterministic edge first</h3><p>The control population runs E01 → ORIGIN → deterministic E07 → E08 → simulated/isolated E09. E03–E06 intelligence may observe but cannot modify this proof population.</p></article>
      <article class="card wide"><div class="kpi">EXECUTE</div><h3>Maker normal; governed emergency reduction</h3><p>Every normal entry and exit is post-only maker. E09 may use taker only to reduce verified exposure under the strict emergency policy; never to enter, add, or reverse.</p></article>
      <article class="card wide"><div class="kpi">MEASURE</div><h3>Money truth before claims</h3><p>Strict fill.v3 lineage, position truth, all costs, campaign attribution, preregistration, power and multiplicity controls precede any profitability claim.</p></article>
    </div>
    {callout("What is being replaced", "ORIGIN replaces deterministic feature, causal structure, reaction, capsule, hypothesis, and candidate-withdrawal authority around E02. It does not replace canonical market state, intelligence, policy, portfolio risk, venue execution, money truth, outcomes, learning, or governance.", "good")}
    {callout("What is not claimed", "The retained chassis is not assumed correct because it is mature. Every inherited edge must pass G-1/G0 evidence. ORIGIN is not assumed profitable because its semantics are cleaner. Positive net live EV remains an empirical result, not a design property.", "warn")}
    <h3>Authority matrix</h3>{simple_table(["Node","Sole authority","Explicit prohibition"], authority_rows)}
    """))

    body.append(section("topology-reference", "02", "Target topology and mandatory V4 corrections", f"""
    {callout("Illustrative, not as-built", "The supplied V3 topology is embedded for orientation. Its own title says target state. It cannot be used to assert that a service, bus, contract, metric, or ownership boundary is deployed.", "warn")}
    <figure><img class="topology" src="{topology_data}" alt="TRIAD master topology V3 target-state overview"><figcaption class="muted">Source: supplied TRIAD Engine Master Topology V3 target-state illustration.</figcaption></figure>
    <h3>Required correction ledger</h3>{simple_table(["Area","V3 implication","RC3 controlling correction"], correction_rows)}
    """))

    body.append(section("constitutional-laws", "03", "Non-negotiable system laws", f"""
    {callout("No implementer interpretation", "These laws are invariant. A team may propose a versioned change, but it may not locally reinterpret a term, default a missing value, weaken a boundary, or inherit a legacy number.", "danger")}
    {laws_html}
    """))

    body.append(section("blocking-decisions", "04", "Ratified decisions and explicit arming blockers", f"""
    <h3>Ratified design decisions</h3>
    <ul><li>Build ORIGIN as a clean E02 repository/service inside the retained TRIAD chassis.</li><li>Use causal event-time semantics, stable identities, monotonic structure lifecycles, integer arithmetic, exact replay, honest nulls, and deterministic mirroring.</li><li>Keep the deterministic control population free of intelligence mutation until its own economic proof exists.</li><li>Preserve older contracts; introduce additive strict major versions and a measured dual-read/write cutover.</li><li>Make E08 the sole sizing/risk authorization authority and E09 the sole venue/money-fact authority.</li><li>Use maker-only normal execution and permit a governed E09 emergency exit-only taker escape.</li><li>Fence MCP to evidence reads plus the two enumerated append-only off-bus proposal/checkup writes; permit no runtime or money-control route, and keep shadow, simulated, dark, canary, and money populations separate.</li></ul>
    <h3>Blocking owner decisions</h3>
    {callout("Eight values remain intentionally unguessed", "Each row below is NOT_RATIFIED and has an explicit SAFE_HOLD consequence. The engineering team must not substitute a legacy value, a code default, zero, a backtest optimum, or its own risk preference.", "danger")}
    {simple_table(["ID","Variable","Value","Unit","Gate","Exact ratification rule","Failure behavior","Owner"], blocker_rows)}
    {callout("Three additional RC3 research sentinels", "EQUAL_LEVEL_MAX_SPAN, BOOK_TILT_MIN_QUOTE_DEPTH and PROTECTED_SWING_REDUCER_VERSION are separately declared NOT_RATIFIED in Chapter 07. Together with the eight business-owner decisions above, they make 11 explicit value/semantic blockers; other PROPOSED_RC2 parameters also remain unavailable until signed.", "warn")}
    """))

    body.append(section("mcp-evidence", "05", "MCP evidence, money-plane limits, and as-built truth", f"""
    {callout("Dated evidence only", "The two supplied MCP books were audited on 2026-08-07. Their measurements are valuable evidence, but RC3 does not relabel them as fresh runtime observations on 2026-08-09.", "warn")}
    {simple_table(["Fact","Reported value","Controlling interpretation"], mcp_rows)}
    <h3>Required ORIGIN evidence posture</h3><ul><li>MCP has no runtime-control or money-control authority. Its two known writes—<code>propose_action</code> and <code>record_checkup</code>—append only to off-bus proposal/checkup evidence stores and execute nothing.</li><li>All unavailable/dark families return a named unavailable state. Zero is never substituted.</li><li>Phase G-1 must capture current deployed/source parity, account/environment identity, process/writer census, contract/config digests, and exact ingress/runtime reachability.</li><li>Money EV remains blocked until strict fill.v3 and exact candidate→decision→authorization→order→fill→position→outcome lineage are proven prospectively.</li><li>Public authentication must be documented, tested, rate-limited, and secret-safe. No bearer credential is embedded in this document.</li></ul>
    """))

    body.append(section("venue-ingress", "06", "Current Binance ingress requirements", f"""
    {callout("Verified primary-source baseline", "The official USDⓈ-M Futures pages were checked on 2026-08-09 and report last modification on 2026-08-08. These requirements are external and mutable; Gate G1 must re-verify them before certification.", "good")}
    {simple_table(["Control","Exact current requirement","ORIGIN/TRIAD consequence"], venue_rows)}
    <p>Primary sources: <a href="https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Important-WebSocket-Change-Notice">route migration</a>, <a href="https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect">connection rules</a>, <a href="https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly">local order-book procedure</a>, and <a href="https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/change-log">change log</a>.</p>
    """))

    body.append(section("rc3-corrections", "07", "RC3 source audit, conflict resolutions, formula errata, and refusal ledger", f"""
    {callout("This chapter overrides conflicting inherited text", "RC1 and RC2 remain incorporated for traceability, but the rows below are the controlling interpretation. RC2 registry rows are reproduced unmodified in later tables as audit evidence; they are not executable authority where this chapter records a defect.", "danger")}
    <h3>Minimum controlling declarations</h3>
    {simple_table(["Declaration","Controlling value","Operational meaning"], source_declarations)}
    <h3>RC1 conflict-resolution ledger</h3>
    {simple_table(["Area","Conflict","RC3 controlling resolution"], rc1_conflicts)}
    <h3>RC2 semantic-validation and control defects</h3>
    {simple_table(["Finding","Defect","Evidence","Required refusal/correction"], rc2_defects)}
    <h3>RC3 conflict-remediation requirements</h3>
    {callout("Exact where materialized; otherwise blocking", "The rows below distinguish exact patch operations from remediation work that still requires row-level semantic ownership. The 17 SEM mappings and 408 legacy-test enforcement edges are intentionally unresolved here and therefore block G2; this document does not invent blanket mappings.", "warn")}
    {simple_table(["Affected control","Defective RC2 binding","RC3 required replacement/refusal"], rc3_task_overrides)}
    <h3>Machine-readable RC3 normative overlay</h3>
    {callout("Controlling, base-bound patch layer", "The source RC2 files remain immutable audit evidence. The embedded triad.origin.v7.master_overlay.v1 is SHA-bound to those exact bytes, and this HTML also embeds the deterministically materialized effective control bundle, its manifest and a post-apply validation report. Every NOT_STARTED, OPEN or BLOCKING record still denies its gate; materialization is not implementation or arming.", "good")}
    <h4>Exact RC2 base binding</h4>{simple_table(["Artifact","Path / registry","Required SHA-256"], overlay_base_digest_rows)}
    <h4>Deterministic applier contract</h4>{simple_table(["Field","Value"], [["Version", code_text(overlay_applier_contract["version"])],["Canonical JSON", text(overlay_applier_contract["canonical_json"])],["Failure behavior", text(overlay_applier_contract["failure_behavior"])],["Overlay schema SHA-256", code_text(overlay_schema_sha256)],["Executable builder SHA-256", code_text(sha256(ROOT / "build_origin_v7_complete_master_rc3.py"))]])}{applier_steps_html}
    {callout("Executable, not decorative", "The standalone file embeds the exact digest-bound Python builder/applier as base64 and exposes it through the Download executable builder control. The builder executes the closed schema profile, validates base digests, materializes every operation, synchronizes denormalized task fields and refuses partial output on any failed invariant.", "good")}
    <h4>Effective bundle manifest</h4>{simple_table(["Field","Value"], effective_manifest_rows)}
    <h4>Effective registry counts</h4>{simple_table(["Registry metric","Count"], effective_count_rows)}
    <h4>Post-apply validation</h4>{simple_table(["Check","Result"], validation_check_rows)}
    <h4>Overlay parameters</h4>{generic_registry("overlay-parameters", overlay_parameters, ["status","gate","owner"], list(overlay_parameters[0].keys()))}
    <h4>Parameter supersession operations</h4>{generic_registry("overlay-parameter-operations", overlay_parameter_operations, ["operation"], list(overlay_parameter_operations[0].keys()))}
    <h4>Overlay formula replacements</h4>{generic_registry("overlay-formulas", overlay_formulas, ["status","gate"], list(overlay_formulas[0].keys()))}
    <h4>Golden-vector replacement operations</h4>{generic_registry("overlay-golden-vector-operations", overlay_golden_vector_operations, ["operation","status"], list(overlay_golden_vector_operations[0].keys()))}
    <h4>Overlay wiring operations</h4>{generic_registry("overlay-wiring-operations", overlay_wiring_operations, ["operation","gate"], list(overlay_wiring_operations[0].keys()))}
    <h4>Formula-to-wiring traceability operations</h4>{generic_registry("overlay-formula-wiring-operations", overlay_formula_wiring_operations, ["operation","status"], list(overlay_formula_wiring_operations[0].keys()))}
    <h4>Overlay implementation controls</h4>{generic_registry("overlay-tasks", overlay_tasks, ["gate","owner","status"], list(overlay_tasks[0].keys()))}
    <h4>Overlay acceptance criteria</h4>{generic_registry("overlay-acceptance", overlay_acceptance, ["gate","required","initial_result"], list(overlay_acceptance[0].keys()))}
    <h4>DAG edge operations</h4>{generic_registry("overlay-dag", overlay_dag, ["operation"], list(overlay_dag[0].keys()))}
    <h4>Overlay verifications</h4>{generic_registry("overlay-verifications", overlay_verifications, ["gate"], list(overlay_verifications[0].keys()))}
    <h4>Overlay typed traceability edges</h4>{generic_registry("overlay-traceability", overlay_traceability, ["source_type","target_type","gate"], list(overlay_traceability[0].keys()))}
    <h4>Unresolved row-level linkage blockers</h4>{generic_registry("overlay-linkage-blockers", linkage_blockers, ["status","gate"], list(linkage_blockers[0].keys()))}
    <h4>binding.v2 required field law</h4>{generic_registry("binding-v2-fields", binding_v2_required_fields, [], list(binding_v2_required_fields[0].keys()))}
    <h4>binding.v2 lifecycle operations</h4>
    {callout("Migration is deliberately incomplete", f"The effective composition contains 105 binding rows with the binding.v2 field set. {len(binding_v2_unmigrated_ids)} preserved RC2 rows are explicit BLOCKED_NOT_STARTED sentinels: their semantic slot, scope, cardinality and consumer edge are not inferred. RC3-TASK-G2-BINDING-V2 must replace every sentinel with owner-ratified values before G2 can pass.", "danger")}
    {generic_registry("overlay-binding-operations", overlay_binding_operations, ["operation","lifecycle_status"], list(overlay_binding_operations[0].keys()))}
    <h4>Typed external prerequisite registry</h4>{generic_registry("overlay-prerequisites", overlay_prerequisites, ["gate","type","status","accountable_owner"], list(overlay_prerequisites[0].keys()))}
    <h4>Receipt-v2 and semantic-validator requirements</h4>{generic_registry("receipt-v2-requirements", receipt_v2_requirements, [], list(receipt_v2_requirements[0].keys()))}
    <h4>Reproducibility input manifest</h4>{generic_registry("reproducibility-inputs", reproducibility_manifest, [], list(reproducibility_manifest[0].keys()))}
    <h3>Contract catalog/wiring union closure</h3>
    {simple_table(["Set","Count","Contract names","G0 requirement"], contract_closure_rows)}
    <h3>Exact named venue/account/environment refusals</h3>
    {simple_table(["Required code","Trigger","Required behavior"], named_rejection_rows)}
    <h3>Normative formula and vector errata</h3>
    {callout("Status discipline", "An erratum fixes internal contradiction; it does not ratify a parameter whose registry status is PROPOSED_RC2_MUST_RATIFY. Such a formula remains unavailable to a money-capable build until the exact parameter record is signed.", "warn")}
    {simple_table(["Formula/vector","Correction","Exact controlling rule"], formula_errata)}
    <h3>Strict fill.v3 minimum field law</h3>
    {callout("Additive major contract", "fill.v1 and permissive fill.v2 remain immutable. E09 dual-publishes strict fill.v3 from the same raw venue fact, reconciles v2/v3 during migration, quarantines incomplete v3, and cuts consumers over only after 100% required-field and lineage coverage for the selected scope.", "good")}
    {simple_table(["Field family","Required native fields","Completeness rule"], fill_v3_fields)}
    <h3>Parameter-status census</h3>
    {simple_table(["Status","Count","Interpretation"], [
        [status_chip("PROPOSED_RC2_MUST_RATIFY"), str(sum(1 for r in parameters if r["status"]=="PROPOSED_RC2_MUST_RATIFY")), "Candidate values only; affected gate remains blocked until signed."],
        [status_chip("RATIFIED_RC1"), str(sum(1 for r in parameters if r["status"]=="RATIFIED_RC1")), "Retained unless expressly superseded by RC3."],
        [status_chip("DECLARED_RC2"), str(sum(1 for r in parameters if r["status"]=="DECLARED_RC2")), "RC2 declaration subject to RC3 errata and ratification scope."],
        [status_chip("BLOCKING_OWNER_DECISION"), str(len(blocking)), "No value; SAFE_HOLD by definition."],
        [status_chip("Other evidence/target states"), str(len(parameters)-sum(1 for r in parameters if r["status"] in {"PROPOSED_RC2_MUST_RATIFY","RATIFIED_RC1","DECLARED_RC2","BLOCKING_OWNER_DECISION"})), "Vendor-derived, formula-derived, illustrative target or not-provisioned; preserve exact status."],
    ])}
    <h3>Required RC3 validator amendments</h3><ol><li>Parse verification gate membership as a nonempty array of canonical gate IDs; reject composite strings.</li><li>Reject any linked task, formula, parameter, wiring, requirement, inventory, test or source ID absent from its typed registry.</li><li>Attach all 408 preserved RC1 tests to required task/criterion edges and applicable gates.</li><li>Reject PASS/WAIVED P0 evidence, empty scope, empty evidence, open blockers, missing digests/signatures, identity collision between builder and independent reviewer, and illegal status transitions.</li><li>Require schema bytes, exact edge closure and compatibility fixtures for the full 35-name catalog/wiring union before G0.</li><li>Run formula dimension, binding-cardinality, golden-vector and mirror/property checks against corrected RC3 semantics.</li><li>Include generators and exact input digests in the reproducible release source bundle.</li></ol>
    """))

    body.append(section("rc1-incorporated", "08", "Incorporated RC1 normative architecture and semantic baseline", f"""
    {callout("How to read this chapter", "This is the complete RC1 consolidated specification incorporated into RC3 for continuity and auditability. RC3 corrections and the RC2 canonical registries control any conflict. RC1 Documents 07–08 are traceability baselines only; they do not replace the atomic checklist or verification registry later in this file.", "warn")}
    <div class="legacy-baseline">{extract_rc1_main()}</div>
    """, "heavy"))

    body.append(section("gate-ledger", "09", "Release-gate ledger: RC2 source counts plus mandatory RC3 controls", f"""
    {callout("Gate truth is derived", "No human checkbox passes a gate. A current signed receipt requires exact scope, predecessor receipt, complete required tasks/tests, unexpired evidence, matching digests, independent review, no open P0/P1 blocker, and tested stop/rollback.", "danger")}
    {simple_table(["Gate","Phase","Name","RC2 source tasks","RC3 controls","Effective tasks","Entry","Exit","Automatic fail","Receipt","Derived pass rule"], effective_gate_rows)}
    """))

    body.append(section("parameter-registry", "10", f"RC2 source parameter registry ({len(parameters)} records; RC3 overlay controls conflicts)", f"""
    {callout("Value law", "These 183 rows are reproduced for auditability. They are not all ratified: 125 are proposals, eight are value-less blockers, and PAR-179 is expressly superseded. Apply the RC3 overlay first. A NOT_RATIFIED sentinel is a blocker, not a default.", "warn")}
    {parameter_table(parameters)}
    """, "heavy"))

    body.append(section("formula-registry", "11", f"RC2 source formula registry ({len(formulas)} rows; RC3 overlay replaces conflicting semantics)", f"""
    {callout("Semantic law", f'The {len(formulas)} RC2 rows are source evidence, not an unqualified normative registry. The {len(overlay_formulas)} RC3 machine-overlay rows control: {", ".join(row["id"] for row in overlay_formulas)}. Every formula remains subject to its declared readiness, parameters, binding.v2 migration, required vectors and gate evidence.', "warn")}
    {formula_table(formulas)}
    <h3>Formula-to-parameter bindings ({len(bindings)})</h3>
    {generic_registry("bindings", bindings, ["formula_id", "status", "gate"], ["binding_id","formula_id","parameter_id","parameter_name","declared_value","unit","status","gate","boundary_rule","failure_behavior"])}
    <h3>Golden numeric and boundary vectors ({len(golden)})</h3>
    {generic_registry("golden", golden, ["area"], ["id","area","inputs","operation","expected","boundary","linked"])}
    """, "heavy"))

    body.append(section("wiring-registry", "12", f"RC2 source wiring registry ({len(wiring)} rows; {len(overlay_wiring_operations)} RC3 wiring operations)", f"""
    {callout("Source rows plus controlling patch", "The RC2 rows below remain audit evidence. Apply the Chapter 07 wiring and traceability operations before implementation. Logical contract semantics remain transport-neutral across the Phase-0 append-only file ledger and any future certified JetStream binding; NATS is not a production dependency until provisioned, secured, observed, replay-tested and gate-certified.", "warn")}
    {wiring_table(wiring)}
    """, "heavy"))

    body.append(section("task-registry", "13", f"RC2 source implementation-control checklist ({len(tasks):,} rows; {len(overlay_tasks)} RC3 controls)", f"""
    {callout("Source checklist is not effective by itself", "These are RC2 source controls, not proof that every scope parent is atomized or that RC3 defects are repaired. Effective execution also requires every Chapter 07 overlay control. A row passes only after required work is decomposed, all typed hard predecessors pass for the exact scope, every required acceptance criterion and verification has a current immutable receipt, evidence digests match, accountable ownership and independent review are present, and no invariant or blocker invalidates the result.", "danger")}
    {task_table(tasks)}
    """, "heavy"))

    body.append(section("dependency-registry", "14", f"RC2 source dependency graph ({len(dependencies):,} edges; {len(overlay_dag)} RC3 patch operations)", f"""
    {callout("Patch before evaluation", "The RC2 DAG below cannot issue a receipt without the typed ADD/REMOVE operations in Chapter 07. The operation count is not a net-edge count; removals and additions must be applied exactly and revalidated for cycles and reachability.", "warn")}
    {generic_registry("dependencies", dependencies, ["dependency_type", "hard_or_soft"], ["edge_id","predecessor_task_id","successor_task_id","dependency_type","hard_or_soft","condition","lag","external_dependency_id"])}
    """, "heavy"))

    body.append(section("acceptance-registry", "15", f"RC2 source acceptance registry ({len(acceptance):,} rows; {len(overlay_acceptance)} RC3 criteria)", f"""
    {callout("Effective set is additive", "The rows below are the RC2 source set. Every RC3 control has a typed acceptance criterion in Chapter 07; a gate evaluator must require both populations after applying supersession/refusal rules.", "warn")}
    {generic_registry("acceptance", acceptance, ["criticality", "required", "initial_result"], ["criterion_id","task_id","criterion","verification_method","expected_result","verification_id","evidence_type","criticality","required","initial_result","evidence_id"])}
    """, "heavy"))

    body.append(section("verification-registry", "16", f"RC2 source verification registry ({len(verifications):,} rows; {len(overlay_verifications)} RC3 definitions)", f"""
    {callout("Falsification first", "Tests must be able to prove the implementation wrong. Historical optimization, future leakage, duplicate aliases, uncalibrated touch-equals-fill assumptions, hidden costs, weak power and multiplicity are explicit failure modes.", "warn")}
    {callout("Known source-linkage block", "The 182 composite-gate rows, 17 dangling SEM mappings and 408 disconnected RC1 tests remain source defects. Chapter 07 names the required migration and keeps G2 blocked until row-level edges are materialized.", "danger")}
    {verification_table(verifications)}
    """, "heavy"))

    body.append(section("traceability-registry", "17", f"RC2 source traceability registry ({len(traceability):,} links; {len(overlay_traceability)} RC3 typed edges)", f"""
    {callout("Not closed until migration", "The source rows below do not include the effective RC3 edges and contain untyped/free-text reference defects. Apply the Chapter 07 typed edges and complete the blocking requirement/inventory and legacy-test migrations before any gate receipt.", "danger")}
    {generic_registry("traceability", traceability, ["reference_type", "relationship", "required"], ["trace_id","task_id","reference_type","reference_id","relationship","required"])}
    """, "heavy"))

    body.append(section("rc1-crosswalk", "18", f"RC1-to-RC2 scope-closure crosswalk ({len(crosswalk)} rows)", f"""
    {callout("No scope disappears", "Every broad RC1 checklist row remains traceable and has a stable RC2 closure control. The crosswalk does not count an RC1 epic as completed implementation; it proves that its entire intended scope is either closed by atomic work or explicitly refused/deferred.", "info")}
    {generic_registry("crosswalk", crosswalk, ["classification", "corrected_gate", "priority", "canonical_accountable_owner"], list(crosswalk[0].keys()))}
    """, "heavy"))

    body.append(section("evidence-schemas", "19", "RC2 source receipt schemas — audit-only until strict v2 replacement", f"""
    {callout("Not executable authority", "The three displayed RC2 v1 schemas are reproduced unchanged for auditability and are permissive enough to admit semantically invalid PASS records. They cannot authorize any gate. Authority requires the additive receipt-v2 schemas and semantic transition validator defined as NOT_STARTED RC3 controls in Chapter 07, followed by current signed evidence bound to exact scope and digests.", "danger")}
    <div class="schema-grid">{"".join(schemas)}</div>
    """, "heavy"))

    body.append(section("source-register", "20", f"Consolidated source register ({len(sources)} records)", f"""
    {generic_registry("sources", sources, ["status"], ["id","title","url","status","use"])}
    <h3>External primary-source links</h3><ul>{source_links}</ul>
    """))

    body.append(section("ratification", "21", "Ratification, activation, and handoff", f"""
    {callout("Current disposition", f'{status_chip(STATUS)}. Implementation may begin only within the gate sequence. Production-connected execution remains denied until all applicable receipts are current and all 11 explicit business/research value-or-semantic blockers are ratified.', "danger")}
    <h3>Required sign-off record</h3>{simple_table(["Role","Must attest","Current"], [
        ["Owner / Governance", "Scope, risk appetite, canary dimensions, emergency-exit policy and activation manifest", status_chip("PENDING")],
        ["Architecture", "Boundaries, authority, contracts, identity, state machines and as-built parity", status_chip("PENDING")],
        ["Data / E01 / ORIGIN", "Ingress, watermarks, replay, formula semantics, causal availability and structure truth", status_chip("PENDING")],
        ["E07 / E08 / E09 / E10", "Decision, sizing, money authority, protection, accounting and attribution separation", status_chip("PENDING")],
        ["Security / SRE / Operations", "Secrets, access, observability, failure drills, backup/DR and rollback", status_chip("PENDING")],
        ["Validation / Research", "Golden/property/fault tests, preregistration, power, multiplicity, costs and falsification", status_chip("PENDING")],
        ["Release", "Current task/gate receipts, exact digests, one-dimensional promotion and legacy retirement", status_chip("PENDING")],
    ])}
    <h3>Activation law</h3><ol><li>G-1 through G6 prove secure reproducibility, contracts, ingress, deterministic semantics, capsule integrity, paired replay, dark operation and execution rehearsal.</li><li>G7 authorizes exactly one isolated safety canary only after all four canary scope variables and loss controls are ratified.</li><li>G8 requires an adequately powered prospective money sample and determines whether a net economic claim is supported.</li><li>G9 transfers one producer scope dimension at a time, drains and de-permissions legacy writers, and keeps rollback/DR current.</li><li>Any changed code, artifact, config, contract, parameter, instrument metadata, dataset, account, venue behavior or required evidence digest makes dependent receipts stale.</li></ol>
    <div class="signature-grid grid"><article class="card wide"><h3>Owner / Governance</h3><div style="height:70px;border-bottom:1px solid #58717d"></div><p class="muted">Name · signature · UTC timestamp · decision-record ID</p></article><article class="card wide"><h3>Independent technical approver</h3><div style="height:70px;border-bottom:1px solid #58717d"></div><p class="muted">Name · role · signature · UTC timestamp · reviewed digest</p></article></div>
    """))

    toc = [
        ("document-control", "00 · Control & precedence"), ("executive-decision", "01 · Executive boundary"),
        ("topology-reference", "02 · Topology corrections"), ("constitutional-laws", "03 · System laws"),
        ("blocking-decisions", "04 · Ratification blockers"), ("mcp-evidence", "05 · MCP evidence"),
        ("venue-ingress", "06 · Venue ingress"), ("rc3-corrections", "07 · RC3 corrections & refusals"),
        ("rc1-incorporated", "08 · RC1 architecture baseline"), ("gate-ledger", "09 · Gate ledger"),
        ("parameter-registry", "10 · Parameters"), ("formula-registry", "11 · Formulas & vectors"),
        ("wiring-registry", "12 · Wiring & plumbing"), ("task-registry", "13 · Control checklist"),
        ("dependency-registry", "14 · Dependencies"), ("acceptance-registry", "15 · Acceptance criteria"),
        ("verification-registry", "16 · Verification"), ("traceability-registry", "17 · Traceability"),
        ("rc1-crosswalk", "18 · RC1 crosswalk"), ("evidence-schemas", "19 · Evidence schemas"),
        ("source-register", "20 · Sources"), ("ratification", "21 · Ratification & activation"),
    ]
    toc_html = "".join(f'<a href="#{a}">{esc(b)}</a>' for a, b in toc)
    quick = "".join(f'<a href="#{a}">{esc(b.split("·",1)[-1].strip())}</a>' for a, b in toc[:8])
    overlay_raw = overlay_canonical.replace("</", "<\\/")
    overlay_schema_raw = canonical_json(overlay_schema_definition).replace("</", "<\\/")
    effective_bundle_raw = effective_bundle_canonical.replace("</", "<\\/")
    effective_manifest_raw = canonical_json(effective_bundle_manifest).replace("</", "<\\/")
    effective_validation_raw = canonical_json(effective_validation_report).replace("</", "<\\/")
    executable_builder_bytes = Path(__file__).read_bytes()
    executable_builder_b64 = base64.b64encode(executable_builder_bytes).decode("ascii")

    js = r"""
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
function applyFilter(tableId){
  const table=document.getElementById(tableId); if(!table) return;
  const q=($(`[data-query-for="${tableId}"]`)?.value||'').trim().toLowerCase();
  const selects=$$(`[data-facet-for="${tableId}"]`);
  let visible=0,total=0;
  $$('tbody tr',table).forEach(row=>{ total++; let ok=!q||(row.dataset.search||row.textContent.toLowerCase()).includes(q);
    selects.forEach(sel=>{if(sel.value&&(row.dataset[sel.dataset.facet]||'')!==sel.value)ok=false});
    row.hidden=!ok;if(ok)visible++;
  });
  const counter=$(`[data-count-for="${tableId}"]`);if(counter)counter.textContent=`${visible} / ${total}`;
}
$$('[data-query-for]').forEach(el=>el.addEventListener('input',()=>applyFilter(el.dataset.queryFor)));
$$('[data-facet-for]').forEach(el=>el.addEventListener('change',()=>applyFilter(el.dataset.facetFor)));
$$('[data-reset-for]').forEach(btn=>btn.addEventListener('click',()=>{const id=btn.dataset.resetFor;const q=$(`[data-query-for="${id}"]`);if(q)q.value='';$$(`[data-facet-for="${id}"]`).forEach(x=>x.value='');applyFilter(id)}));
function csvCell(v){v=(v||'').replace(/\s+/g,' ').trim();return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}
$$('[data-export-for]').forEach(btn=>btn.addEventListener('click',()=>{const id=btn.dataset.exportFor,t=document.getElementById(id);if(!t)return;const rows=$$('tr',t).filter(r=>!r.hidden);const csv=rows.map(r=>$$('th,td',r).map(c=>csvCell(c.innerText)).join(',')).join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download=`${id}-visible.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}));
document.getElementById('openAll')?.addEventListener('click',()=>$$('details').forEach(d=>d.open=true));
document.getElementById('closeAll')?.addEventListener('click',()=>$$('details').forEach(d=>d.open=false));
function downloadEmbeddedJson(sourceId,filename){const raw=document.getElementById(sourceId)?.textContent;if(!raw)return;const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([raw],{type:'application/json'}));a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function downloadEmbeddedBase64(sourceId,filename){const raw=(document.getElementById(sourceId)?.textContent||'').trim();if(!raw)return;const binary=atob(raw),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([bytes],{type:'text/x-python'}));a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
document.getElementById('downloadOverlay')?.addEventListener('click',()=>downloadEmbeddedJson('rc3-normative-overlay','TRIAD_ORIGIN_V7_RC3_NORMATIVE_OVERLAY.json'));
document.getElementById('downloadEffective')?.addEventListener('click',()=>downloadEmbeddedJson('rc3-effective-control-bundle','TRIAD_ORIGIN_V7_RC3_EFFECTIVE_CONTROL_BUNDLE.json'));
document.getElementById('downloadValidation')?.addEventListener('click',()=>downloadEmbeddedJson('rc3-effective-validation-report','TRIAD_ORIGIN_V7_RC3_EFFECTIVE_VALIDATION_REPORT.json'));
document.getElementById('downloadBuilder')?.addEventListener('click',()=>downloadEmbeddedBase64('rc3-executable-builder','build_origin_v7_complete_master_rc3.py'));
"""

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Complete standalone master specification and implementation document for TRIAD ORIGIN V7.">
<title>TRIAD ORIGIN V7 — Complete Master Specification &amp; Master Document — {VERSION}</title><style>{css}</style></head>
<body id="top"><div class="topline"></div><header class="mast"><div class="mast-inner"><div class="brand"><b>TRIAD ORIGIN V7</b><small>Complete Master · {VERSION}</small></div><nav class="quicknav">{quick}<button id="openAll" class="chip no-print" type="button">Open details</button><button id="closeAll" class="chip no-print" type="button">Close details</button><button id="downloadOverlay" class="chip no-print" type="button">Download RC3 overlay</button><button id="downloadEffective" class="chip no-print" type="button">Download effective bundle</button><button id="downloadValidation" class="chip no-print" type="button">Download validation</button><button id="downloadBuilder" class="chip no-print" type="button">Download executable builder</button></nav></div></header>
<section class="hero"><div class="container"><div class="eyebrow">Deterministic Causal Edge Core · Consolidated build constitution</div><h1>Complete Master <em>Specification</em><br>&amp; Master Document</h1><p class="lead">Architecture, causal structure definitions, contracts, identities, state machines, formulas, parameters, wiring, plumbing, implementation inventory, atomic checklist, dependencies, acceptance evidence, falsification tests, migration, rollback, and ratification control—in one standalone HTML file.</p><div class="chips">{status_chip(VERSION)}{status_chip(STATUS)}<span class="chip">Issued {DATE}</span><span class="chip">No profitability claim</span><span class="chip">No live activation</span></div></div></section>
<div class="layout"><aside class="side"><strong>Master contents</strong>{toc_html}</aside><main class="content">{"".join(body)}</main></div>
<footer class="footer"><div class="container"><b>TRIAD ORIGIN V7 — Deterministic Causal Edge Core</b><p>Complete Master Specification &amp; Master Document · {VERSION} · {DATE} · {STATUS}</p><p>This document contains no credential and grants no live authority. Governed implementation evidence and signed gate receipts control release.</p></div></footer><a class="backtop no-print" href="#top" aria-label="Back to top">↑</a>
<script id="rc3-overlay-schema" type="application/schema+json">{overlay_schema_raw}</script>
<script id="rc3-normative-overlay" type="application/json">{overlay_raw}</script>
<script id="rc3-effective-control-bundle" type="application/json">{effective_bundle_raw}</script>
<script id="rc3-effective-bundle-manifest" type="application/json">{effective_manifest_raw}</script>
<script id="rc3-effective-validation-report" type="application/json">{effective_validation_raw}</script>
<script id="rc3-executable-builder" type="application/octet-stream" data-encoding="base64">{executable_builder_b64}</script>
<script>{js}</script></body></html>"""

    OUTPUT.write_text(document, encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT), "bytes": OUTPUT.stat().st_size, "sha256": sha256(OUTPUT),
        "tasks": len(tasks), "dependencies": len(dependencies), "acceptance": len(acceptance),
        "verifications": len(verifications), "parameters": len(parameters), "formulas": len(formulas),
        "bindings": len(bindings), "golden": len(golden), "wiring": len(wiring),
        "traceability": len(traceability), "crosswalk": len(crosswalk), "blocking": len(blocking),
        "overlay_tasks": len(overlay_tasks), "overlay_dag_operations": len(overlay_dag),
        "overlay_verifications": len(overlay_verifications), "overlay_traceability": len(overlay_traceability),
        "effective_bundle_sha256": effective_bundle_sha256,
        "effective_counts": effective_control_bundle["summary"],
        "effective_validation": effective_validation_report["status"],
    }, indent=2))


if __name__ == "__main__":
    build()

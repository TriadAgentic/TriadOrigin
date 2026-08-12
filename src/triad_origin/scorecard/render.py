"""Deterministic, dependency-free HTML rendering for a built scorecard report."""

from __future__ import annotations

from ..canonical import canonical_json, sha256_hex
from .model import ScorecardError


def verify_report_digest(report: dict) -> None:
    if not isinstance(report, dict):
        raise ScorecardError("scorecard report must be an object")
    declared = report.get("content_digest")
    if not isinstance(declared, str):
        raise ScorecardError("scorecard report lacks content_digest")
    unsigned = {key: value for key, value in report.items() if key != "content_digest"}
    actual = sha256_hex(canonical_json(unsigned))
    if actual != declared:
        raise ScorecardError("scorecard content_digest mismatch")


def render_scorecard_html(report: dict) -> str:
    """Render one self-contained report.  Rendering has no authority or write side effect."""
    verify_report_digest(report)
    publication = report["publication"]
    outcome = publication["outcome"]
    stage_rows = "".join(_stage_row(row) for row in report["stage_cells"])
    edge_rows = "".join(_edge_row(row) for row in report["edge_cells"])
    metric_rows = "".join(_metric_row(row) for row in report["metrics"])
    component_rows = "".join(_component_row(row) for row in report["components"])
    trace_rows = "".join(_trace_rows(report["candidate_traces"]))
    blocker_rows = "".join(_finding_row(row) for row in publication["blockers"])
    status_rows = "".join(_finding_row(row) for row in publication["status_flags"])
    conservation = report["conservation"]
    desired = report["desired_posture"]
    observed = report["observed_posture"]
    cohort = report["candidate_cohort"]
    observed_text = "UNAVAILABLE" if observed is None else " / ".join(observed.values())
    desired_text = " / ".join(desired.values())
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TRIAD full-pipeline scorecard</title><style>
:root{color-scheme:dark;--bg:#071015;--panel:#0d1920;--line:#25404c;--text:#e8f0f2;--muted:#93a9b1;--cyan:#4adcf8;--green:#66e09a;--amber:#f5c35b;--red:#ff7180;--violet:#c3a2ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:28px}h1{font-size:28px;margin:0 0 6px}h2{font-size:17px;margin:30px 0 10px;color:var(--cyan)}p{color:var(--muted)}.hero,.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}.hero{display:grid;grid-template-columns:1fr auto;gap:20px}.outcome{align-self:start;padding:8px 12px;border-radius:999px;font-weight:800;border:1px solid currentColor}.WITHHELD,.STALE,.UNRECONCILED{color:var(--red)}.STATUS_ONLY,.DARK,.NOT_IMPLEMENTED{color:var(--amber)}.FULL,.PROVEN{color:var(--green)}.OFF{color:var(--violet)}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.stat{background:#09141a;border:1px solid var(--line);border-radius:9px;padding:12px}.stat b{display:block;font-size:20px}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line)}th,td{padding:9px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em}code{color:var(--cyan)}.state{font-weight:800}.scroll{overflow:auto}.empty{padding:14px;color:var(--muted)}details{margin:3px 0}summary{cursor:pointer;color:var(--cyan)}@media(max-width:850px){main{padding:14px}.hero{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}}
</style></head><body><main>""" + f"""
<section class="hero"><div><h1>TRIAD full-pipeline scorecard</h1><div class="muted">{_escape(report['report_id'])} · as-of {_escape(report['as_of_us'])}</div><p>{_escape(report['claim'])}. Visibility is not deployment, activation, execution, or merge authority.</p></div><div class="outcome {_escape(outcome)}">{_escape(outcome)}</div></section>
<h2>Four-plane posture</h2><section class="panel"><b>Desired:</b> {_escape(desired_text)}<br><b>Observed:</b> {_escape(observed_text)}<br><b>Proof:</b> <span class="state {_escape(report['posture_proof']['state'])}">{_escape(report['posture_proof']['state'])}</span> · {_escape(report['posture_proof']['reason_code'])}</section>
<h2>Terminal conservation</h2><section class="grid">
{_stat('Candidates', conservation['candidate_count'])}{_stat('Evaluations', conservation['evaluation_count'])}{_stat('Population routes', conservation['population_instance_count'])}{_stat('Reconciled terminals', conservation['reconciled_terminal_count'])}
{_stat('Pending within grace', conservation['pending_count'])}{_stat('Unexplained', conservation['unexplained_count'])}{_stat('Conflicts', conservation['conflict_count'])}{_stat('Orphans', conservation['orphan_terminal_count'])}
</section>
<h2>E02 candidate cohort</h2><section class="panel">{_cohort_summary(cohort)}</section>
<h2>Stage proof cells</h2><div class="scroll"><table><thead><tr><th>Stage/path</th><th>Component</th><th>State</th><th>Four proof dimensions</th><th>Reason</th></tr></thead><tbody>{stage_rows}</tbody></table></div>
<h2>Pipeline edges</h2><div class="scroll"><table><thead><tr><th>Edge</th><th>Channel</th><th>State</th><th>Watermarks / freshness</th><th>Reason</th></tr></thead><tbody>{edge_rows}</tbody></table></div>
<h2>Component-role registry</h2><div class="scroll"><table><thead><tr><th>Stage</th><th>Component</th><th>Role</th><th>Mapping / evidence</th><th>Authority claims</th></tr></thead><tbody>{component_rows}</tbody></table></div>
<h2>Candidate → evaluation → population → terminal</h2><div class="scroll"><table><thead><tr><th>Candidate</th><th>Evaluation</th><th>Decision</th><th>Event-time posture</th><th>Population instance</th><th>Terminal facts</th></tr></thead><tbody>{trace_rows or '<tr><td colspan="6" class="empty">No candidate traces supplied</td></tr>'}</tbody></table></div>
<h2>Plane-separated metrics</h2><div class="scroll"><table><thead><tr><th>Metric</th><th>Population</th><th>Value</th><th>Availability</th><th>Reason</th></tr></thead><tbody>{metric_rows or '<tr><td colspan="5" class="empty">No metric facts supplied</td></tr>'}</tbody></table></div>
<h2>Publication blockers</h2><div class="scroll"><table><thead><tr><th>Code</th><th>Subject</th></tr></thead><tbody>{blocker_rows or '<tr><td colspan="2" class="empty">None</td></tr>'}</tbody></table></div>
<h2>Status-only limitations</h2><div class="scroll"><table><thead><tr><th>Code</th><th>Subject</th></tr></thead><tbody>{status_rows or '<tr><td colspan="2" class="empty">None</td></tr>'}</tbody></table></div>
<h2>Immutable identity</h2><section class="panel"><code>{_escape(report['content_digest'])}</code><p>Candidate traces, route instances, terminal evidence references, and metric zero proofs remain in the JSON companion artifact.</p></section>
</main></body></html>"""


def _stage_row(row: dict) -> str:
    dimensions = row["dimensions"]
    dimension_text = " · ".join(
        f"{name}={_display(value)}" for name, value in dimensions.items()
    )
    return (
        f"<tr><td><b>{_escape(row['stage'])}/{_escape(row['path'])}</b><br>"
        f"<span class=\"muted\">expected {_escape(row['expected_state'])}</span></td>"
        f"<td>{_escape(row['component_id'])}</td>"
        f"<td class=\"state {_escape(row['state'])}\">{_escape(row['state'])}</td>"
        f"<td>{_escape(dimension_text)}</td><td><code>{_escape(row['reason_code'])}</code></td></tr>"
    )


def _edge_row(row: dict) -> str:
    proof = row["proof"]
    detail = (
        "unavailable" if proof is None else
        f"{_display(proof['source_watermark'])} → {_display(proof['consumer_watermark'])}; "
        f"{_display(proof['freshness_age_ms'])}/{_display(proof['freshness_bound_ms'])} ms"
    )
    return (
        f"<tr><td><b>{_escape(row['source_stage'])} → {_escape(row['target_stage'])}</b></td>"
        f"<td>{_escape(row['channel'])}</td>"
        f"<td class=\"state {_escape(row['state'])}\">{_escape(row['state'])}</td>"
        f"<td>{_escape(detail)}</td><td><code>{_escape(row['reason_code'])}</code></td></tr>"
    )


def _metric_row(row: dict) -> str:
    return (
        f"<tr><td><code>{_escape(row['metric_id'])}</code></td>"
        f"<td>{_escape(row['population'])}</td><td>{_escape(row['value'])} {_escape(row['unit'])}</td>"
        f"<td>{_escape(row['availability'])}</td><td>{_escape(row['reason_code'])}</td></tr>"
    )


def _component_row(row: dict) -> str:
    return (
        f"<tr><td>{_escape(row['stage'])}</td><td><code>{_escape(row['component_id'])}</code></td>"
        f"<td>{_escape(row['role'])}</td><td>{_escape(row['mapping_status'])}<br>"
        f"<span class=\"muted\">{_escape(', '.join(row['mapping_evidence_refs']) or 'NONE')}</span></td>"
        f"<td>{_escape(', '.join(row['authority_claims']) or 'NONE')}</td></tr>"
    )


def _trace_rows(traces: list[dict]) -> list[str]:
    rows: list[str] = []
    for trace in traces:
        for evaluation in trace["evaluations"]:
            posture = " / ".join(evaluation["event_posture"].values())
            for route in evaluation["routes"]:
                terminals = ", ".join(
                    f"{terminal['kind']}:{terminal['terminal_id']}"
                    for terminal in route["terminals"]
                ) or "UNAVAILABLE"
                rows.append(
                    f"<tr><td><code>{_escape(trace['candidate_id'])}</code></td>"
                    f"<td><code>{_escape(evaluation['evaluation_id'])}</code></td>"
                    f"<td>{_escape(evaluation['decision_state'])}</td>"
                    f"<td>{_escape(posture)}</td>"
                    f"<td>{_escape(route['population'])}<br><code>"
                    f"{_escape(route['population_instance_id'])}</code></td>"
                    f"<td>{_escape(terminals)}</td></tr>"
                )
    return rows


def _cohort_summary(cohort: dict | None) -> str:
    if cohort is None:
        return '<span class="WITHHELD">UNAVAILABLE</span>'
    return (
        f"<b>{_escape(cohort['cohort_id'])}</b> · {_escape(len(cohort['candidate_ids']))} "
        f"candidates · complete={_escape(cohort['complete'])}<br>"
        f"window {_escape(cohort['window_start_us'])}–{_escape(cohort['window_end_us'])} μs · "
        f"source watermark <code>{_escape(cohort['source_watermark'])}</code>"
    )


def _finding_row(row: dict) -> str:
    return f"<tr><td><code>{_escape(row['code'])}</code></td><td>{_escape(row['subject'])}</td></tr>"


def _stat(label: str, value) -> str:
    return f"<div class=\"stat\"><span class=\"muted\">{_escape(label)}</span><b>{_escape(value)}</b></div>"


def _display(value) -> str:
    if value is None:
        return "UNAVAILABLE"
    if type(value) is bool:
        return "TRUE" if value else "FALSE"
    return str(value)


def _escape(value) -> str:
    text = _display(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )

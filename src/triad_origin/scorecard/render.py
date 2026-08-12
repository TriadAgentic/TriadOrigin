"""Deterministic, dependency-free HTML rendering for a built scorecard report.

The browser artifact is deliberately inert.  It contains no script, network reference, form,
credential, endpoint, or control verb.  Every headline value is derived from the authenticated
report object after its content digest has been verified; there is no independently maintained
UI count that can drift from the canonical JSON.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from ..canonical import canonical_json, sha256_hex
from .model import ScorecardError


_POSTURE_FIELDS = (
    ("venue_environment", "Venue environment"),
    ("venue_activation", "Venue activation"),
    ("paper_activation", "Paper activation"),
    ("shadow_activation", "Shadow activation"),
)

_STAGE_LAYER = {
    "E00": "data",
    "E01": "engine",
    "E02": "engine",
    "E03": "intelligence",
    "E04": "intelligence",
    "E05": "intelligence",
    "E06": "intelligence",
    "E07": "decision",
    "E08": "risk",
    "E09": "execution",
    "E10": "outcomes",
}

_STAGE_LABEL = {
    "E00": "Market & raw data",
    "E01": "Canonical state",
    "E02": "Origin · features & candidates",
    "E03": "Forecast provider",
    "E04": "Specialist evidence",
    "E05": "Intelligence coordinator",
    "E06": "Language & knowledge",
    "E07": "Decision & policy",
    "E08": "Risk & governance",
    "E09": "Execution",
    "E10": "Outcomes & learning",
}

_STAGE_CONTRACT = {
    "E00": "raw facts",
    "E01": "market_state.v2",
    "E02": "feature_snapshot.v2 / edge_candidate.v2",
    "E03": "forecast advisory · binding not ratified",
    "E04": "specialist advisory · binding not ratified",
    "E05": "fused calibrated evidence · binding not ratified",
    "E06": "language / knowledge advisory · binding not ratified",
    "E07": "decision.v2",
    "E08": "risk_decision.v2 / execution_authorization.v3",
    "E09": "execution_cmd.v2 / fill.v3",
    "E10": "outcome.v2",
}

_POPULATION_ORDER = ("SHADOW", "PAPER", "TESTNET", "LIVE")

_STATE_ICON = {
    "PROVEN": "✓",
    "OFF": "○",
    "DARK": "◐",
    "NOT_IMPLEMENTED": "∅",
    "STALE": "⌛",
    "UNRECONCILED": "!",
    "WITHHELD": "!",
    "STATUS_ONLY": "◐",
    "FULL": "✓",
    "RATIFIED": "✓",
    "OPERATOR_ASSERTED_UNATTESTED": "△",
    "UNBOUND": "!",
    "CONFLICT": "×",
}


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
    """Render one self-contained evidence console with no authority or write side effect."""
    verify_report_digest(report)
    publication = report["publication"]
    outcome = publication["outcome"]
    components = {row["component_id"]: row for row in report["components"]}
    metrics_by_stage = _metrics_by_stage(report["metrics"])
    stage_rows = "".join(_stage_row(row, components) for row in report["stage_cells"])
    edge_rows = "".join(_edge_row(row) for row in report["edge_cells"])
    metric_rows = "".join(_metric_row(row) for row in report["metrics"])
    component_rows = "".join(_component_row(row) for row in report["components"])
    trace_rows = "".join(_trace_rows(report["candidate_traces"]))
    blocker_rows = "".join(_finding_row(row) for row in publication["blockers"])
    status_rows = "".join(_finding_row(row) for row in publication["status_flags"])
    pipeline_cards = _pipeline_cards(report["stage_cells"], components, metrics_by_stage)
    route_cards = "".join(_edge_card(row) for row in report["edge_cells"])
    population_cards = "".join(_population_card(report, name) for name in _POPULATION_ORDER)
    conservation = report["conservation"]
    cohort = report["candidate_cohort"]
    state_counts = Counter(row["state"] for row in report["stage_cells"])
    proven_edges = sum(row["state"] == "PROVEN" for row in report["edge_cells"])
    mapped_components = sum(row["mapping_status"] == "RATIFIED" for row in report["components"])
    cohort_count = 0 if cohort is None else len(cohort["candidate_ids"])
    headline = (
        _stat("Authoritative E02 cohort", cohort_count, _cohort_badge(cohort))
        + _stat(
            "Stage-path proof",
            state_counts["PROVEN"],
            f"of {len(report['stage_cells'])} PROVEN",
        )
        + _stat(
            "Canonical edges",
            proven_edges,
            f"of {len(report['edge_cells'])} PROVEN",
        )
        + _stat(
            "Ratified mappings",
            mapped_components,
            f"of {len(report['components'])} supplied",
        )
        + _stat(
            "Terminal reconciliation",
            conservation["reconciled_terminal_count"],
            f"of {conservation['population_instance_count']} routes",
        )
        + _stat(
            "Unresolved",
            conservation["unexplained_count"] + conservation["conflict_count"],
            f"{conservation['orphan_terminal_count']} orphan terminals",
        )
    )
    posture_cards = "".join(
        _posture_card(key, label, report["desired_posture"], report["observed_posture"])
        for key, label in _POSTURE_FIELDS
    )
    evidence_alert = _publication_alert(publication)
    conservation_state = _conservation_display_state(conservation, cohort)

    return _document_start(report, outcome) + f"""
<a class="skip-link" href="#main">Skip to scorecard</a>
<header class="truth-header">
  <div class="shell hero-row">
    <div>
      <div class="eyebrow">TRIAD ORIGIN · E00–E10 · EVIDENCE CONSOLE</div>
      <h1>Full-pipeline scorecard</h1>
      <p class="lede">Origin E02 with an independently evidenced E05 coordinator, Kairos/E03 and
      Logos/E06 mappings. Visibility is not deployment, activation, admission, risk, execution,
      promotion, or merge authority.</p>
    </div>
    {_badge(outcome, large=True)}
  </div>
  <div class="shell truth-grid" aria-label="Report truth bar">
    <div><span>Report</span><code>{_escape(report['report_id'])}</code></div>
    <div><span>As-of (epoch μs)</span><code>{_escape(report['as_of_us'])}</code></div>
    <div><span>Evidence trust</span><strong>{_escape(report['evidence_trust'])}</strong></div>
    <div><span>Content digest</span><code title="{_escape(report['content_digest'])}">{_escape(_short(report['content_digest']))}</code></div>
  </div>
</header>
<nav class="anchor-nav" aria-label="Scorecard sections"><div class="shell">
  <a href="#overview">Overview</a><a href="#pipeline">Pipeline</a>
  <a href="#conservation">Conservation</a><a href="#populations">Populations</a>
  <a href="#lineage">Lineage</a><a href="#outcomes">Outcomes</a>
  <a href="#evidence">Evidence</a>
</div></nav>
<main id="main" class="shell">
  <section id="overview" class="section" aria-labelledby="overview-title">
    <div class="section-heading"><div><span class="section-no">01</span><h2 id="overview-title">Operational truth</h2></div>
    <p>All counts below are derived from the canonical report rows. Missing evidence stays missing.</p></div>
    {evidence_alert}
    <div class="stat-grid">{headline}</div>
    <h3>Four-plane event-time posture</h3>
    <div class="posture-grid">{posture_cards}</div>
    <div class="proof-strip">
      <span>Posture proof</span>{_badge(report['posture_proof']['state'])}
      <code>{_escape(report['posture_proof']['reason_code'])}</code>
      <span>freshness={_escape(report['posture_proof']['freshness'])}</span>
      <span>attestation={_escape(report['posture_proof']['attestation'])}</span>
      <span>side-effect census={_display(report['posture_proof']['side_effect_census_complete'])}</span>
    </div>
  </section>

  <section id="pipeline" class="section" aria-labelledby="pipeline-title">
    <div class="section-heading"><div><span class="section-no">02</span><h2 id="pipeline-title">As-built evidence pipeline</h2></div>
    <p>Cards report supplied evidence. Grey or dashed routes are not proven wiring.</p></div>
    <div class="callout info"><strong>Authority law.</strong> Origin owns E02 evidence. E05 fans out
    advisory work and joins it. Kairos/E03 forecasts; Logos/E06 is the language/knowledge boundary.
    Only E07 admits, E08 sizes/allows, and E09 acts at a venue. Kairos and Logos never call each other.</div>
    <div class="pipeline-grid">{pipeline_cards}</div>
    <h3>Canonical evidence routes</h3>
    <div class="route-grid">{route_cards or _empty('No edge evidence supplied')}</div>
  </section>

  <section id="conservation" class="section" aria-labelledby="conservation-title">
    <div class="section-heading"><div><span class="section-no">03</span><h2 id="conservation-title">Terminal conservation</h2></div>
    <p>Every matured population route must resolve to one compatible terminal.</p></div>
    <div class="law-grid">
      <article class="law"><span class="law-no">LAW A</span><h3>Candidate disposition</h3><p>Every authoritative
      Origin candidate must be evaluated. Rejection, untradeable, accepted, expired, or withdrawal
      remains explicit; none may disappear.</p></article>
      <article class="law"><span class="law-no">LAW B</span><h3>Population routes</h3><p>Every accepted
      evaluation receives an independent SHADOW route, plus only the additive PAPER and event-time
      TESTNET or LIVE routes authorized by its posture. Populations never share a denominator.</p></article>
    </div>
    <div class="stat-grid compact">
      {_stat('Candidates', conservation['candidate_count'], 'authoritative cohort')}
      {_stat('Evaluations', conservation['evaluation_count'], 'explicit cardinality')}
      {_stat('Population routes', conservation['population_instance_count'], 'event-time derived')}
      {_stat('Reconciled', conservation['reconciled_terminal_count'], 'compatible terminals')}
      {_stat('Pending', conservation['pending_count'], 'within maturity grace')}
      {_stat('Unexplained', conservation['unexplained_count'], 'matured without terminal')}
      {_stat('Conflicts', conservation['conflict_count'], 'incompatible / duplicate')}
      {_stat('Orphans', conservation['orphan_terminal_count'], 'terminal without route')}
    </div>
    <div class="proof-strip"><span>Conservation result</span>
      {_badge(conservation_state)}
      <span>multiplicity explicit={_display(conservation['multiplicity_explicit'])}</span>
    </div>
  </section>

  <section id="populations" class="section" aria-labelledby="populations-title">
    <div class="section-heading"><div><span class="section-no">04</span><h2 id="populations-title">Plane-separated populations</h2></div>
    <p>SHADOW, PAPER, TESTNET, and LIVE are independent event-time populations.</p></div>
    <div class="population-grid">{population_cards}</div>
  </section>

  <section id="lineage" class="section" aria-labelledby="lineage-title">
    <div class="section-heading"><div><span class="section-no">05</span><h2 id="lineage-title">Candidate lineage</h2></div>
    <p>Candidate → evaluation → route → terminal. Empty and unresolved traces remain visible.</p></div>
    <div class="table-wrap"><table><caption>Candidate, evaluation, event-time posture, population, and terminal lineage</caption>
      <thead><tr><th scope="col">Candidate</th><th scope="col">Evaluation</th><th scope="col">Decision</th>
      <th scope="col">Event-time posture</th><th scope="col">Population instance</th><th scope="col">Terminal facts</th></tr></thead>
      <tbody>{trace_rows or _empty_row(6, 'No candidate traces supplied')}</tbody></table></div>
    <details class="drawer"><summary>E02 candidate cohort proof</summary><div class="drawer-body">{_cohort_summary(cohort)}</div></details>
  </section>

  <section id="outcomes" class="section" aria-labelledby="outcomes-title">
    <div class="section-heading"><div><span class="section-no">06</span><h2 id="outcomes-title">Health and outcomes</h2></div>
    <p>Null is not zero. Economic metrics remain scoped to one explicit population.</p></div>
    <div class="callout warning"><strong>Legacy matrix boundary.</strong> Historical 418-cell backfill
    is not embedded or promoted here. It becomes a subordinate historical view only after its cohort,
    source, population, fee lineage, denominators, confidence intervals, and E02→E10 identity chain
    are supplied. Until then, its performance is <code>NOT_MEASURABLE</code>.</div>
    <div class="table-wrap"><table><caption>Canonical plane-separated metric facts</caption>
      <thead><tr><th scope="col">Metric</th><th scope="col">Population</th><th scope="col">Value</th>
      <th scope="col">Availability</th><th scope="col">Reason</th></tr></thead>
      <tbody>{metric_rows or _empty_row(5, 'No metric facts supplied')}</tbody></table></div>
  </section>

  <section id="evidence" class="section" aria-labelledby="evidence-title">
    <div class="section-heading"><div><span class="section-no">07</span><h2 id="evidence-title">Evidence manifest</h2></div>
    <p>Proof state, mapping, provenance, and findings stay independently visible.</p></div>
    <details class="drawer" open><summary>Stage and path evidence</summary><div class="drawer-body table-wrap"><table>
      <caption>E00–E10 stage/path proof cells</caption><thead><tr><th scope="col">Stage/path</th><th scope="col">Component</th>
      <th scope="col">State</th><th scope="col">Four proof dimensions</th><th scope="col">Reason</th></tr></thead>
      <tbody>{stage_rows}</tbody></table></div></details>
    <details class="drawer"><summary>Pipeline edge evidence</summary><div class="drawer-body table-wrap"><table>
      <caption>Canonical semantic edge proof</caption><thead><tr><th scope="col">Edge</th><th scope="col">Channel</th>
      <th scope="col">State</th><th scope="col">Watermarks / freshness</th><th scope="col">Reason</th></tr></thead>
      <tbody>{edge_rows or _empty_row(5, 'No edge evidence supplied')}</tbody></table></div></details>
    <details class="drawer"><summary>Component-role registry</summary><div class="drawer-body table-wrap"><table>
      <caption>Component mapping and authority assertions</caption><thead><tr><th scope="col">Stage</th><th scope="col">Component</th>
      <th scope="col">Role</th><th scope="col">Mapping / evidence</th><th scope="col">Authority claims</th></tr></thead>
      <tbody>{component_rows or _empty_row(5, 'No component mappings supplied')}</tbody></table></div></details>
    <div class="findings-grid">
      <div><h3>Publication blockers <span class="count">{len(publication['blockers'])}</span></h3><div class="table-wrap"><table>
        <caption>Blocking findings</caption><thead><tr><th scope="col">Code</th><th scope="col">Subject</th></tr></thead>
        <tbody>{blocker_rows or _empty_row(2, 'None')}</tbody></table></div></div>
      <div><h3>Status limitations <span class="count">{len(publication['status_flags'])}</span></h3><div class="table-wrap"><table>
        <caption>Status-only limitations</caption><thead><tr><th scope="col">Code</th><th scope="col">Subject</th></tr></thead>
        <tbody>{status_rows or _empty_row(2, 'None')}</tbody></table></div></div>
    </div>
    <div class="identity"><span>Canonical immutable report identity</span><code>{_escape(report['content_digest'])}</code>
      <p>Candidate traces, route instances, terminal evidence references, and zero proofs remain in
      the canonical JSON companion. This HTML never changes report authority.</p></div>
  </section>
</main>
<footer><div class="shell"><strong>TRIAD ORIGIN FULL-PIPELINE SCORECARD</strong><span>{_escape(report['claim'])}</span>
<span>authority effect: {_escape(report['authority_effect'])}</span><span>population totals are never aggregated</span></div></footer>
</body></html>"""


def _document_start(report: dict, outcome: str) -> str:
    title = f"TRIAD Origin full-pipeline scorecard · {report['report_id']} · {outcome}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src 'none'; script-src 'none'; connect-src 'none'; object-src 'none'; media-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
<title>{_escape(title)}</title><style>
:root{{--bg:#030a0f;--bg2:#061118;--panel:#081820;--panel2:#0b2029;--line:#1d4655;--line2:#153540;--ink:#e9f1f4;--muted:#91a6af;--data:#25b99a;--engine:#3aa7df;--intelligence:#a178d4;--decision:#d9ad2f;--risk:#dc7d2e;--execution:#19bdd0;--outcomes:#58b96a;--danger:#ef7070;--warning:#f1c45d;--off:#72a4b8;--focus:#fff27a;--mono:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth;scroll-padding-top:74px}}body{{margin:0;background:radial-gradient(circle at 50% -20%,#0c2631 0,var(--bg) 42%);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}a{{color:var(--execution)}}a:focus-visible,summary:focus-visible{{outline:3px solid var(--focus);outline-offset:3px}}code{{font-family:var(--mono);color:#bceef6;overflow-wrap:anywhere}}.shell{{width:min(1560px,calc(100% - 36px));margin-inline:auto}}.skip-link{{position:fixed;left:12px;top:-80px;background:#fff;color:#000;padding:12px 16px;z-index:1000;border-radius:4px}}.skip-link:focus{{top:12px}}.truth-header{{border-bottom:1px solid var(--line);background:linear-gradient(180deg,#07151d 0,#041017 100%)}}.hero-row{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:28px;padding:30px 0 22px;align-items:start}}.eyebrow{{font:700 11px/1.3 var(--mono);letter-spacing:.14em;color:var(--execution)}}h1{{font-size:clamp(28px,4vw,48px);line-height:1.05;letter-spacing:.01em;margin:7px 0 10px}}h2{{margin:0;font-size:23px}}h3{{font-size:15px;margin:20px 0 9px}}p{{color:var(--muted)}}.lede{{max-width:900px;margin:0;font-size:15px}}.truth-grid{{display:grid;grid-template-columns:1.2fr .7fr .8fr .8fr;border-top:1px solid var(--line2)}}.truth-grid>div{{min-width:0;padding:12px 15px;border-right:1px solid var(--line2)}}.truth-grid>div:last-child{{border-right:0}}.truth-grid span{{display:block;text-transform:uppercase;letter-spacing:.08em;font:700 10px/1.2 var(--mono);color:var(--muted);margin-bottom:4px}}.truth-grid code,.truth-grid strong{{font-size:12px}}.anchor-nav{{position:sticky;top:0;z-index:40;background:rgba(3,10,15,.96);border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}}.anchor-nav .shell{{display:flex;overflow:auto;gap:5px}}.anchor-nav a{{display:grid;place-items:center;min-height:48px;padding:0 13px;text-decoration:none;color:var(--muted);font:700 11px/1 var(--mono);text-transform:uppercase;letter-spacing:.06em;white-space:nowrap;border-bottom:2px solid transparent}}.anchor-nav a:hover{{color:var(--ink);border-color:var(--execution)}}.section{{padding:42px 0 8px}}.section-heading{{display:flex;justify-content:space-between;align-items:end;gap:24px;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:16px}}.section-heading>div{{display:flex;gap:10px;align-items:center}}.section-heading p{{margin:0;text-align:right;max-width:620px}}.section-no{{display:inline-grid;place-items:center;border:1px solid var(--line);width:32px;height:32px;border-radius:50%;font:700 10px var(--mono);color:var(--execution)}}.badge{{display:inline-flex;align-items:center;gap:7px;min-height:28px;padding:4px 9px;border:1px solid currentColor;border-radius:999px;font:800 10px/1 var(--mono);letter-spacing:.04em;white-space:nowrap}}.badge.large{{min-height:42px;padding:8px 15px;font-size:12px}}.badge.PROVEN,.badge.FULL,.badge.RATIFIED{{color:#72e3a2;background:#0c2a20}}.badge.WITHHELD,.badge.UNRECONCILED,.badge.STALE,.badge.CONFLICT{{color:#ff8b8b;background:#2d1418}}.badge.STATUS_ONLY,.badge.DARK,.badge.NOT_IMPLEMENTED,.badge.OPERATOR_ASSERTED_UNATTESTED{{color:#ffd272;background:#2b2412}}.badge.OFF,.badge.UNBOUND{{color:#a8cad7;background:#13262d}}.callout{{border:1px solid var(--line);border-left:4px solid var(--execution);border-radius:6px;background:var(--panel);padding:12px 14px;margin:12px 0 16px;color:var(--muted)}}.callout strong{{color:var(--ink)}}.callout.danger{{border-left-color:var(--danger);background:#1d1115}}.callout.warning{{border-left-color:var(--warning);background:#1d1a10}}.stat-grid{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px}}.stat-grid.compact{{grid-template-columns:repeat(4,minmax(0,1fr))}}.stat{{min-width:0;background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:7px;padding:12px}}.stat span{{display:block;color:var(--muted);font:700 10px/1.2 var(--mono);text-transform:uppercase;letter-spacing:.04em}}.stat b{{display:block;font:800 25px/1.2 var(--mono);margin:5px 0;color:var(--ink)}}.stat small{{display:block;color:var(--muted)}}.posture-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}}.posture-card{{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:12px}}.posture-card h4{{font:700 10px var(--mono);text-transform:uppercase;color:var(--muted);margin:0 0 8px}}.posture-values{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.posture-values span{{display:block;color:var(--muted);font-size:10px}}.posture-values b{{font:800 16px var(--mono)}}.proof-strip{{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px;padding:10px 12px;background:#06151c;border:1px dashed var(--line);border-radius:7px;color:var(--muted)}}.proof-strip>span:first-child{{color:var(--ink);font-weight:800}}.pipeline-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}.stage-card{{--accent:var(--engine);position:relative;min-width:0;background:linear-gradient(180deg,color-mix(in srgb,var(--accent) 10%,var(--panel)),var(--panel));border:1px solid color-mix(in srgb,var(--accent) 60%,var(--line));border-top:4px solid var(--accent);border-radius:8px;padding:13px;overflow:hidden}}.stage-card.data{{--accent:var(--data)}}.stage-card.engine{{--accent:var(--engine)}}.stage-card.intelligence{{--accent:var(--intelligence)}}.stage-card.decision{{--accent:var(--decision)}}.stage-card.risk{{--accent:var(--risk)}}.stage-card.execution{{--accent:var(--execution)}}.stage-card.outcomes{{--accent:var(--outcomes)}}.stage-head{{display:flex;align-items:start;justify-content:space-between;gap:8px}}.stage-id{{font:800 18px var(--mono);color:var(--accent)}}.stage-card h3{{margin:5px 0 10px;font-size:16px}}.stage-card dl{{margin:0;display:grid;grid-template-columns:86px minmax(0,1fr);gap:5px 8px;font-size:12px}}.stage-card dt{{color:var(--muted)}}.stage-card dd{{margin:0;overflow-wrap:anywhere}}.stage-card .contract{{margin-top:10px;padding-top:9px;border-top:1px solid var(--line2);font:11px/1.4 var(--mono);color:#bed3db}}.route-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}}.route-card{{border:1px dashed var(--line);border-left:3px solid var(--muted);background:var(--panel);padding:10px;border-radius:6px;min-width:0}}.route-card.proven{{border-style:solid;border-left-color:var(--execution)}}.route-card b{{font:800 12px var(--mono)}}.route-card code{{display:block;font-size:10px;margin:4px 0}}.route-card small{{color:var(--muted)}}.law-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}}.law{{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:15px}}.law h3{{margin:5px 0}}.law p{{margin:0}}.law-no{{color:var(--execution);font:800 10px var(--mono);letter-spacing:.1em}}.population-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}.population-card{{background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}}.population-card header{{display:flex;justify-content:space-between;align-items:center;padding:12px 13px;background:#0a2029;border-bottom:1px solid var(--line)}}.population-card h3{{margin:0;font:800 16px var(--mono)}}.population-card dl{{display:grid;grid-template-columns:1fr auto;gap:6px 10px;padding:12px;margin:0}}.population-card dt{{color:var(--muted)}}.population-card dd{{margin:0;font-family:var(--mono)}}.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:7px;background:var(--panel)}}table{{width:100%;border-collapse:collapse;min-width:780px}}caption{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}th,td{{padding:9px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line2)}}th{{position:sticky;top:0;z-index:2;background:#0c2a34;color:#b8cbd2;font:800 10px/1.2 var(--mono);text-transform:uppercase;letter-spacing:.05em}}tbody tr:nth-child(even) td{{background:#07151c}}tbody tr:last-child td{{border-bottom:0}}td{{font-size:12px}}.state-text{{font-weight:800}}.state-text.PROVEN{{color:#72e3a2}}.state-text.WITHHELD,.state-text.UNRECONCILED,.state-text.STALE{{color:#ff8b8b}}.state-text.STATUS_ONLY,.state-text.DARK,.state-text.NOT_IMPLEMENTED{{color:#ffd272}}.state-text.OFF{{color:#a8cad7}}.muted{{color:var(--muted)}}.empty{{padding:18px;color:var(--muted);text-align:center}}.drawer{{margin:9px 0;border:1px solid var(--line);border-radius:7px;background:var(--panel)}}.drawer summary{{display:flex;align-items:center;min-height:48px;cursor:pointer;padding:0 14px;color:var(--ink);font-weight:800}}.drawer summary::marker{{color:var(--execution)}}.drawer-body{{border-top:1px solid var(--line);padding:13px}}.drawer-body.table-wrap{{padding:0;border:0;border-radius:0}}.findings-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.count{{display:inline-grid;place-items:center;min-width:24px;height:24px;border:1px solid var(--line);border-radius:50%;font:800 10px var(--mono);color:var(--muted)}}.identity{{margin:18px 0;padding:14px;border:1px solid var(--line);background:#06151c;border-radius:7px}}.identity>span{{display:block;color:var(--muted);font:800 10px var(--mono);text-transform:uppercase;margin-bottom:6px}}.identity p{{margin:7px 0 0}}footer{{margin-top:42px;border-top:1px solid var(--line);background:#02070a}}footer .shell{{display:flex;flex-wrap:wrap;gap:12px 24px;padding:18px 0;color:var(--muted);font:10px var(--mono)}}footer strong{{color:var(--ink)}}
@media(max-width:1200px){{.stat-grid{{grid-template-columns:repeat(3,1fr)}}.pipeline-grid,.route-grid{{grid-template-columns:repeat(3,1fr)}}.population-grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:820px){{.shell{{width:min(100% - 24px,1560px)}}.hero-row{{grid-template-columns:1fr}}.truth-grid{{grid-template-columns:1fr 1fr}}.truth-grid>div:nth-child(2){{border-right:0}}.section-heading{{display:block}}.section-heading p{{text-align:left}}.pipeline-grid,.route-grid{{grid-template-columns:repeat(2,1fr)}}.posture-grid{{grid-template-columns:repeat(2,1fr)}}.findings-grid{{grid-template-columns:1fr}}}}
@media(max-width:520px){{body{{font-size:14px}}.truth-grid,.stat-grid,.stat-grid.compact,.pipeline-grid,.route-grid,.population-grid,.posture-grid,.law-grid{{grid-template-columns:1fr}}.truth-grid>div{{border-right:0}}.stage-card{{min-height:auto}}.anchor-nav a{{min-height:48px}}}}
@media(prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}}}
@media print{{:root{{color-scheme:light}}body{{background:#fff;color:#111}}.anchor-nav,.skip-link{{display:none}}.truth-header,.panel,.stage-card,.route-card,.law,.population-card,.table-wrap,.drawer,.identity,.stat,.posture-card{{background:#fff!important;color:#111;border-color:#777}}p,.muted,footer .shell{{color:#333}}.section{{break-inside:avoid}}.drawer:not([open])>.drawer-body{{display:block}}}}
</style></head><body>"""


def _publication_alert(publication: dict) -> str:
    outcome = publication["outcome"]
    blockers = len(publication["blockers"])
    flags = len(publication["status_flags"])
    css = "danger" if outcome == "WITHHELD" else "warning" if outcome == "STATUS_ONLY" else "info"
    return (
        f'<div class="callout {css}"><strong>{_escape(outcome)}.</strong> '
        f'{blockers} publication blockers and {flags} status limitations. '
        "FULL, when available, means evidence completeness only; it never means trading readiness "
        "or authority.</div>"
    )


def _posture_card(key: str, label: str, desired: dict, observed: dict | None) -> str:
    observed_value = "UNAVAILABLE" if observed is None else observed[key]
    return (
        f'<article class="posture-card"><h4>{_escape(label)}</h4><div class="posture-values">'
        f'<div><span>Desired</span><b>{_escape(desired[key])}</b></div>'
        f'<div><span>Observed</span><b>{_escape(observed_value)}</b></div>'
        "</div></article>"
    )


def _pipeline_cards(
    stage_cells: list[dict],
    components: dict[str, dict],
    metrics_by_stage: dict[str, list[dict]],
) -> str:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in stage_cells:
        grouped[row["stage"]].append(row)
    return "".join(
        _stage_card(stage, grouped[stage], components, metrics_by_stage)
        for stage in _STAGE_LABEL
    )


def _stage_card(
    stage: str,
    rows: list[dict],
    components: dict[str, dict],
    metrics_by_stage: dict[str, list[dict]],
) -> str:
    component_ids = {row["component_id"] for row in rows}
    component_id = next(iter(component_ids)) if len(component_ids) == 1 else None
    if component_id is None and component_ids == {None}:
        stage_components = [
            item for item in components.values() if item["stage"] == stage
        ]
        if len(stage_components) == 1:
            component_id = stage_components[0]["component_id"]
    component = components.get(component_id)
    mapping = "CONFLICT" if len(component_ids) > 1 else "UNBOUND" if component is None else component["mapping_status"]
    component_text = "CONFLICT" if len(component_ids) > 1 else "UNAVAILABLE" if component_id is None else component_id
    aggregate_state = _aggregate_stage_state(rows)
    proofs = [row["proof"] for row in rows if row["proof"] is not None]
    activation_values = {proof["activation"] for proof in proofs}
    freshness_values = {proof["freshness"] for proof in proofs}
    activation = _single_or_mixed(activation_values)
    freshness = _single_or_mixed(freshness_values)
    watermarks = [proof["consumer_watermark"] for proof in proofs if proof["consumer_watermark"] is not None]
    newest = "UNAVAILABLE" if not watermarks else " | ".join(sorted(set(watermarks)))
    counts = [metric for metric in metrics_by_stage.get(stage, []) if metric["metric_class"] == "COUNT"]
    count_text = "UNAVAILABLE"
    observed = [metric for metric in counts if metric["value"] is not None]
    if observed:
        count_text = ", ".join(f"{_metric_short(item['metric_id'])}={item['value']}" for item in observed[:3])
    mapping_detail = _mapping_product_hint(stage, component_text, mapping)
    path_detail = " · ".join(
        f"{row['path']}={row['state']} (expected {row['expected_state']})" for row in rows
    )
    authority = " | ".join(sorted({row["authority"] for row in rows}))
    return f"""<article class="stage-card {_escape(_STAGE_LAYER[stage])}" data-stage-card="{_escape(stage)}">
      <div class="stage-head"><div class="stage-id">{_escape(stage)}</div>{_badge(aggregate_state)}</div>
      <h3>{_escape(_STAGE_LABEL[stage])}</h3>
      <dl><dt>Component</dt><dd><code>{_escape(component_text)}</code>{mapping_detail}</dd>
      <dt>Mapping</dt><dd>{_badge(mapping)}</dd><dt>Paths</dt><dd>{_escape(path_detail)}</dd>
      <dt>Activation</dt><dd>{_escape(activation)}</dd><dt>Freshness</dt><dd>{_escape(freshness)}</dd>
      <dt>Watermark</dt><dd><code>{_escape(newest)}</code></dd><dt>Counts</dt><dd>{_escape(count_text)}</dd>
      <dt>Authority</dt><dd>{_escape(authority)}</dd></dl>
      <div class="contract">CONTRACT · {_escape(_STAGE_CONTRACT[stage])}</div>
    </article>"""


def _aggregate_stage_state(rows: list[dict]) -> str:
    if all(
        (row["expected_state"] == "ACTIVE" and row["state"] == "PROVEN")
        or (row["expected_state"] == "OFF" and row["state"] == "OFF")
        for row in rows
    ):
        return "PROVEN"
    for state in ("STALE", "UNRECONCILED", "CONFLICT", "NOT_IMPLEMENTED", "DARK", "OFF"):
        if any(row["state"] == state for row in rows):
            return state
    return rows[0]["state"]


def _single_or_mixed(values: set[str]) -> str:
    if not values:
        return "UNAVAILABLE"
    if len(values) == 1:
        return next(iter(values))
    return "MIXED_PATHS"


def _mapping_product_hint(stage: str, component_id: str, mapping: str) -> str:
    if stage == "E03" and "kairos" in component_id.lower():
        return f'<br><span class="muted">Kairos · {_escape(mapping)}</span>'
    if stage == "E05":
        return '<br><span class="muted">independent coordinator</span>'
    if stage == "E06" and "logos" in component_id.lower():
        return f'<br><span class="muted">Logos · {_escape(mapping)}</span>'
    return ""


def _edge_card(row: dict) -> str:
    css = "proven" if row["state"] == "PROVEN" else ""
    return (
        f'<article class="route-card {css}"><b>{_escape(row["source_stage"])} → '
        f'{_escape(row["target_stage"])}</b><code>{_escape(row["channel"])}</code>'
        f'{_badge(row["state"])}<small>{_escape(row["reason_code"])}</small></article>'
    )


def _population_card(report: dict, population: str) -> str:
    routes = [row for row in report["routes"] if row["population"] == population]
    route_ids = {row["population_instance_id"] for row in routes}
    terminals = [row for row in report["terminals"] if row["population_instance_id"] in route_ids]
    metrics = [row for row in report["metrics"] if row["population"] == population]
    observed_metrics = sum(row["value"] is not None for row in metrics)
    matured = sum(row["matured"] for row in routes)
    if population == "SHADOW":
        desired = report["desired_posture"]["shadow_activation"]
    elif population == "PAPER":
        desired = report["desired_posture"]["paper_activation"]
    else:
        desired = report["desired_posture"]["venue_activation"]
    return f"""<article class="population-card"><header><h3>{_escape(population)}</h3>{_badge(desired)}</header>
      <dl><dt>Population routes</dt><dd>{len(routes)}</dd><dt>Matured routes</dt><dd>{matured}</dd>
      <dt>Terminal records</dt><dd>{len(terminals)}</dd><dt>Observed metrics</dt><dd>{observed_metrics}</dd>
      <dt>Missing metrics</dt><dd>{len(metrics) - observed_metrics}</dd></dl></article>"""


def _conservation_display_state(conservation: dict, cohort: dict | None) -> str:
    """Do not render vacuous empty-set reconciliation as a positive proof."""
    has_authoritative_population = (
        cohort is not None
        and cohort["complete"]
        and bool(cohort["candidate_ids"])
        and conservation["population_instance_count"] > 0
    )
    if conservation["reconciled"] and has_authoritative_population:
        return "PROVEN"
    return "UNRECONCILED"


def _stage_row(row: dict, components: dict[str, dict]) -> str:
    dimensions = row["dimensions"]
    dimension_text = " · ".join(
        f"{name}={_display(value)}" for name, value in dimensions.items()
    )
    component = components.get(row["component_id"])
    mapping = "UNBOUND" if component is None else component["mapping_status"]
    return (
        f"<tr><td><b>{_escape(row['stage'])}/{_escape(row['path'])}</b><br>"
        f"<span class=\"muted\">expected {_escape(row['expected_state'])}</span></td>"
        f"<td>{_escape(row['component_id'])}<br><span class=\"muted\">{_escape(mapping)}</span></td>"
        f"<td>{_state_text(row['state'])}</td>"
        f"<td>{_escape(dimension_text)}</td><td><code>{_escape(row['reason_code'])}</code></td></tr>"
    )


def _edge_row(row: dict) -> str:
    proof = row["proof"]
    detail = (
        "UNAVAILABLE" if proof is None else
        f"{_display(proof['source_watermark'])} → {_display(proof['consumer_watermark'])}; "
        f"{_display(proof['freshness_age_ms'])}/{_display(proof['freshness_bound_ms'])} ms"
    )
    return (
        f"<tr><td><b>{_escape(row['source_stage'])} → {_escape(row['target_stage'])}</b></td>"
        f"<td><code>{_escape(row['channel'])}</code></td>"
        f"<td>{_state_text(row['state'])}</td>"
        f"<td>{_escape(detail)}</td><td><code>{_escape(row['reason_code'])}</code></td></tr>"
    )


def _metric_row(row: dict) -> str:
    value = "—" if row["value"] is None else row["value"]
    unit = "" if row["value"] is None else f" {row['unit']}"
    return (
        f"<tr><td><code>{_escape(row['metric_id'])}</code></td>"
        f"<td>{_escape(row['population'])}</td><td>{_escape(value)}{_escape(unit)}</td>"
        f"<td>{_escape(row['availability'])}</td><td>{_escape(row['reason_code'])}</td></tr>"
    )


def _component_row(row: dict) -> str:
    return (
        f"<tr><td>{_escape(row['stage'])}</td><td><code>{_escape(row['component_id'])}</code></td>"
        f"<td>{_escape(row['role'])}</td><td>{_badge(row['mapping_status'])}<br>"
        f"<span class=\"muted\">{_escape(', '.join(row['mapping_evidence_refs']) or 'NONE')}</span></td>"
        f"<td>{_escape(', '.join(row['authority_claims']) or 'NONE')}</td></tr>"
    )


def _trace_rows(traces: list[dict]) -> list[str]:
    rows: list[str] = []
    for trace in traces:
        for evaluation in trace["evaluations"]:
            posture = " / ".join(
                evaluation["event_posture"][key] for key, _ in _POSTURE_FIELDS
            )
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
        return '<span class="state-text UNRECONCILED">! UNAVAILABLE</span>'
    zero_proof = "PRESENT" if cohort["zero_proof"] is not None else "NOT_APPLICABLE"
    return (
        f"<b>{_escape(cohort['cohort_id'])}</b> · {_escape(len(cohort['candidate_ids']))} "
        f"candidates · complete={_escape(cohort['complete'])} · zero proof={_escape(zero_proof)}<br>"
        f"window {_escape(cohort['window_start_us'])}–{_escape(cohort['window_end_us'])} μs · "
        f"source watermark <code>{_escape(cohort['source_watermark'])}</code> · cut "
        f"<code>{_escape(cohort['source_cut_digest'])}</code>"
    )


def _cohort_badge(cohort: dict | None) -> str:
    if cohort is None:
        return "NO EVIDENCE"
    if not cohort["complete"]:
        return "INCOMPLETE"
    if not cohort["candidate_ids"]:
        return "0 · RECEIPT"
    return "COMPLETE CUT"


def _finding_row(row: dict) -> str:
    return f"<tr><td><code>{_escape(row['code'])}</code></td><td>{_escape(row['subject'])}</td></tr>"


def _stat(label: str, value, note: str) -> str:
    return (
        f'<article class="stat"><span>{_escape(label)}</span><b>{_escape(value)}</b>'
        f'<small>{_escape(note)}</small></article>'
    )


def _badge(state: str, *, large: bool = False) -> str:
    icon = _STATE_ICON.get(str(state), "·")
    css = " large" if large else ""
    return (
        f'<span class="badge {_escape(state)}{css}"><span aria-hidden="true">{_escape(icon)}</span>'
        f'{_escape(state)}</span>'
    )


def _state_text(state: str) -> str:
    icon = _STATE_ICON.get(state, "·")
    return f'<span class="state-text {_escape(state)}"><span aria-hidden="true">{_escape(icon)}</span> {_escape(state)}</span>'


def _metrics_by_stage(metrics: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for metric in metrics:
        prefix = metric["metric_id"].split(".", 1)[0].upper()
        if prefix in _STAGE_LABEL:
            result[prefix].append(metric)
    return result


def _metric_short(metric_id: str) -> str:
    bits = metric_id.split(".")
    return ".".join(bits[1:-1]) or metric_id


def _short(value: str) -> str:
    return value if len(value) <= 22 else f"{value[:12]}…{value[-8:]}"


def _empty(message: str) -> str:
    return f'<div class="empty">{_escape(message)}</div>'


def _empty_row(columns: int, message: str) -> str:
    return f'<tr><td colspan="{columns}" class="empty">{_escape(message)}</td></tr>'


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

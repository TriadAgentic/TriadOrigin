# TRIAD box change request — investigation MCP only

**Date:** 2026-08-10  
**Status:** ready for a box operator to execute after preflight approval  
**Scope:** expose and verify exactly six read-only `investigation` MCP tools  
**Not in scope:** B00R, TriadOrigin deployment, E08/E09, venue or execution work

This is an operator change request, not a blind paste-and-run script. The repository does not contain
the box's current paths, process supervisor topology, firewall policy, service account, or effective
configuration precedence. Those facts must be resolved on the box and recorded before any mutation.

## 0. Non-negotiable boundary

TriadOrigin remains the deterministic DARK-only E02 edge core. E08 authorizes and E09 executes.
Do not inspect, disclose, mutate, or invoke configurations, credentials, control APIs, or processes
belonging to Origin, Judge, Executor, E08, E09, or venues. The only permitted execution-derived reads
are the ledger `live_fills` and `live_intents` data accessed internally by the six approved
investigation tools. Private machine processing of the selected config target is permitted only for
backup, four-key validation, and rollback; unrelated values must never be displayed or returned.

The Origin safety posture remains distinct from enabling this read-only MCP family:

```text
activation_result=DENIED_SAFE_HOLD
venue_environment=OFF
venue_activation=OFF
paper_activation=OFF
shadow_activation=LIVE
```

Forbidden actions include changing `TRIAD_LIVE_ENABLED`, `TRIAD_EXEC_MODE`, arm tokens, venue
credentials, order/cancel/flatten paths, or any PAPER, TESTNET, or LIVE-money setting. Do not call
`propose_action` or `record_checkup`; both append data.

B00R is separate repository-governance work. No box output can supply a GitHub ruleset, CODEOWNERS
identity, provider canary, signed receipt, or protected receipt anchor.

## 1. Required operator inputs

Record these values in the returned evidence manifest. Placeholders are a hard stop.

| Input | Required proof |
|---|---|
| Deployed TRIAD Learning root | absolute real path, Git commit, clean status or reviewed dirty diff |
| Keeper file | absolute real path, SHA-256, owner/group/mode |
| Effective config target | exactly one of the keeper or the active `mcp.v1.json`; precedence proven from deployed `config.py` and keeper |
| Keeper Python | absolute executable path used by the running child |
| Canonical bank | absolute source SQLite path; source-versus-mirror status recorded |
| Canonical ledger | absolute source ledger root |
| Accounts | real, unique account IDs and each resolved ledger path |
| Keeper identity | PID, start time, user, parent, command |
| MCP child identity | sole port-8801 PID, start time, user, parent, Python, command and imported module paths |
| Maintenance window | approved interruption window and rollback owner |
| Network boundary | firewall/PF evidence proving the unauthenticated listener is restricted as intended |

Machine-reject empty, whitespace-containing, wildcard, duplicate, placeholder, and nonexistent account
IDs. Verify every resolved account path using the MCP service identity, not only the interactive
operator.

Before work begins, verify the required local tools are already present: the keeper Python and its
test environment, `git`, `curl`, `jq`, `rg`, `lsof`, `shasum`, `sudo`, `ps`,
`/sbin/pfctl`, and `/usr/sbin/netstat`. Do not install packages on production for this change.

## 2. Preflight — complete before configuration changes

### 2.1 Deployed/source parity

Capture:

- deployed Git commit and worktree status;
- SHA-256 of the stable keeper, `server.py`, `config.py`, and
  `families/investigation.py`;
- the running child's Python executable and imported file paths for
  `triad_core.mcp.server`, `triad_core.mcp.config`, and
  `triad_core.mcp.families.investigation`.

Every imported path must resolve to the reviewed deployment or a separately pinned installed
artifact. Tests from a checkout the keeper does not import are not deployment evidence.

### 2.2 Database and ledger identity

Do not hash the live multi-gigabyte SQLite file. Record its real path and `stat` identity plus
`-wal` and `-shm` metadata. Open it only through an escaped `Path.as_uri()` URI with
`mode=ro`, set `PRAGMA query_only=ON`, verify it reads back as `1`, then record
`user_version`, `schema_version`, and table inventory. Do not checkpoint, vacuum, or copy the
live database.

Prove the service identity can traverse the ledger root and read the database and every resolved
account input.

### 2.3 Process identity

On the documented MacStudio, use `ps -axo pid=,ppid=,user=,lstart=,command=` rather than Linux-only
`pgrep -af`.

Require exactly one listener on TCP 8801. Record the keeper and child PID, start time, user, PPID,
Python path, command, and imported paths. Do not authorize a future termination from this early
snapshot; Section 5 requires the entire fingerprint to be re-resolved immediately before `TERM`.

### 2.4 Firewall/trust-boundary gate

This gate precedes activation because the supplied contract says the MCP listener is unauthenticated
on `0.0.0.0:8801`.

Capture, without aborting away the evidence:

- `/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate`;
- `sudo -n /sbin/pfctl -sr`;
- `/usr/sbin/netstat -anv -p tcp` filtered to port 8801; and
- the relevant upstream/VLAN/host policy.

A human network owner must confirm that these facts restrict the listener to the intended trust
boundary. If the commands fail, the policy is ambiguous, or the listener is broader than intended,
return `BLOCKED_FIREWALL_EVIDENCE` and do not activate.

Successful loopback access does not establish public access. The supplied MCP book documents
Cloudflare device pairing for the public endpoint; it does not document query-token authentication.
If pairing is prohibited, remote public access remains blocked.

### 2.5 Focused tests

Run only the deployed investigation-family test file:

```text
tests/mcp/test_investigation_family.py
```

All nine documented tests must pass. Do not install dependencies or run unreviewed live/integration
tests on production. Record the run ID, commit, and exact result of any complete MCP suite executed on
a clean non-production runner. That full-suite result is an MCP source/release signal, not an
additional production-box activation gate; the supplied books disagree on historical totals and
document two pre-existing failures.

## 3. Measure the live baseline

Use loopback only: `http://127.0.0.1:8801/mcp`.

The MCP client used for evidence must:

- initialize with protocol `2025-06-18`;
- keep the returned session ID in a mode-600 private header file, never an exported variable or
  process argument;
- use `curl -H @<private-header-file>`, connect timeout, and a maximum time greater than the
  server's 30-second tool timeout;
- require the expected HTTP status;
- parse JSON or complete SSE events;
- join multiline SSE `data:` fields, ignore pings and non-JSON events, and select exactly one
  JSON-RPC response matching the expected request ID; and
- delete private headers and unset session state through an `EXIT` cleanup trap.

Save a sorted `tools/list` name inventory and derive the `investigate_*` subset. Compare it
machine-to-machine with this canonical file:

```text
investigate_contract_integrity
investigate_death_causes
investigate_estate_provenance
investigate_money_population
investigate_populations
investigate_symbol_funnel
```

Choose exactly one mode:

| Measured baseline | Mode | Action |
|---|---|---|
| No `investigate_*` names | `ACTIVATION` | Continue to Section 4 |
| Exactly the canonical six | `VERIFICATION_ONLY` | Do not edit or restart; continue to Section 6 |
| Partial, extra, renamed, or duplicate investigation surface | none | Return `BLOCKED_DEPLOYMENT_DRIFT` |

The dated 142/148 totals are observations, not acceptance thresholds.

## 4. Activation — one config target, private rollback material

Skip this section in `VERIFICATION_ONLY` mode.

Create two separate mode-700 directories:

- an evidence directory that may be returned after redaction; and
- a private rollback directory that is never archived.

The keeper may contain the full environment. Store the raw pre-change keeper/config copy and any raw
diff only in the private rollback directory. Never print or `tee` that diff. The returned evidence
may contain only before/after hashes, owner/group/mode, and an allowlisted summary of changed key
names.

Back up exactly the proven effective config target, then edit only the investigation family values:

| Environment form | JSON form |
|---|---|
| `TRIAD_MCP_INVESTIGATION_FAMILY_ENABLED=1` | `"investigation_family_enabled": true` |
| `TRIAD_MCP_INVESTIGATION_BANK_PATH=<canonical bank>` | `"investigation_bank_path": "<canonical bank>"` |
| `TRIAD_MCP_INVESTIGATION_LEDGER_ROOT=<canonical ledger>` | `"investigation_ledger_root": "<canonical ledger>"` |
| exact accounts key proven from deployed code | `"investigation_accounts": "<approved IDs>"` |

Do not assume an environment accounts key that the deployed `config.py` does not implement.

Validate the selected target with `bash -n` or `jq -e .`. A private zero-context diff must return
exactly status 1: status 0 means no change; status greater than 1 is an error. Parse that private diff
and require the changed-key set to be exactly the four investigation settings. Any other key,
especially an Origin/live/venue/credential/execution setting, triggers rollback.

Record the after hash and prove owner/group/mode are unchanged.

## 5. Restart only the re-verified MCP child

Skip this section in `VERIFICATION_ONLY` mode.

Immediately before termination:

1. prove the keeper PID and start time are unchanged and it is alive;
2. re-resolve the sole port-8801 listener;
3. require the same child PID and start time captured in preflight;
4. require the same user, PPID, Python path, command, and imported deployment; and
5. require the approved interruption window to be open.

Only then send `TERM` to that exact child. Never terminate a PID taken only from the earlier
snapshot, a wildcard process match, the keeper, Origin, E08, E09, judge, or Executor.

Wait a bounded interval for exactly one replacement listener. Require a different child PID, a new
start time, the same keeper PPID, user, Python, MCP command, and deployed imports. Failure to prove the
replacement fingerprint triggers Section 8 rollback.

## 6. Verify the surface and all six tools

Open a new MCP session. Never reuse a pre-restart session.

Save a second sorted tool inventory and machine-compute additions and removals. Also preserve the
complete `tools/list` entries for the canonical six: names, descriptions, and `inputSchema`.
Compare them with the reviewed deployed registration and reject any write/control argument or schema
change. Record the initialize response's actual server name/version and negotiated protocol before
and after. A name match with a signature, schema, server, or protocol mismatch is
`BLOCKED_DEPLOYMENT_DRIFT`.

| Mode | Required exact result |
|---|---|
| `ACTIVATION` | additions equal the canonical six; removals empty |
| `VERIFICATION_ONLY` | full before/after lists identical; canonical six already present |

Record host and MCP-process RSS/memory-pressure evidence before and after the calls. Call each
canonical tool once, strictly sequentially; do not overlap heavy tools. The normalizer must require
the expected JSON-RPC ID, reject a
JSON-RPC error, reject `result.isError=true`, require every examined content item to be an object,
and extract exactly one JSON tool envelope. Functional acceptance requires all six envelopes to have
`ok:true`.

`DISJOINT` and `CONTAMINATED` are data verdicts, not transport failures. A `CONTAMINATED`
result may leave the MCP transport technically verified, but it must emit a named contamination
finding and the affected scorecard must not be treated as P&L; do not return an unqualified verified
outcome. `NOT_MEASURABLE` and
`UNRESOLVED_SYMBOL` may be valid data results. Any `unavailable`, `tool_timeout`,
`not_implemented`, missing/duplicate envelope, malformed content, or HTTP/session failure leaves
functional verification incomplete.

Run a separate recorded data-law review:

- provenance reports authoritative source status; its resolved database and ledger real paths and
  account set exactly equal the approved preflight inputs; `MIRROR`, `UNKNOWN`, or any mismatch
  is `BLOCKED_PROVENANCE_MISMATCH` and triggers rollback in activation mode;
- every result names SHADOW or MONEY and never blends the planes;
- while side/role is absent, WR, EV, MFE, MAE, and capture remain `NOT_MEASURABLE` under F-004;
- when symbol is absent, it is recovered only through the documented
  `intent_id → live_intents` join; a failed join returns `UNRESOLVED_SYMBOL` under F-011; and
- dated August 7 counts are reference observations, never present-day thresholds.

Repeat the firewall capture after activation. A missing command, changed firewall/PF policy, or
broader listener boundary triggers rollback.

## 7. Evidence that may be returned

Return a redacted archive and a checksum containing:

- UTC operator transcript and maintenance-window approval;
- source commit/status and stable-file hashes;
- keeper/child identity before and after;
- database/ledger/account identity without database contents;
- pre/post firewall and listener evidence;
- focused nine-test result;
- before/after tool inventories and exact delta;
- six normalized JSON-RPC responses and extracted `ok:true` envelopes;
- the recorded data-law review;
- selected-target before/after hashes, owner/group/mode, and changed-key names; and
- final outcome: `VERIFIED_ACTIVATION`, `VERIFIED_ALREADY_ENABLED`, `ROLLED_BACK`, or
  `BLOCKED_<REASON>`.

Keep shell tracing disabled while handling sessions or configuration. Build the return archive from
an explicit allowlist of the items above; do not archive the evidence directory wholesale. Before
packaging, delete private response headers. Scan the allowlisted archive for session IDs, tokens, API
keys, cookies, pairing codes, credentials, private keys, signing seeds, full environment dumps, raw
keeper/config copies, and raw diffs. The private rollback directory is never returned.

## 8. Symmetric rollback

Rollback is mandatory for any activation-mode failure after the config edit.

1. Re-verify the keeper PID, start time, user, and command.
2. If exactly one expected MCP child exists, re-verify its complete
   PID/start-time/user/PPID/Python/command fingerprint.
3. If no listener/child exists because the bad config caused a crash loop, restore and validate the
   config first; do not require or attempt to terminate a nonexistent child. Wait for the unchanged
   keeper to spawn one valid child.
4. If an unknown process owns port 8801, do not kill it. Restore the private config copy and escalate.
5. Restore the private pre-change copy to the exact selected target and validate it with `bash -n`
   or `jq -e .`.
6. Require the original SHA-256, owner, group, and mode.
7. Only in the verified-child branch, during the approved interruption window, terminate that
   freshly re-verified child and require an identity-matching replacement.
8. Initialize a new session and list tools.
9. Require the full post-rollback tool-name list to be byte-identical to the measured original
   baseline.
10. Do not call the six investigation tools after restoring a zero-tool baseline.
11. Recheck firewall/listener state and return `ROLLED_BACK` with redacted evidence.

If safe rollback cannot be completed, stop, preserve the private recovery material on the box, and
escalate `BLOCKED_ROLLBACK`. Do not improvise changes to Origin, E08, E09, venue, or execution
controls.

## 9. What to send back

Send these items back before any further TRIAD work:

1. the redacted evidence archive and SHA-256;
2. final mode and outcome;
3. deployed commit and whether the checkout was clean;
4. exact before/after tool-name lists;
5. six envelope results plus the data-law review;
6. database/ledger/account provenance verdict;
7. pre/post process and firewall verdicts;
8. whether public access remains pairing-blocked; and
9. rollback outcome, or the preserved private rollback-directory location if escalation is required.

Do not send credentials, session IDs, full keeper/config contents, raw diffs, or database/ledger
contents.

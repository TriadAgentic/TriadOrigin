# TRIAD box handoff — investigation MCP only

**Date:** 2026-08-10  
**Scope:** expose and verify the six read-only `investigation` MCP tools  
**Explicit exclusion:** B00R closure, Origin deployment, venue activation, and execution work

## 0. Hard boundary

TriadOrigin remains the deterministic DARK-only E02 edge core. E08 owns authorization and E09
owns execution. This run must not change, export, inspect, or restart:

- `TRIAD_LIVE_ENABLED`, `TRIAD_EXEC_MODE`, arm tokens, or venue credentials;
- Origin, judge, Executor, E08, or E09 configuration or processes;
- order, cancel, flatten, enable, widen, release, or reset paths.

Restart only the verified MCP child under its existing keeper. Do not call `propose_action` or
`record_checkup`; both append data. The six `investigate_*` tools are the only approved read
surface.

B00R is separately blocked by GitHub governance and receipt controls. No box output can substitute
for the real no-bypass ruleset, corrective source merge, signed receipt-only PR, or protected
`B00R_RECEIPT_ANCHOR`.

## 1. Required operator inputs

Do not copy the dated Linux/macOS example paths. Resolve the actual deployed paths and actual
accounts first.

```bash
set -euo pipefail
umask 077

export TRIAD_BOX_LEARNING="<ABSOLUTE_PATH_TO_DEPLOYED_TRIAD_LEARNING>"
export TRIAD_BOX_KEEPER="<ABSOLUTE_PATH_TO_TRIAD_MCP_KEEPER>"
export TRIAD_BOX_CONFIG="<ABSOLUTE_PATH_TO_ACTIVE_MCP_V1_JSON_OR_EMPTY>"
export TRIAD_BOX_BANK="<ABSOLUTE_CANONICAL_SOURCE_PATH_TO_TRIAD_DB>"
export TRIAD_BOX_LEDGER="<ABSOLUTE_CANONICAL_SOURCE_PATH_TO_LEDGER>"
export TRIAD_BOX_ACCOUNTS="<REAL_COMMA_SEPARATED_ACCOUNT_IDS>"
export TRIAD_BOX_PYTHON="<ABSOLUTE_PATH_TO_KEEPER_PYTHON>"
export TRIAD_BOX_KEEPER_PID="<VERIFIED_KEEPER_PID>"
export TRIAD_BOX_CHANGE_TARGET="<keeper|json>"
export TRIAD_BOX_EVIDENCE="$(mktemp -d /tmp/triad-mcp-investigation.XXXXXXXX)"
chmod 700 "$TRIAD_BOX_EVIDENCE"

test -d "$TRIAD_BOX_LEARNING"
test -r "$TRIAD_BOX_LEARNING/src/triad_core/mcp/families/investigation.py"
test -r "$TRIAD_BOX_KEEPER"
test -r "$TRIAD_BOX_BANK"
test -d "$TRIAD_BOX_LEDGER"
test -x "$TRIAD_BOX_PYTHON"
test "$TRIAD_BOX_ACCOUNTS" != "account1,account2,account3"
test -n "$TRIAD_BOX_ACCOUNTS"
case "$TRIAD_BOX_CHANGE_TARGET" in keeper|json) ;; *) exit 2 ;; esac
if test "$TRIAD_BOX_CHANGE_TARGET" = json; then test -r "$TRIAD_BOX_CONFIG"; fi
```

Reject empty, wildcard, whitespace-only, or placeholder account IDs. For each comma-separated ID,
prove the corresponding account exists under the resolved ledger layout. Do not guess the layout;
derive it from the investigation-family reader.

## 2. Capture deployed identity without hashing the live database

A multi-gigabyte live SQLite hash is prohibited: it creates unnecessary I/O and does not represent a
coherent WAL-backed state.

```bash
git -C "$TRIAD_BOX_LEARNING" rev-parse HEAD   | tee "$TRIAD_BOX_EVIDENCE/source-commit.txt"
git -C "$TRIAD_BOX_LEARNING" status --porcelain=v1   | tee "$TRIAD_BOX_EVIDENCE/source-status.txt"

shasum -a 256 "$TRIAD_BOX_KEEPER"   "$TRIAD_BOX_LEARNING/src/triad_core/mcp/server.py"   "$TRIAD_BOX_LEARNING/src/triad_core/mcp/config.py"   "$TRIAD_BOX_LEARNING/src/triad_core/mcp/families/investigation.py"   | tee "$TRIAD_BOX_EVIDENCE/stable-source-sha256.txt"

if test "$TRIAD_BOX_CHANGE_TARGET" = json; then
  shasum -a 256 "$TRIAD_BOX_CONFIG"     | tee "$TRIAD_BOX_EVIDENCE/config-before-sha256.txt"
fi

"$TRIAD_BOX_PYTHON" - "$TRIAD_BOX_BANK" <<'PY'   | tee "$TRIAD_BOX_EVIDENCE/database-metadata.txt"
import os, sqlite3, sys
path = os.path.realpath(sys.argv[1])
print("realpath", path)
for suffix in ("", "-wal", "-shm"):
    candidate = path + suffix
    try:
        st = os.stat(candidate)
    except FileNotFoundError:
        print("absent", candidate)
    else:
        print("stat", candidate, st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
uri = "file:" + path + "?mode=ro"
con = sqlite3.connect(uri, uri=True)
try:
    print("query_only", con.execute("PRAGMA query_only").fetchone()[0])
    print("user_version", con.execute("PRAGMA user_version").fetchone()[0])
    print("schema_version", con.execute("PRAGMA schema_version").fetchone()[0])
    print("tables", con.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table'"
    ).fetchone()[0])
finally:
    con.close()
PY

ps -axo pid=,ppid=,user=,command=   | rg 'triad_mcp_keeper|triad.*mcp'   | tee "$TRIAD_BOX_EVIDENCE/processes-before.txt"
lsof -nP -iTCP:8801 -sTCP:LISTEN   | tee "$TRIAD_BOX_EVIDENCE/listener-before.txt"
```

The deployed checkout must be clean or its exact dirty diff must be separately reviewed. Confirm the
keeper command uses `TRIAD_BOX_PYTHON`, then prove that interpreter imports the intended modules:

```bash
"$TRIAD_BOX_PYTHON" - <<'PY'   | tee "$TRIAD_BOX_EVIDENCE/import-paths.txt"
import triad_core.mcp.server
import triad_core.mcp.config
import triad_core.mcp.families.investigation
for module in (
    triad_core.mcp.server,
    triad_core.mcp.config,
    triad_core.mcp.families.investigation,
):
    print(module.__name__, module.__file__)
PY
```

Every imported path must resolve to the reviewed deployment or to a separately pinned installed
artifact. A test checkout that the keeper does not import is not deployment parity.

## 3. Verify service identity and read access

```bash
test -n "$TRIAD_BOX_KEEPER_PID"
kill -0 "$TRIAD_BOX_KEEPER_PID"

TRIAD_BOX_KEEPER_ROW="$(
  ps -p "$TRIAD_BOX_KEEPER_PID" -o pid=,ppid=,user=,command=
)"
printf '%s\n' "$TRIAD_BOX_KEEPER_ROW"   | tee "$TRIAD_BOX_EVIDENCE/keeper-identity.txt"
printf '%s\n' "$TRIAD_BOX_KEEPER_ROW" | rg -F "$TRIAD_BOX_KEEPER"

TRIAD_BOX_SERVICE_USER="$(
  ps -p "$TRIAD_BOX_KEEPER_PID" -o user= | tr -d ' '
)"
test -n "$TRIAD_BOX_SERVICE_USER"

TRIAD_BOX_OLD_PID="$(
  lsof -nP -tiTCP:8801 -sTCP:LISTEN | sort -u
)"
test -n "$TRIAD_BOX_OLD_PID"
test "$(printf '%s\n' "$TRIAD_BOX_OLD_PID" | wc -l | tr -d ' ')" = "1"

TRIAD_BOX_CHILD_PPID="$(
  ps -p "$TRIAD_BOX_OLD_PID" -o ppid= | tr -d ' '
)"
TRIAD_BOX_CHILD_USER="$(
  ps -p "$TRIAD_BOX_OLD_PID" -o user= | tr -d ' '
)"
TRIAD_BOX_CHILD_CMD="$(
  ps -p "$TRIAD_BOX_OLD_PID" -o command=
)"
test "$TRIAD_BOX_CHILD_PPID" = "$TRIAD_BOX_KEEPER_PID"
test "$TRIAD_BOX_CHILD_USER" = "$TRIAD_BOX_SERVICE_USER"
printf '%s\n' "$TRIAD_BOX_CHILD_CMD" | rg -F "$TRIAD_BOX_PYTHON"
printf '%s\n' "$TRIAD_BOX_CHILD_CMD" | rg 'triad.*mcp'

sudo -n -u "$TRIAD_BOX_SERVICE_USER" test -r "$TRIAD_BOX_BANK"
sudo -n -u "$TRIAD_BOX_SERVICE_USER" test -r "$TRIAD_BOX_LEDGER"
```

If passwordless identity switching is unavailable, obtain an equivalent operator-approved proof.
Do not continue merely because the interactive operator can read paths the service cannot.

## 4. Run the isolated family test

Do not install dependencies or run unreviewed integration/live tests on production.

```bash
"$TRIAD_BOX_PYTHON" -m pytest   "$TRIAD_BOX_LEARNING/tests/mcp/test_investigation_family.py" -q   2>&1 | tee "$TRIAD_BOX_EVIDENCE/investigation-tests.txt"
```

All nine documented investigation tests must pass. The full MCP suite is not a box acceptance gate;
the books conflict on counts and document two pre-existing failures. Reproduce the full suite on a
clean non-production runner at the identical commit instead.

## 5. MCP response normalizer

This handles plain JSON and streamable-HTTP SSE. It writes only normalized JSON.

```bash
normalize_mcp_body() {
  "$TRIAD_BOX_PYTHON" - "$1" "$2" <<'PY'
import json, pathlib, sys
src, dst = map(pathlib.Path, sys.argv[1:3])
text = src.read_text(encoding="utf-8")
frames = [
    line[5:].strip()
    for line in text.splitlines()
    if line.startswith("data:")
]
payload = frames[-1] if frames else text.strip()
obj = json.loads(payload)
dst.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY
}

mcp_initialize() {
  TRIAD_BOX_LABEL="$1"
  curl -sS     -D "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.headers.private"     -o "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.body.raw"     -X POST http://127.0.0.1:8801/mcp     -H 'Content-Type: application/json'     -H 'Accept: application/json, text/event-stream'     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"triad-box-audit","version":"1.0"}}}'
  chmod 600 "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.headers.private"
  TRIAD_BOX_SESSION_ID="$(
    awk 'tolower($1)=="mcp-session-id:" {print $2}'       "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.headers.private" | tr -d '\r'
  )"
  test -n "$TRIAD_BOX_SESSION_ID"
  normalize_mcp_body     "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.body.raw"     "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.json"
}

mcp_post() {
  TRIAD_BOX_LABEL="$1"
  TRIAD_BOX_PAYLOAD="$2"
  curl -sS     -o "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.body.raw"     -X POST http://127.0.0.1:8801/mcp     -H 'Content-Type: application/json'     -H 'Accept: application/json, text/event-stream'     -H "Mcp-Session-Id: $TRIAD_BOX_SESSION_ID"     -d "$TRIAD_BOX_PAYLOAD"
  normalize_mcp_body     "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.body.raw"     "$TRIAD_BOX_EVIDENCE/$TRIAD_BOX_LABEL.json"
}
```

Keep `TRIAD_BOX_SESSION_ID` shell-local; never export it. Before packaging evidence, redact or
delete every `*.headers.private` and raw response that might contain session material.

## 6. Measure the baseline and choose the idempotent path

```bash
mcp_initialize "init-before"
mcp_post "tools-before"   '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

"$TRIAD_BOX_PYTHON" - "$TRIAD_BOX_EVIDENCE/tools-before.json"   "$TRIAD_BOX_EVIDENCE/tools-before.names" <<'PY'
import json, pathlib, sys
doc = json.loads(pathlib.Path(sys.argv[1]).read_text())
tools = doc.get("result", {}).get("tools")
if not isinstance(tools, list):
    raise SystemExit("tools/list result missing")
names = sorted(item["name"] for item in tools if isinstance(item, dict))
pathlib.Path(sys.argv[2]).write_text("\n".join(names) + "\n")
print("tool_count", len(names))
print("investigation", [name for name in names if name.startswith("investigate_")])
PY

rg '^investigate_' "$TRIAD_BOX_EVIDENCE/tools-before.names"   > "$TRIAD_BOX_EVIDENCE/investigation-before.names" || true
```

Canonical set:

```text
investigate_contract_integrity
investigate_death_causes
investigate_estate_provenance
investigate_money_population
investigate_populations
investigate_symbol_funnel
```

Decision:

- zero `investigate_*`: activation path;
- exactly the canonical six: verification-only path; do not edit or restart;
- any partial or different set: stop as deployment drift.

The dated 142/148 counts are observations, not forced thresholds.

## 7. Activation path — one selected config target only

Skip this section entirely for verification-only mode.

Resolve configuration precedence from `config.py` and the keeper. Set
`TRIAD_BOX_CHANGE_TARGET` to the one file that actually controls the child.

```bash
if test "$TRIAD_BOX_CHANGE_TARGET" = keeper; then
  TRIAD_BOX_SELECTED_TARGET="$TRIAD_BOX_KEEPER"
else
  TRIAD_BOX_SELECTED_TARGET="$TRIAD_BOX_CONFIG"
fi

test -f "$TRIAD_BOX_SELECTED_TARGET"
cp -p "$TRIAD_BOX_SELECTED_TARGET"   "$TRIAD_BOX_EVIDENCE/change-target.before"
shasum -a 256 "$TRIAD_BOX_SELECTED_TARGET"   | tee "$TRIAD_BOX_EVIDENCE/change-target.before.sha256"
ls -lO "$TRIAD_BOX_SELECTED_TARGET"   | tee "$TRIAD_BOX_EVIDENCE/change-target.before.mode"
```

Now edit only that selected target. Required effective values:

```text
TRIAD_MCP_INVESTIGATION_FAMILY_ENABLED=1
TRIAD_MCP_INVESTIGATION_BANK_PATH=<canonical source database>
TRIAD_MCP_INVESTIGATION_LEDGER_ROOT=<canonical source ledger>
TRIAD_MCP_INVESTIGATION_ACCOUNTS=<real account IDs; exact key must be proven from config.py>
```

For JSON mode, use the exact proven JSON keys instead of adding environment names to JSON.

After the edit:

```bash
if test "$TRIAD_BOX_CHANGE_TARGET" = keeper; then
  bash -n "$TRIAD_BOX_SELECTED_TARGET"
else
  jq -e . "$TRIAD_BOX_SELECTED_TARGET" > /dev/null
fi

diff -u "$TRIAD_BOX_EVIDENCE/change-target.before" "$TRIAD_BOX_SELECTED_TARGET"   | tee "$TRIAD_BOX_EVIDENCE/change-target.diff"
shasum -a 256 "$TRIAD_BOX_SELECTED_TARGET"   | tee "$TRIAD_BOX_EVIDENCE/change-target.after.sha256"
ls -lO "$TRIAD_BOX_SELECTED_TARGET"   | tee "$TRIAD_BOX_EVIDENCE/change-target.after.mode"
```

The diff may contain only investigation-family configuration. Any Origin, live-mode, arm-token,
venue, credential, or execution change is a hard stop.

## 8. Restart the verified child during an approved interruption window

Existing MCP clients will be disconnected. Obtain and record the interruption window before this
step.

```bash
kill -0 "$TRIAD_BOX_KEEPER_PID"
kill -TERM "$TRIAD_BOX_OLD_PID"

TRIAD_BOX_NEW_PID=""
for TRIAD_BOX_ATTEMPT in $(seq 1 15); do
  TRIAD_BOX_CANDIDATES="$(
    lsof -nP -tiTCP:8801 -sTCP:LISTEN 2>/dev/null | sort -u || true
  )"
  if test -n "$TRIAD_BOX_CANDIDATES" &&
     test "$(printf '%s\n' "$TRIAD_BOX_CANDIDATES" | wc -l | tr -d ' ')" = "1" &&
     test "$TRIAD_BOX_CANDIDATES" != "$TRIAD_BOX_OLD_PID"; then
    TRIAD_BOX_NEW_PID="$TRIAD_BOX_CANDIDATES"
    break
  fi
  sleep 1
done

test -n "$TRIAD_BOX_NEW_PID"
kill -0 "$TRIAD_BOX_KEEPER_PID"
test "$(ps -p "$TRIAD_BOX_NEW_PID" -o ppid= | tr -d ' ')" = "$TRIAD_BOX_KEEPER_PID"
test "$(ps -p "$TRIAD_BOX_NEW_PID" -o user= | tr -d ' ')" = "$TRIAD_BOX_SERVICE_USER"
TRIAD_BOX_NEW_CMD="$(ps -p "$TRIAD_BOX_NEW_PID" -o command=)"
printf '%s\n' "$TRIAD_BOX_NEW_CMD" | rg -F "$TRIAD_BOX_PYTHON"
printf '%s\n' "$TRIAD_BOX_NEW_CMD" | rg 'triad.*mcp'
ps -p "$TRIAD_BOX_NEW_PID" -o pid=,ppid=,user=,lstart=,command=   | tee "$TRIAD_BOX_EVIDENCE/process-after.txt"
```

## 9. Post-restart surface and exact delta

Open a new session; never reuse the pre-restart session.

```bash
TRIAD_BOX_SESSION_ID=""
mcp_initialize "init-after"
mcp_post "tools-after"   '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

"$TRIAD_BOX_PYTHON" - "$TRIAD_BOX_EVIDENCE/tools-after.json"   "$TRIAD_BOX_EVIDENCE/tools-after.names" <<'PY'
import json, pathlib, sys
doc = json.loads(pathlib.Path(sys.argv[1]).read_text())
tools = doc.get("result", {}).get("tools")
if not isinstance(tools, list):
    raise SystemExit("tools/list result missing")
names = sorted(item["name"] for item in tools if isinstance(item, dict))
pathlib.Path(sys.argv[2]).write_text("\n".join(names) + "\n")
print("tool_count", len(names))
PY

comm -13 "$TRIAD_BOX_EVIDENCE/tools-before.names"   "$TRIAD_BOX_EVIDENCE/tools-after.names"   | tee "$TRIAD_BOX_EVIDENCE/tools-added.names"
comm -23 "$TRIAD_BOX_EVIDENCE/tools-before.names"   "$TRIAD_BOX_EVIDENCE/tools-after.names"   | tee "$TRIAD_BOX_EVIDENCE/tools-removed.names"
```

Activation acceptance requires zero removals and exactly the canonical six additions. In
verification-only mode, require zero additions/removals and exactly the canonical six already
present.

## 10. Functional calls

Call provenance first and each heavy tool once.

```bash
mcp_post "call-estate-provenance"   '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"investigate_estate_provenance","arguments":{}}}'
mcp_post "call-contract-integrity"   '{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"investigate_contract_integrity","arguments":{}}}'
mcp_post "call-populations"   '{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"investigate_populations","arguments":{}}}'
mcp_post "call-money-population"   '{"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"investigate_money_population","arguments":{}}}'
mcp_post "call-symbol-funnel"   '{"jsonrpc":"2.0","id":14,"method":"tools/call","params":{"name":"investigate_symbol_funnel","arguments":{}}}'
mcp_post "call-death-causes"   '{"jsonrpc":"2.0","id":15,"method":"tools/call","params":{"name":"investigate_death_causes","arguments":{}}}'

"$TRIAD_BOX_PYTHON" - "$TRIAD_BOX_EVIDENCE" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
files = sorted(root.glob("call-*.json"))
if len(files) != 6:
    raise SystemExit("expected six normalized call responses")
for path in files:
    rpc = json.loads(path.read_text())
    if "error" in rpc:
        raise SystemExit(f"{path.name}: JSON-RPC error: {rpc['error']}")
    content = rpc.get("result", {}).get("content")
    if not isinstance(content, list):
        raise SystemExit(f"{path.name}: missing MCP result.content")
    texts = [item.get("text") for item in content if item.get("type") == "text"]
    envelopes = []
    for value in texts:
        try:
            candidate = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(candidate, dict) and "ok" in candidate:
            envelopes.append(candidate)
    if len(envelopes) != 1:
        raise SystemExit(f"{path.name}: expected exactly one tool envelope")
    envelope = envelopes[0]
    (root / path.name.replace(".json", ".envelope.json")).write_text(
        json.dumps(envelope, sort_keys=True, indent=2) + "\n"
    )
    if envelope.get("ok") is not True:
        raise SystemExit(f"{path.name}: functional verification incomplete: {envelope}")
    print(path.name, "ok:true")
PY
```

Functional acceptance requires all six calls to complete with `ok:true`.
`DISJOINT` or `CONTAMINATED` is a data verdict, not a transport failure.
`NOT_MEASURABLE` and `UNRESOLVED_SYMBOL` may be valid data results. Any `unavailable`,
`tool_timeout`, or `not_implemented` leaves functional verification incomplete.

Data-law acceptance:

- provenance identifies resolved database/ledger paths and source versus mirror;
- every result names SHADOW or MONEY and never blends them;
- while `side`/`role` is absent, WR, EV, MFE, MAE, and capture remain
  `NOT_MEASURABLE` under F-004;
- when `symbol` is absent, it may be recovered only by the documented
  `intent_id → live_intents` join; a failed join returns `UNRESOLVED_SYMBOL` under F-011;
- dated August 7 counts are reference observations, not current thresholds.

## 11. Listener/firewall and public-auth evidence

`lsof` proves the bind address, not network restriction. On the documented MacStudio, capture:

```bash
/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate   | tee "$TRIAD_BOX_EVIDENCE/application-firewall.txt"
sudo -n pfctl -sr   | tee "$TRIAD_BOX_EVIDENCE/pf-rules.txt"
netstat -anv -p tcp | rg '[.:]8801'   | tee "$TRIAD_BOX_EVIDENCE/listener-network.txt"
```

If these do not prove that unauthenticated `0.0.0.0:8801` is restricted to the intended trust
boundary, record `BLOCKED_FIREWALL_EVIDENCE` and do not claim LAN safety.

Successful loopback verification does not establish remote access. The supplied contract documents
Cloudflare device pairing for public MCP; it does not document query-token authentication. If
pairing remains prohibited, remote access remains blocked.

## 12. Evidence return

Return a redacted archive containing the UTC transcript, host/source identity, stable hashes,
selected-target before/after hashes and diff, test result, process/listener evidence, measured tool
lists and delta, all six normalized tool envelopes, provenance verdict, and firewall evidence.

Before packaging:

```bash
find "$TRIAD_BOX_EVIDENCE" -name '*.headers.private' -delete
```

Do not include tokens, API keys, cookies, pairing codes, full environment dumps, private keys,
signing seeds, or session IDs.

## 13. Symmetric rollback

For activation-mode failure only:

1. re-verify keeper and current child PID/PPID/user/command;
2. restore `change-target.before` to the exact selected target with preserved owner/mode;
3. validate with `bash -n` or `jq -e`;
4. verify the restored SHA-256 and owner/mode match the pre-change evidence;
5. terminate only the re-verified MCP child during the approved interruption window;
6. verify the keeper respawns an identity-matching child;
7. repeat Sections 9–10; and
8. require the measured original baseline, not an assumed 142-tool/zero-family state.

Do not modify Origin, E08, E09, venue, or execution controls during rollback.

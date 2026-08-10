# TRIAD box handoff — investigation MCP only

**Date:** 2026-08-10  
**Scope:** expose and verify the six read-only `investigation` MCP tools  
**Explicit exclusion:** this is not B00R closure, Origin deployment, venue activation, or execution work

## 0. Hard boundary

TriadOrigin remains the deterministic DARK-only E02 edge core. E08 owns authorization and E09
owns execution. This run must not change, export, or inspect:

- `TRIAD_LIVE_ENABLED`, `TRIAD_EXEC_MODE`, any arm token, or venue credentials;
- Origin, judge, Executor, E08, or E09 configuration or processes;
- production order, cancel, flatten, enable, widen, release, or reset paths.

Restart only the verified MCP child. Do not call `propose_action` or `record_checkup`; both append
data despite the server's read-only headline. The six `investigate_*` tools are the approved
read-only scope.

B00R is still blocked by GitHub governance and receipt controls. No box output can substitute for
the real no-bypass ruleset, corrective source merge, signed receipt-only PR, or protected
`B00R_RECEIPT_ANCHOR`.

## 1. Resolve real paths and interpreter

Do not copy the dated Linux/macOS examples blindly. Resolve the canonical source database and ledger,
not an unexplained mirror.

```bash
set -euo pipefail

export TRIAD_BOX_LEARNING="<ABSOLUTE_PATH_TO_TRIAD_LEARNING>"
export TRIAD_BOX_KEEPER="<ABSOLUTE_PATH_TO_TRIAD_MCP_KEEPER>"
export TRIAD_BOX_BANK="<ABSOLUTE_CANONICAL_SOURCE_PATH_TO_TRIAD_DB>"
export TRIAD_BOX_LEDGER="<ABSOLUTE_CANONICAL_SOURCE_PATH_TO_LEDGER>"
export TRIAD_BOX_ACCOUNTS="account1,account2,account3"
export TRIAD_BOX_PYTHON="<ABSOLUTE_PATH_TO_KEEPER_PYTHON>"
export TRIAD_BOX_EVIDENCE="$(mktemp -d /tmp/triad-mcp-investigation.XXXXXXXX)"
chmod 700 "$TRIAD_BOX_EVIDENCE"

test -r "$TRIAD_BOX_LEARNING/src/triad_core/mcp/families/investigation.py"
test -r "$TRIAD_BOX_KEEPER"
test -r "$TRIAD_BOX_BANK"
test -d "$TRIAD_BOX_LEDGER"
test -x "$TRIAD_BOX_PYTHON"

git -C "$TRIAD_BOX_LEARNING" rev-parse HEAD   | tee "$TRIAD_BOX_EVIDENCE/source-commit.txt"
git -C "$TRIAD_BOX_LEARNING" status --porcelain=v1   | tee "$TRIAD_BOX_EVIDENCE/source-status.txt"

shasum -a 256 "$TRIAD_BOX_KEEPER" "$TRIAD_BOX_BANK"   | tee "$TRIAD_BOX_EVIDENCE/prechange-sha256.txt"

rg -n 'investigation_(family_enabled|bank_path|ledger_root|accounts)|TRIAD_MCP_INVESTIGATION'   "$TRIAD_BOX_LEARNING/src/triad_core/mcp/config.py"   "$TRIAD_BOX_KEEPER"   | tee "$TRIAD_BOX_EVIDENCE/config-mapping.txt"

pgrep -af 'triad_mcp_keeper|triad.*mcp'   | tee "$TRIAD_BOX_EVIDENCE/processes-before.txt"
lsof -nP -iTCP:8801 -sTCP:LISTEN   | tee "$TRIAD_BOX_EVIDENCE/listener-before.txt"
```

Stop if any of these is true:

- source versus mirror authority is unresolved;
- the deployed source is unexpectedly dirty;
- the interpreter, keeper, or port owner is ambiguous;
- the effective accounts environment name or config precedence cannot be proven from source;
- port 8801 is not owned by the expected MCP child;
- an unauthenticated `0.0.0.0:8801` listener is not firewall-restricted.

## 2. Reproduce the tests before changing configuration

```bash
"$TRIAD_BOX_PYTHON" -m pytest   "$TRIAD_BOX_LEARNING/tests/mcp/test_investigation_family.py" -q   | tee "$TRIAD_BOX_EVIDENCE/investigation-tests.txt"

"$TRIAD_BOX_PYTHON" -m pytest   "$TRIAD_BOX_LEARNING/tests/mcp" -q   | tee "$TRIAD_BOX_EVIDENCE/mcp-tests.txt"
```

The focused family must pass all nine documented tests. Record the actual full-suite count; the
supplied books conflict between 337, 473, and 471+2+6 and therefore are not acceptance evidence.

## 3. Capture the gate-off baseline over loopback

The box must use loopback. Do not put a public token in the URL, shell history, proxy, or evidence.

```bash
curl -sS -D "$TRIAD_BOX_EVIDENCE/init-before.headers"   -o "$TRIAD_BOX_EVIDENCE/init-before.body"   -X POST http://127.0.0.1:8801/mcp   -H 'Content-Type: application/json'   -H 'Accept: application/json, text/event-stream'   -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"triad-box-audit","version":"1.0"}}}'

export TRIAD_BOX_SESSION="$(
  awk 'tolower($1)=="mcp-session-id:" {print $2}'     "$TRIAD_BOX_EVIDENCE/init-before.headers" | tr -d '\r'
)"
test -n "$TRIAD_BOX_SESSION"

curl -sS -o "$TRIAD_BOX_EVIDENCE/tools-before.body"   -X POST http://127.0.0.1:8801/mcp   -H 'Content-Type: application/json'   -H 'Accept: application/json, text/event-stream'   -H "Mcp-Session-Id: $TRIAD_BOX_SESSION"   -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

Parse plain JSON or the final SSE `data:` frame. The dated baseline is 142 tools with zero
`investigate_*`; record the measured current baseline rather than forcing that historical count.

## 4. Enable only the investigation family

First prove whether the keeper reads environment variables or `configs/mcp.v1.json`, and prove
precedence. Use exactly one mechanism.

Required effective values:

```text
TRIAD_MCP_INVESTIGATION_FAMILY_ENABLED=1
TRIAD_MCP_INVESTIGATION_BANK_PATH=<canonical source database>
TRIAD_MCP_INVESTIGATION_LEDGER_ROOT=<canonical source ledger>
```

Set the accounts value using the exact environment name found in `config.py`. The supplied docs
guarantee only the JSON key:

```json
"investigation_accounts": "account1,account2,account3"
```

Before restart:

```bash
cp -p "$TRIAD_BOX_KEEPER" "$TRIAD_BOX_EVIDENCE/triad_mcp_keeper.sh.before"
bash -n "$TRIAD_BOX_KEEPER"

diff -u "$TRIAD_BOX_EVIDENCE/triad_mcp_keeper.sh.before" "$TRIAD_BOX_KEEPER"   | tee "$TRIAD_BOX_EVIDENCE/keeper.diff"
```

The diff may contain only the investigation MCP configuration. Any Origin, live-mode, arm-token,
venue, credential, or execution change is a hard stop.

## 5. Restart only the verified MCP child

The keeper is documented to respawn its child within ten seconds. Do not terminate the keeper.

```bash
export TRIAD_BOX_OLD_PID="$(
  lsof -nP -tiTCP:8801 -sTCP:LISTEN | sort -u
)"
test "$(printf '%s\n' "$TRIAD_BOX_OLD_PID" | wc -l | tr -d ' ')" = "1"

export TRIAD_BOX_OLD_CMD="$(ps -p "$TRIAD_BOX_OLD_PID" -o command=)"
case "$TRIAD_BOX_OLD_CMD" in
  *triad*mcp*) ;;
  *) echo "STOP: port 8801 owner is not verified TRIAD MCP"; exit 1 ;;
esac

kill -TERM "$TRIAD_BOX_OLD_PID"

for TRIAD_BOX_ATTEMPT in $(seq 1 15); do
  TRIAD_BOX_NEW_PID="$(
    lsof -nP -tiTCP:8801 -sTCP:LISTEN 2>/dev/null | sort -u || true
  )"
  if test -n "$TRIAD_BOX_NEW_PID" &&
     test "$TRIAD_BOX_NEW_PID" != "$TRIAD_BOX_OLD_PID"; then
    break
  fi
  sleep 1
done

test -n "${TRIAD_BOX_NEW_PID:-}"
test "$TRIAD_BOX_NEW_PID" != "$TRIAD_BOX_OLD_PID"
ps -p "$TRIAD_BOX_NEW_PID" -o pid,lstart,command   | tee "$TRIAD_BOX_EVIDENCE/process-after.txt"
```

## 6. Post-restart acceptance

Initialize a new session and list tools again. Require exactly six additions and no removals or
unrelated additions:

```text
investigate_populations
investigate_money_population
investigate_symbol_funnel
investigate_death_causes
investigate_contract_integrity
investigate_estate_provenance
```

Call provenance first, then the remaining tools one at a time:

```json
{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"investigate_estate_provenance","arguments":{}}}
{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"investigate_contract_integrity","arguments":{}}}
{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"investigate_populations","arguments":{}}}
{"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"investigate_money_population","arguments":{}}}
{"jsonrpc":"2.0","id":14,"method":"tools/call","params":{"name":"investigate_symbol_funnel","arguments":{}}}
{"jsonrpc":"2.0","id":15,"method":"tools/call","params":{"name":"investigate_death_causes","arguments":{}}}
```

Acceptance law:

- provenance names the resolved database and ledger and distinguishes source from mirror;
- every result explicitly names SHADOW or MONEY and never blends them;
- missing input returns `unavailable`, never zero;
- unresolved instruments remain `UNRESOLVED_SYMBOL`, never guessed;
- while `fill.v1` lacks `side`/`role` or `symbol`, WR, EV, MFE, MAE, and capture remain
  `NOT_MEASURABLE`, never estimated;
- heavy calls are not looped: budget 30/minute, timeout 30 seconds;
- dated August 7 values are reference observations, not current thresholds;
- `CONTAMINATED` is escalated as a finding, not hidden;
- `unavailable`, `tool_timeout`, and `not_implemented` remain distinct outcomes.

## 7. Evidence return bundle

Return a redacted archive containing:

- UTC transcript and host identity;
- source commit and clean/dirty status;
- server version and protocol;
- keeper/config hashes and exact diff;
- focused and full MCP test logs;
- process/listener evidence before and after;
- baseline and post-change tool lists;
- all six raw MCP responses;
- provenance verdict and resolved paths;
- firewall/listener evidence for any unauthenticated LAN binding;
- explicit confirmation that no Origin/E08/E09/execution process or config was touched.

Never include tokens, API keys, secrets, cookies, pairing codes, full environment dumps, private keys,
or signing seeds.

## 8. Rollback

If the six-tool delta, provenance, tests, or restart checks fail:

1. restore the keeper/config from the captured pre-change copy;
2. syntax-check it;
3. terminate only the re-verified MCP child;
4. confirm the keeper respawns it; and
5. confirm the tool surface returns to the measured baseline with zero `investigate_*`.

Do not modify Origin, E08, E09, venue, or execution controls as part of rollback.

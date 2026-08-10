# Superseded: B00R is not an on-box procedure

Do **not** execute the former contents of this file. That snapshot used stale PR/SHA identities and
an obsolete receipt layout, and it incorrectly placed repository-authority work on the trading/MCP
host.

B00R requires no trading-box, execution-host, database, venue, or MCP credentials. Its residual work
belongs to GitHub repository administration, separated signing workstations, and an ephemeral clean
runner. Use:

`docs/governance/B00R_EXTERNAL_AUTHORITY_AND_CLEAN_RUNNER_HANDOFF.md`

That guide is authoritative for the protected pins, real Ed25519 authority ceremony, write-authorized
ruleset captures, exact-head CI/review/merge, canonical bare receipt, and protected annotated anchor.
The implemented tag validator does not claim cryptographic tag-signature verification.

Actual investigation-MCP host deployment and runtime verification are a separate operational task
and must use the separately delivered MCP residual on-box guide. Neither task authorizes trading,
paper execution, venue activation, or executor activation. Maintain `DENIED_SAFE_HOLD` and
OFF/OFF/OFF/LIVE throughout.

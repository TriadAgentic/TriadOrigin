# Package Validation Record

## Scope and cut-off

- Validation date: 2026-08-09
- GitHub refresh cut-off: 2026-08-09T12:33:04Z
- Repository: `TriadAgentic/TriadOrigin`
- Current observed `main`: `2cebc1391d65028a2a7de200d2e3fb9f82369872`
- Governance posture: `DENIED_SAFE_HOLD`
- This package is a repository repair/audit procedure. It is not a G0–G9 gate receipt, estate certification, runtime attestation, or activation authorization.

At the cut-off, branch-governance issue #5 remained open. B07 PR #24 had merged as `2cebc1391d65028a2a7de200d2e3fb9f82369872` from final head `7a51bf62305ad87b61784b334a17212916806dbc` on invalid B06 receipt base `b8dc8ba514eb3d5b7f9e3d9c3b49169b58cd1b07`. It is classified `BUILT_ON_INVALID_ANCESTRY` and receives no grandfathered receipt. B07 receipt PR #25 was open at head `84c98d9b61528d96dc9efa2a8560bb42bf193e76` against that invalid subject; its automated review bound earlier head `04a0c6b5bb…` and CI remained in progress. It is preserved only as an invalid-subject receipt attempt.

## Frozen source checks

- Documents 01–05: exact-hash residual review clean after receipt, timing/durability, blocker-register, and contract-ownership corrections.
- Documents 06–10: exact-hash residual review clean after route-containment, governance, status-enum, PR #24 chronology, and forward-repair corrections.
- Markdown conflict-marker and balanced-code-fence scans: clean.
- Invented combined runtime token `NOT_ATTESTED/UNAVAILABLE`: absent; `NOT_ATTESTED` and `UNAVAILABLE` remain distinct statuses.

## Audit runner verification

- File: `triad_origin_b01_b10_audit.py`
- Version: `1.2.0`
- Frozen SHA-256: `12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2`
- `python3 -m py_compile triad_origin_b01_b10_audit.py`: PASS
- `python3 triad_origin_b01_b10_audit.py --self-test`: `63/63 passed`
- Independent final-hardening review closed two last P1 paths: an exact-equivalent governance procedure cannot mask an actual bypass, and legacy `merge_contains_head=true` cannot replace structured ancestry/squash proof.

## Representative fail-closed run

A deliberately incomplete, clean Git fixture was audited in local B01 mode against externally pinned head `faaa36c5c68095231983542d4f3aa927e41ec527` with explicit repository-code execution consent.

Observed result:

- process exit: `1`
- status: `HARD_GATE_FAIL`
- hard gate: `FAIL`
- `repository_safe_hold_eligible=false`
- `receipt_profile_decision_pin_valid=false`
- `estate_certification_eligible=false`
- JUnit: 11 tests, 10 failures, 0 errors, 0 skipped
- generated report `SHA256SUMS`: all entries verified
- report bundle included content-addressed input preimages and did not set a tool error

This is the expected result for incomplete evidence. The numeric completion score did not override the hard gate.

## Operational limitations

- Mandatory repository commands are consented host processes, not a security sandbox. Run untrusted repository code in an external container or VM with read-only source, disabled network, disposable writable output, and CPU/memory/process/file-size limits.
- POSIX process-group cleanup cannot stop a descendant that deliberately creates a new session; non-POSIX descendant cleanup is best-effort.
- Live GitHub bypass/no-bypass evidence remains fail-closed without signed governance evidence. Strict rule matching and same-base exact-tree squash proof may false-red complex valid cases rather than guessing.
- Repository/provider future-time tolerance is zero and the receipt-profile decision vocabulary is closed. A differently ratified profile requires a reviewed runner update.
- No live GitHub/network execution fixture was run in this workspace; signed offline GitHub behavior and tamper cases are covered by the embedded suite.

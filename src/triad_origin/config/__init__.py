"""ORIGIN signed configuration (B07 — the activation-facing materialization gate).

Every module here reads immutable governance artifacts (the RC3 effective control bundle's
192-row parameters table, the RC4 four-plane control bundle) and materializes them into a
digest-identified, fail-closed registry. This is a **stricter** gate than the code-level
``DECLARED_*`` rule-string constants B03–B06 already consume directly (writing offline code
against a declared rule string is always permitted — ``AUTHORIZED_OFFLINE_IMPLEMENTATION_ONLY``):
:mod:`triad_origin.config.parameters` additionally refuses to hand back a value for any parameter
whose *governance status* is not yet ratified/current, mirroring this repository's
``DENIED_SAFE_HOLD`` activation posture at the configuration layer itself. Nothing here reads a
clock, opens a socket, or holds a credential.
"""

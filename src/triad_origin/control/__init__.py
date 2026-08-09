"""ORIGIN four-plane control substrate (B05 — RC4 lever/shadow/paper law).

Every module here implements the RC4 Four-Plane/Lever addendum's *substrate*: the exact lever
enums, the 35 invalid aliases, the 10 valid combinations, the 32 refusal codes with their
containment (``minimum_action``) resolution, the append-only runtime lever registry, the durable
SHADOW outbox/health law, and the keyless PAPER virtual ledger. :mod:`triad_origin.control.lever_law`
is the shared, dependency-free classifier every other module here imports; nothing here reads a
system clock, opens a socket, or holds a venue credential (Doc 04 §04.17 DARK posture).
"""

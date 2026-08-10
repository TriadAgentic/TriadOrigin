"""ORIGIN read-face evidence surfaces (B08 — RC3 W25 / RC4 §L6 read-only projections).

This package is the honest, read-only evidence layer: the six RC4 §L6 read faces
(``get_engine_lever_registry``, ``get_engine_lever_attestation``, ``get_engine_lever_history``,
``get_shadow_health``, ``get_four_plane_status``, ``get_engine_inventory_reconciliation``) and the
ONE shared :mod:`triad_origin.read_faces.envelope` shape they all return. Every face is a pure
projection of already-computed substrate state — it never mutates state, arms, activates, switches,
or reaches a venue/credential/order/money path; a face that cannot compute a fact returns an honest
``UNAVAILABLE``/``NOT_MEASURABLE`` envelope, never a fabricated zero (RC3 W25 "no empty green").
Nothing here reads a system clock, opens a socket, or holds a credential (Doc 04 §04.17 DARK
posture); every 'current' fact is caller-supplied.
"""

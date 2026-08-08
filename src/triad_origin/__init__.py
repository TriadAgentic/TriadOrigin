"""TRIAD ORIGIN V7 — Deterministic Causal Edge Core.

Node ``E02-V7`` / service ``triad-origin-e02`` / namespace ``triad.origin.v7``.

This package is the clean-room deterministic E02 replacement. It ships **DARK**: no venue
credentials, no order verbs, no money authority. It publishes only structures, candidates,
checkpoints, quarantine records, evidence and metrics.

The runtime is stdlib-only by design (deterministic, self-contained CI).
"""

from __future__ import annotations

# --- Immutable identity constants (Doc 00 §00.2) -------------------------------------------------
PRODUCT_NAME = "TRIAD ORIGIN V7"
DESCRIPTIVE_NAME = "Deterministic Causal Edge Core"
SPEC_VERSION = "1.0.0-RC1"
PACKAGE_VERSION = "7.0.0rc1"

SERVICE_ID = "triad-origin-e02"
TOPOLOGY_NODE = "E02-V7"
NAMESPACE = "triad.origin.v7"
SHORTHAND = "ORIGIN"

# --- Constitutional posture (Doc 00, Doc 04) -----------------------------------------------------
# A healthy deployed process holds no money authority. Authority is a scoped producer lease.
POSTURE = "DARK"  # DARK | READY_NO_AUTHORITY are the only postures this package can hold.
ALLOW_MONEY_PUBLISH = False  # Enforced by capability/ACL, not merely this boolean (Doc 09 §09.4).

# The three modes are a promotion ladder, not a venue switch (Doc 00 ADR-005).
MODES = ("shadow", "paper", "live")

__all__ = [
    "PRODUCT_NAME",
    "DESCRIPTIVE_NAME",
    "SPEC_VERSION",
    "PACKAGE_VERSION",
    "SERVICE_ID",
    "TOPOLOGY_NODE",
    "NAMESPACE",
    "SHORTHAND",
    "POSTURE",
    "ALLOW_MONEY_PUBLISH",
    "MODES",
]

"""Package posture: ORIGIN ships DARK with no money authority (Doc 00, Doc 04)."""

from __future__ import annotations

import triad_origin as origin


def test_identity_constants():
    assert origin.SERVICE_ID == "triad-origin-e02"
    assert origin.TOPOLOGY_NODE == "E02-V7"
    assert origin.NAMESPACE == "triad.origin.v7"
    assert origin.SPEC_VERSION == "1.0.0-RC1"
    assert origin.PACKAGE_VERSION == "7.0.0rc1.post1"


def test_dark_posture():
    assert origin.POSTURE == "DARK"
    assert origin.ALLOW_MONEY_PUBLISH is False


def test_live_is_the_only_production_mode():
    assert origin.PRODUCTION_MODES == ("live",)
    assert origin.OFFLINE_HARNESSES == ("replay", "simulation")
    assert "paper" not in origin.PRODUCTION_MODES
    assert "shadow" not in origin.PRODUCTION_MODES
    assert "testnet" not in origin.PRODUCTION_MODES

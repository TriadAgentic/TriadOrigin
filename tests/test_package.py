"""Package posture: ORIGIN ships DARK with no money authority (Doc 00, Doc 04)."""

from __future__ import annotations

import triad_origin as origin


def test_identity_constants():
    assert origin.SERVICE_ID == "triad-origin-e02"
    assert origin.TOPOLOGY_NODE == "E02-V7"
    assert origin.NAMESPACE == "triad.origin.v7"
    assert origin.SPEC_VERSION == "1.0.0-RC1"


def test_dark_posture():
    assert origin.POSTURE == "DARK"
    assert origin.ALLOW_MONEY_PUBLISH is False


def test_three_mode_ladder_no_testnet():
    assert origin.MODES == ("shadow", "paper", "live")
    assert "testnet" not in origin.MODES
    assert "paper" in origin.MODES  # measurement lane, not a test venue

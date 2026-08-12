"""B02C milestone golden home — GV-001a / GV-001b (F00, ``instrument_math.v2``).

This file is the B02C acceptance profile's REQUIRED ARTIFACT
(``docs/control/closure/closure_semantics.v1.json`` → ``tests/formulas/test_f00_golden_b02c.py``).
It executes the Part D §D.1 registry-row replacements of GV-001:

* **GV-001a (ingress exact):** price ``"1.0"``, tick ``"0.10"`` → ``10`` PASS;
  price ``"1.05"``, tick ``"0.10"`` → ``QUARANTINE_NON_INTEGRAL``. No rounding anywhere.
* **GV-001b (order-compute):** computed BUY price ``100.005``, tick ``"0.01"`` →
  ``FLOOR_TO_TICK`` → ``100.00`` — explicitly PAR-006 / F21-scope SIDE SNAPPING, owned by E09.
  Origin hosts no price side-snap (order verbs are a forbidden capability here), so GV-001b's
  executable half in THIS repo is the negative wall: ingress must QUARANTINE the very value
  side-snap would round, proving ingress and side-snap can never be conflated again.

The exhaustive R-F00 battery (T1–T13 + property) lives in
``tests/kernel/test_instrument_math_v2.py``; this file re-walks only the registry-row vectors.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import instrument_math_v2 as im2  # noqa: E402

REV = "rev-1"


def _instrument(tick: str) -> im2.InstrumentV2:
    return im2.InstrumentV2(
        canonical_instrument_id="BINANCE_USDM:BTCUSDT",
        venue_model="BINANCE_USDM",
        tick_size=tick,
        step_size="0.001",
        min_notional="5",
        metadata_revision=REV,
    )


class TestGV001aIngressExact:
    def test_exact_grid_price_passes_as_the_integer_tick_count(self) -> None:
        # GV-001a PASS half: "1.0" on a "0.10" grid IS 10 ticks exactly.
        assert im2.price_to_ticks_ingress(_instrument("0.10"), "1.0", REV) == 10

    def test_off_grid_price_quarantines_non_integral_never_rounds(self) -> None:
        # GV-001a QUARANTINE half: "1.05" on a "0.10" grid is 10.5 ticks — a venue fact that
        # contradicts the declared grid. No rounding anywhere: the event is quarantined.
        with pytest.raises(im2.InstrumentV2Error) as exc:
            im2.price_to_ticks_ingress(_instrument("0.10"), "1.05", REV)
        assert exc.value.reason == im2.QUARANTINE_NON_INTEGRAL

    def test_no_rounding_mode_exists_on_the_v2_ingress_surface(self) -> None:
        # The v1 defect was a Rounding mode on ingress. v2 exposes none: the ingress functions
        # take no mode argument and the module defines no rounding enum.
        assert not hasattr(im2, "Rounding")


class TestGV001bOrderComputeScopeWall:
    """GV-001b is PAR-006 / F21-scope (E09-owned). Origin proves the scope wall."""

    def test_the_side_snap_input_is_quarantined_at_ingress(self) -> None:
        # 100.005 on a "0.01" grid is 10000.5 ticks. FLOOR_TO_TICK (F21 order-compute) would
        # yield 100.00 — but at INGRESS this exact value must quarantine, never round: the
        # conflation of ingress with side-snap is the defect GV-001 originally encoded.
        with pytest.raises(im2.InstrumentV2Error) as exc:
            im2.price_to_ticks_ingress(_instrument("0.01"), "100.005", REV)
        assert exc.value.reason == im2.QUARANTINE_NON_INTEGRAL

    def test_origin_hosts_no_price_side_snap_surface(self) -> None:
        # The only order-compute floor in Origin is QUANTITY (risk-conservative, spec §R-F00);
        # a PRICE order-compute snap would be an order-verb surface (forbidden here, E09 scope).
        assert hasattr(im2, "qty_to_steps_order_compute")
        assert not hasattr(im2, "price_to_ticks_order_compute")

    def test_quantity_order_compute_floors_toward_zero(self) -> None:
        # The lawful Origin-side order-compute half: quantity floors (never rounds up risk).
        inst = _instrument("0.01")
        assert im2.qty_to_steps_order_compute(inst, "0.0019", REV) == 1


class TestRevisionBinding:
    def test_mismatched_metadata_revision_quarantines(self) -> None:
        # §1.4: a conversion presented under a different metadata revision is refused — the
        # grid belongs to a revision, not to the instrument name.
        with pytest.raises(im2.InstrumentV2Error) as exc:
            im2.price_to_ticks_ingress(_instrument("0.10"), "1.0", "rev-2")
        assert exc.value.reason == im2.QUARANTINE_METADATA_REVISION

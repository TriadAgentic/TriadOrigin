"""B07 service-main battery: composed readiness (bootstrap + control-plane conjuncts), narrowness
(never exceeds READY_NO_AUTHORITY), the milestone's exact downgrade laws, zero forbidden
capability, and read-only/side-effect-free status reporting."""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts, service  # noqa: E402
from triad_origin.config import parameters as p  # noqa: E402
from triad_origin.health import Readiness  # noqa: E402


@pytest.fixture(scope="module")
def registry() -> p.ParameterRegistry:
    return p.load_registry()


@pytest.fixture(scope="module")
def known_contracts() -> frozenset:
    return frozenset(contracts.known_contracts())


READY_KWARGS = dict(
    manifest_ok=True, warmup_complete=True, checkpoint_parity=True, ledgers_writable=True)


def test_full_readiness_when_every_conjunct_holds(registry, known_contracts):
    readiness, detail = service.compute_service_readiness(
        parameter_registry=registry, known_contract_ids=known_contracts, **READY_KWARGS)
    assert readiness is Readiness.READY_NO_AUTHORITY
    assert detail["bootstrap"] == "READY_NO_AUTHORITY"
    assert detail["control_plane"]["config_ready"] is True


@pytest.mark.parametrize("field", ["manifest_ok", "warmup_complete", "checkpoint_parity",
                                    "ledgers_writable"])
def test_a_failing_bootstrap_conjunct_is_reported_verbatim_never_upgraded(
        registry, known_contracts, field):
    kwargs = dict(READY_KWARGS)
    kwargs[field] = False
    readiness, detail = service.compute_service_readiness(
        parameter_registry=registry, known_contract_ids=known_contracts, **kwargs)
    assert readiness is not Readiness.READY_NO_AUTHORITY
    assert detail["bootstrap"] != "READY_NO_AUTHORITY"


def test_a_failing_control_plane_conjunct_downgrades_to_warming_not_a_bare_false(
        registry, known_contracts):
    readiness, detail = service.compute_service_readiness(
        parameter_registry=registry, known_contract_ids=frozenset(), **READY_KWARGS)
    assert readiness is Readiness.WARMING
    assert detail["control_plane"]["config_ready"] is False
    assert detail["control_plane"]["signed_bundle_built"] is False


def test_control_plane_conjunct_names_every_check_never_a_bare_boolean(registry, known_contracts):
    result = service.b07_control_plane_ready(registry, known_contracts)
    assert set(result) == {
        "signed_bundle_built", "signed_bundle_verifies", "control_modules_present",
        "config_ready",
    }
    assert result["control_modules_present"] == (
        "triad_origin.control.comparator",
        "triad_origin.control.authority_fact_verifier",
        "triad_origin.control.legacy_bridge",
        "triad_origin.control.replay_runner",
    )


def test_service_status_shape(registry, known_contracts):
    status = service.service_status(
        parameter_registry=registry, known_contract_ids=known_contracts, **READY_KWARGS)
    assert status["service_id"] == "triad-origin-e02"
    assert status["posture"] == "DARK"
    assert status["readiness"] == "READY_NO_AUTHORITY"
    assert "detail" in status


def test_service_status_is_deterministic(registry, known_contracts):
    a = service.service_status(
        parameter_registry=registry, known_contract_ids=known_contracts, **READY_KWARGS)
    b = service.service_status(
        parameter_registry=registry, known_contract_ids=known_contracts, **READY_KWARGS)
    assert a == b


# ---------------------------------------------------------------------------------------------
# Narrowness: readiness can never exceed READY_NO_AUTHORITY (the enum has no state beyond it)
# ---------------------------------------------------------------------------------------------


def test_readiness_enum_has_no_state_beyond_ready_no_authority():
    values = [r.value for r in Readiness]
    idx = values.index("READY_NO_AUTHORITY")
    # Every value after READY_NO_AUTHORITY in declaration order is a WIND-DOWN state
    # (DRAINING/STOPPED/FAILED), never a "more ready" or "authorized" state.
    for later in values[idx + 1:]:
        assert later in ("DRAINING", "STOPPED", "FAILED")


def test_no_module_level_symbol_claims_authority_or_armed():
    import triad_origin.service as module
    forbidden_substrings = ("armed", "authorized", "live_", "credential", "venue")
    public_names = [name for name in dir(module) if not name.startswith("_")]
    for name in public_names:
        lowered = name.lower()
        for bad in forbidden_substrings:
            assert bad not in lowered, f"unexpectedly capability-shaped export: {name}"


# ---------------------------------------------------------------------------------------------
# Zero forbidden capability (the module import closure is stdlib + internal only)
# ---------------------------------------------------------------------------------------------


def test_capability_scanner_passes_over_the_whole_runtime():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_no_forbidden_capabilities.py")],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_service_module_only_imports_stdlib_and_internal_triad_origin():
    import ast
    tree = ast.parse((ROOT / "src" / "triad_origin" / "service.py").read_text(encoding="utf-8"))
    allowed_stdlib = {"__future__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                assert root in allowed_stdlib, f"unexpected import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                root = node.module.split(".", 1)[0]
                assert root in allowed_stdlib | {"triad_origin"}, \
                    f"unexpected import: {node.module}"
            else:
                # relative import — must resolve within the triad_origin package (level >= 1)
                assert node.level >= 1

"""The B07 service main — composes the R00 bootstrap readiness (:mod:`triad_origin.health`) with
the B07 control-plane readiness conjunct and reports a single, narrow verdict.

**THE LAW** (milestone B07 deliverable, verbatim): "Service main that reaches
``READY_NO_AUTHORITY`` only when its declared inputs are current and has no venue/order/credential
imports." This module (and its whole import closure) is stdlib-only + internal
:mod:`triad_origin` modules — proved by :mod:`tools.verify_no_forbidden_capabilities`, which this
file's own test battery also asserts passes.

**NARROWNESS** (row CTRL-B08-001, ``docs/plan/05_RC2_CONFLICT_REGISTER.md``): this module adds
exactly ONE new conjunct beyond R00's four bootstrap facts — that the B07 signed configuration
bundle is present and self-verifies, and that the B07 control-plane modules
(comparator/authority-fact-verifier/legacy-bridge/replay-runner) are importable. It does **not**
claim source freshness, coverage, lease validity, or estate activation — those remain B08's named,
still-open evidence dimensions (``triad_origin.health``'s own docstring: "does not yet prove
source freshness/coverage, lease validity or estate activation"). Readiness here can therefore
never exceed ``Readiness.READY_NO_AUTHORITY`` — the enum itself has no state beyond it (Doc 04
§04.17); there is structurally nothing "more ready" this module could claim even by mistake.

Pure and side-effect-free: no clock, no network, no I/O beyond the caller-injected registry
loaders it is handed (this module itself performs none). Every "current" fact is caller-supplied.
"""

from __future__ import annotations

from . import ALLOW_MONEY_PUBLISH, POSTURE, SERVICE_ID
from .config import parameters as config_parameters
from .config import signed_bundle as config_signed_bundle
from .control import authority_fact_verifier  # noqa: F401 - import-clean proof
from .control import comparator  # noqa: F401 - import-clean proof
from .control import legacy_bridge  # noqa: F401 - import-clean proof
from .control import replay_runner  # noqa: F401 - import-clean proof
from .health import Readiness, compute_readiness

_REQUIRED_CONTROL_MODULES = (
    "triad_origin.control.comparator",
    "triad_origin.control.authority_fact_verifier",
    "triad_origin.control.legacy_bridge",
    "triad_origin.control.replay_runner",
)


class ServiceError(RuntimeError):
    """A service-readiness computation could not proceed — fail closed, never a guessed verdict."""


def b07_control_plane_ready(
    parameter_registry: config_parameters.ParameterRegistry,
    known_contract_ids: frozenset,
) -> dict:
    """The B07 conjunct: the signed configuration bundle is buildable and self-verifies, and
    every required control-plane module is present (its import already having succeeded at this
    module's own load time — a failed import would have raised before this function ever ran).

    Returns a dict naming every check explicitly — never a bare boolean — so a caller can see
    exactly which fact is missing rather than a single opaque False.
    """
    result = {
        "signed_bundle_built": False,
        "signed_bundle_verifies": False,
        "control_modules_present": tuple(_REQUIRED_CONTROL_MODULES),
        "config_ready": False,
    }
    try:
        bundle = config_signed_bundle.build_signed_bundle(parameter_registry, known_contract_ids)
    except config_signed_bundle.SignedBundleError:
        return result
    result["signed_bundle_built"] = True
    result["signed_bundle_verifies"] = config_signed_bundle.verify_signed_bundle(bundle)
    result["config_ready"] = result["signed_bundle_built"] and result["signed_bundle_verifies"]
    return result


def compute_service_readiness(
    *,
    manifest_ok: bool,
    warmup_complete: bool,
    checkpoint_parity: bool,
    ledgers_writable: bool,
    parameter_registry: config_parameters.ParameterRegistry,
    known_contract_ids: frozenset,
) -> tuple[Readiness, dict]:
    """The single B07 service-readiness entry point.

    Composes the existing R00 bootstrap readiness with the new B07 control-plane conjunct:
    the bootstrap facts are checked first (an unready bootstrap is reported verbatim, never
    upgraded); only when bootstrap already reports ``READY_NO_AUTHORITY`` is the B07 conjunct
    consulted, and a failing B07 conjunct downgrades to ``Readiness.WARMING`` (the milestone's
    "only when its declared inputs are current" law) — never silently reported as ready.

    Returns ``(readiness, detail)`` — ``detail`` names every conjunct this function checked, so a
    caller never has to guess which fact blocked readiness.
    """
    if ALLOW_MONEY_PUBLISH:  # pragma: no cover - constitutional invariant, mirrors health.py
        raise ServiceError("constitutional breach: DARK service requires zero money capability")
    bootstrap = compute_readiness(
        manifest_ok=manifest_ok, warmup_complete=warmup_complete,
        checkpoint_parity=checkpoint_parity, ledgers_writable=ledgers_writable)
    control_plane = b07_control_plane_ready(parameter_registry, known_contract_ids)
    detail = {"bootstrap": bootstrap.value, "control_plane": control_plane}
    if bootstrap is not Readiness.READY_NO_AUTHORITY:
        return bootstrap, detail
    if not control_plane["config_ready"]:
        return Readiness.WARMING, detail
    return Readiness.READY_NO_AUTHORITY, detail


def service_status(
    *,
    manifest_ok: bool,
    warmup_complete: bool,
    checkpoint_parity: bool,
    ledgers_writable: bool,
    parameter_registry: config_parameters.ParameterRegistry,
    known_contract_ids: frozenset,
) -> dict:
    """A read-only status snapshot — the shape an operator/estate process reads. No side effect,
    no clock, no I/O; every fact is caller-supplied and merely composed here."""
    readiness, detail = compute_service_readiness(
        manifest_ok=manifest_ok, warmup_complete=warmup_complete,
        checkpoint_parity=checkpoint_parity, ledgers_writable=ledgers_writable,
        parameter_registry=parameter_registry, known_contract_ids=known_contract_ids)
    return {
        "service_id": SERVICE_ID,
        "posture": POSTURE,
        "readiness": readiness.value,
        "detail": detail,
    }

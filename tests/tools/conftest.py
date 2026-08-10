"""Shared fixtures for the ceremony draft-builder tests.

The frozen audit runner (``audit_package/triad_origin_b01_b10_audit.py``, v1.2.0) is the single
source of truth for every format and constant.  It is loaded DIFFERENTIALLY: its SHA-256 is
verified against the frozen pin before anything trusts it, the presence of the ``__main__``
guard is asserted before import (importing must not execute main), and the verified bytes are
staged into a pytest temp directory before ``importlib`` loads them — so the read-only
repository tree is never written to (no ``__pycache__`` beside the runner).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import pathlib
import subprocess
import sys
import types
from typing import Any, Callable

import pytest

# Never write bytecode caches while these tests import the frozen runner or the staged tools.
sys.dont_write_bytecode = True

TESTS_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
TOOLS_DIR = REPO_ROOT / "tools"

RUNNER_SHA256 = "12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2"
_RUNNER_CANDIDATES = (
    REPO_ROOT / "audit_package" / "triad_origin_b01_b10_audit.py",
    pathlib.Path("/home/user/TriadOrigin/audit_package/triad_origin_b01_b10_audit.py"),
)


def _runner_source_path() -> pathlib.Path:
    for candidate in _RUNNER_CANDIDATES:
        if candidate.is_file():
            return candidate
    pytest.skip("frozen audit runner not found in any known location")


@pytest.fixture(scope="session")
def frozen_runner(tmp_path_factory: pytest.TempPathFactory) -> types.ModuleType:
    """The frozen runner module, SHA-verified and imported from a temp copy (repo untouched)."""
    source_path = _runner_source_path()
    raw = source_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == RUNNER_SHA256, (
        f"frozen runner digest {digest} does not match the machine-law pin {RUNNER_SHA256}; "
        "refusing to trust it")
    text = raw.decode("utf-8")
    assert 'if __name__ == "__main__":' in text, (
        "frozen runner lacks a __main__ guard; importing it would execute main")
    staged = tmp_path_factory.mktemp("frozen_runner") / "triad_origin_b01_b10_audit_frozen.py"
    staged.write_bytes(raw)
    return _import_from_path("triad_origin_b01_b10_audit_frozen", staged)


def _import_from_path(module_name: str, path: pathlib.Path) -> types.ModuleType:
    """The documented importlib recipe: register in sys.modules BEFORE exec_module.

    The frozen runner uses ``from __future__ import annotations`` with ``@dataclasses.dataclass``
    classes; CPython's dataclass machinery resolves those string annotations through
    ``sys.modules[cls.__module__]``, so an unregistered module fails to import at all.
    """
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _load_tool(name: str) -> types.ModuleType:
    path = TOOLS_DIR / name
    assert path.is_file(), f"staged tool missing: {path}"
    return _import_from_path(f"staged_{name.removesuffix('.py')}", path)


@pytest.fixture(scope="session")
def tool_profile() -> types.ModuleType:
    return _load_tool("build_profile_decision.py")


@pytest.fixture(scope="session")
def tool_registry() -> types.ModuleType:
    return _load_tool("build_trust_registry.py")


@pytest.fixture(scope="session")
def tool_receipt() -> types.ModuleType:
    return _load_tool("build_receipt_v3.py")


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def tools_dir() -> pathlib.Path:
    return TOOLS_DIR


@pytest.fixture()
def run_tool() -> Callable[..., subprocess.CompletedProcess[str]]:
    """Run a staged tool as a CLI subprocess (the deliverable's real interface)."""
    def _run(name: str, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(TOOLS_DIR / name), *args],
            text=True, capture_output=True, env=env, timeout=120, check=False)
    return _run


def _valid_registry_spec(now_us: int) -> list[dict[str, Any]]:
    """A minimal valid two-key operator spec (PUBLIC key bytes only; never a private key)."""
    import base64
    return [
        {
            "key_id": "fixture-producer",
            "identity": "builder-a",
            "role": "PRODUCER",
            "public_key_base64": base64.b64encode(bytes(range(32))).decode("ascii"),
            "valid_from_us": str(now_us - 86_400_000_000),
            "valid_until_us": str(now_us + 365 * 86_400_000_000),
            "approved_milestones": ["ALL"],
        },
        {
            "key_id": "fixture-countersigner",
            "identity": "reviewer-b",
            "role": "COUNTERSIGNER",
            "public_key_base64": base64.b64encode(bytes(range(32, 64))).decode("ascii"),
            "valid_from_us": str(now_us - 86_400_000_000),
            "valid_until_us": str(now_us + 365 * 86_400_000_000),
            "approved_milestones": "ALL",
        },
    ]


@pytest.fixture(scope="session")
def registry_spec_factory() -> Callable[[int], list[dict[str, Any]]]:
    return _valid_registry_spec

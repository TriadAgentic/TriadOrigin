"""The DARK capability gate detects executable network/order code."""

from __future__ import annotations

import pytest

from tools import verify_no_forbidden_capabilities as gate


def test_current_runtime_has_no_forbidden_capability():
    assert gate.scan_runtime() == []


def test_gate_detects_network_and_order_calls(tmp_path):
    source = tmp_path / "unsafe.py"
    source.write_text("import requests\nplace_order()\n", encoding="utf-8")
    findings = gate.scan_file(source)
    assert any("unapproved runtime import requests" in finding for finding in findings)
    assert any("forbidden capability call place_order" in finding for finding in findings)


def test_gate_detects_standard_library_network_routes(tmp_path):
    source = tmp_path / "stdlib_network.py"
    source.write_text(
        "import urllib.request\nfrom http.client import HTTPSConnection\n"
        "urllib.request.urlopen('https://example.invalid')\n",
        encoding="utf-8",
    )
    findings = gate.scan_file(source)
    assert any("unapproved runtime import urllib.request" in finding for finding in findings)
    assert any("unapproved runtime import http.client" in finding for finding in findings)
    assert any("forbidden capability call urlopen" in finding for finding in findings)


def test_gate_detects_aliased_forbidden_imports(tmp_path):
    source = tmp_path / "aliased_capability.py"
    source.write_text(
        "from os import getenv as harmless_name\n"
        "harmless_name('VENUE_API_KEY')\n",
        encoding="utf-8",
    )
    findings = gate.scan_file(source)
    assert any("forbidden capability import os.getenv" in finding for finding in findings)


@pytest.mark.parametrize(
    "source_text, call_name",
    [
        ("eval(\"__import__('socket').socket()\")\n", "eval"),
        ("exec(compile('pass', '<x>', 'exec'))\n", "exec"),
        ("import os\ngetattr(os, 'get' + 'env')('API_KEY')\n", "getattr"),
    ],
)
def test_gate_rejects_dynamic_capability_construction(tmp_path, source_text, call_name):
    source = tmp_path / "dynamic.py"
    source.write_text(source_text, encoding="utf-8")
    findings = gate.scan_file(source)
    assert any(f"forbidden capability call {call_name}" in finding for finding in findings)

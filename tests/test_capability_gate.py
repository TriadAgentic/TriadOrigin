"""The DARK capability gate detects executable network/order code."""

from __future__ import annotations

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

#!/usr/bin/env python3
"""Emit the exact pytest node-ID collection, one UTF-8 ID per line."""

from __future__ import annotations

import sys

import pytest


class _Collector:
    def __init__(self) -> None:
        self.node_ids: list[str] = []

    def pytest_collection_finish(self, session) -> None:
        self.node_ids = [item.nodeid for item in session.items]


def main() -> int:
    collector = _Collector()
    # Clear configured addopts before disabling the terminal plugin. Repository ``-q`` is
    # implemented by that plugin and would otherwise make this controlled collector fail.
    result = pytest.main(
        [
            "-o", "addopts=", "--collect-only", "-p", "no:terminal",
            "-p", "no:cacheprovider",
        ],
        plugins=[collector],
    )
    if result != pytest.ExitCode.OK:
        print(f"FAIL: pytest collection exited {int(result)}", file=sys.stderr)
        return int(result)
    if not collector.node_ids or len(collector.node_ids) != len(set(collector.node_ids)):
        print("FAIL: pytest collection is empty or contains duplicate node IDs", file=sys.stderr)
        return 1
    for node_id in collector.node_ids:
        print(node_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

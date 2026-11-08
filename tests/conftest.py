"""Shared pytest helpers.

`report_line` lets a test record a diagnostic number (one that is reported but
not asserted on). The lines are printed in a "diagnostics" section of the
terminal summary, so they appear even under `pytest -q`.

`_block_network` runs for every test not marked `network`. It blocks Python
sockets (except Unix-domain sockets, which stay on this machine), DNS lookups,
and the curl_cffi and requests sessions. curl_cffi is patched separately
because it talks to the network through libcurl, not Python sockets, and it is
what yfinance uses.
"""

from __future__ import annotations

import socket
from collections.abc import Callable

import curl_cffi.requests
import pytest
import requests

_REPORT_KEY = pytest.StashKey[list[str]]()


class NetworkBlockedError(RuntimeError):
    """Raised when a test without the network marker tries to use the network."""


def _refuse(*args: object, **kwargs: object) -> None:
    raise NetworkBlockedError(
        "network access in a test not marked @pytest.mark.network"
    )


@pytest.fixture(autouse=True)
def _block_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    if request.node.get_closest_marker("network") is not None:
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def connect(self: socket.socket, address: object) -> None:
        if self.family == socket.AF_UNIX:
            return real_connect(self, address)
        _refuse()

    def connect_ex(self: socket.socket, address: object) -> int:
        if self.family == socket.AF_UNIX:
            return real_connect_ex(self, address)
        _refuse()
        return 1  # not reached

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    monkeypatch.setattr(curl_cffi.requests.Session, "request", _refuse)
    monkeypatch.setattr(curl_cffi.requests.AsyncSession, "request", _refuse)
    monkeypatch.setattr(requests.Session, "request", _refuse)


def pytest_configure(config: pytest.Config) -> None:
    config.stash[_REPORT_KEY] = []


@pytest.fixture
def report_line(request: pytest.FixtureRequest) -> Callable[[str], None]:
    lines = request.config.stash[_REPORT_KEY]
    return lines.append


def pytest_terminal_summary(
    terminalreporter, exitstatus, config: pytest.Config
) -> None:
    lines = config.stash.get(_REPORT_KEY, [])
    if lines:
        terminalreporter.write_sep("-", "diagnostics")
        for line in lines:
            terminalreporter.write_line(line)

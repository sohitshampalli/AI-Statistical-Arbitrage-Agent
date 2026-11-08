"""The autouse guard in conftest.py blocks network access in ordinary tests.

192.0.2.1 is in TEST-NET-1 (RFC 5737), reserved for documentation, so even if
the guard failed these calls would not reach a real host.
"""

from __future__ import annotations

import socket

import curl_cffi.requests
import pytest
import requests

TEST_NET = "192.0.2.1"
BLOCKED = "not marked @pytest.mark.network"


def test_tcp_connect_is_blocked() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        with pytest.raises(RuntimeError, match=BLOCKED):
            s.connect((TEST_NET, 80))
        with pytest.raises(RuntimeError, match=BLOCKED):
            s.connect_ex((TEST_NET, 80))


def test_dns_and_create_connection_are_blocked() -> None:
    with pytest.raises(RuntimeError, match=BLOCKED):
        socket.getaddrinfo("example.com", 80)
    with pytest.raises(RuntimeError, match=BLOCKED):
        socket.create_connection((TEST_NET, 80), timeout=1)


def test_http_clients_are_blocked() -> None:
    with pytest.raises(RuntimeError, match=BLOCKED):
        curl_cffi.requests.get(f"http://{TEST_NET}/", timeout=1)
    with pytest.raises(RuntimeError, match=BLOCKED):
        requests.get(f"http://{TEST_NET}/", timeout=1)


def test_unix_sockets_still_work() -> None:
    a, b = socket.socketpair()
    with a, b:
        a.sendall(b"ok")
        assert b.recv(2) == b"ok"

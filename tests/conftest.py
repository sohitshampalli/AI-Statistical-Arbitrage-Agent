"""Shared pytest helpers.

`report_line` lets a test record a diagnostic number (one that is reported but
not asserted on). The lines are printed in a "diagnostics" section of the
terminal summary, so they appear even under `pytest -q`.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

_REPORT_KEY = pytest.StashKey[list[str]]()


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

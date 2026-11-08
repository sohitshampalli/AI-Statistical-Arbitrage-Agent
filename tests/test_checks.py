"""Tests for the pre-analysis data checks and anomaly flags."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from statarb_agent.data.checks import (
    check_history,
    fatal_failures,
    flags,
)

CALENDAR = pd.bdate_range("2015-01-01", "2015-12-31", name="date")
START = pd.Timestamp("2015-01-01")
ASOF = pd.Timestamp("2016-01-01")
NAMES = [
    "enough_history",
    "listed_throughout",
    "no_missing_days",
    "no_extra_days",
    "large_move",
    "large_distribution",
    "stale_closes",
]


def _prices(index: pd.DatetimeIndex, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 50.0 * np.exp(np.cumsum(0.01 * rng.standard_normal(len(index))))
    return pd.DataFrame(
        {"close": close, "dividends": 0.0, "capital_gains": 0.0}, index=index
    )


def _run(prices: pd.DataFrame, **kwargs: object) -> dict[str, object]:
    checks = check_history(
        prices, ticker="KO", start=START, asof=ASOF, calendar=CALENDAR,
        min_obs=200, **kwargs,
    )
    assert [c.name for c in checks] == NAMES
    return {c.name: c for c in checks}


def test_clean_history_passes_everything() -> None:
    checks = _run(_prices(CALENDAR))
    assert all(c.passed for c in checks.values())
    assert fatal_failures(list(checks.values())) == []
    assert flags(list(checks.values())) == []
    assert [c.fatal for c in checks.values()] == [True] * 4 + [False] * 3


def test_too_little_history() -> None:
    c = _run(_prices(CALENDAR))["enough_history"]
    assert c.passed
    short = check_history(
        _prices(CALENDAR), ticker="KO", start=START, asof=ASOF, calendar=CALENDAR,
        min_obs=300,
    )[0]
    assert not short.passed and "261 rows" in short.detail and "300" in short.detail


def test_late_listing_is_fatal_with_dates() -> None:
    late = CALENDAR[CALENDAR >= "2015-03-02"]
    c = _run(_prices(late))["listed_throughout"]
    assert not c.passed and c.fatal
    assert "starts on 2015-03-02" in c.detail and "2015-01-01" in c.detail


def test_early_end_is_fatal() -> None:
    c = _run(_prices(CALENDAR[CALENDAR <= "2015-11-30"]))["listed_throughout"]
    assert not c.passed and "ends on 2015-11-30" in c.detail


def test_missing_and_extra_days() -> None:
    prices = _prices(CALENDAR).drop(CALENDAR[[40, 41, 90]])
    checks = _run(prices)
    assert not checks["no_missing_days"].passed
    assert "missing 3 trading days" in checks["no_missing_days"].detail
    assert str(CALENDAR[40].date()) in checks["no_missing_days"].detail
    saturday = pd.DatetimeIndex([pd.Timestamp("2015-06-06")])
    extra = pd.concat([_prices(CALENDAR), _prices(saturday)]).sort_index()
    checks = _run(extra)
    assert not checks["no_extra_days"].passed and "2015-06-06" in checks["no_extra_days"].detail


def test_large_move_is_flagged_not_fatal() -> None:
    prices = _prices(CALENDAR)
    prices.iloc[100:, 0] *= 0.6  # log return about -0.51 on one day
    checks = _run(prices)
    c = checks["large_move"]
    assert not c.passed and not c.fatal
    assert str(CALENDAR[100].date()) in c.detail
    assert fatal_failures(list(checks.values())) == []


def test_large_move_threshold_is_strict() -> None:
    prices = _prices(CALENDAR)
    prices.iloc[100:, 0] = prices.iloc[100:, 0] * 0.5
    move = abs(np.log(prices["close"].iloc[100] / prices["close"].iloc[99]))
    assert not _run(prices, max_abs_log_return=move - 1e-9)["large_move"].passed
    assert _run(prices, max_abs_log_return=move)["large_move"].passed  # strict >


def test_large_distribution_is_flagged() -> None:
    prices = _prices(CALENDAR)
    prev = prices["close"].iloc[49]
    prices.iloc[50, prices.columns.get_loc("dividends")] = 0.12 * prev
    prices.iloc[120, prices.columns.get_loc("capital_gains")] = 0.05 * prev
    c = _run(prices)["large_distribution"]
    assert not c.passed and not c.fatal
    assert "1 payments" in c.detail and str(CALENDAR[50].date()) in c.detail


def test_stale_closes_are_flagged_from_five() -> None:
    prices = _prices(CALENDAR)
    prices.iloc[60:64, 0] = prices.iloc[60, 0]  # 4 identical: not flagged
    assert _run(prices)["stale_closes"].passed
    prices.iloc[150:155, 0] = prices.iloc[150, 0]  # 5 identical: flagged
    c = _run(prices)["stale_closes"]
    assert not c.passed and not c.fatal
    assert f"{CALENDAR[150].date()} (5 days)" in c.detail and "1 runs" in c.detail


def test_rows_at_or_after_asof_are_never_read() -> None:
    """Look-ahead test: gaps, anomalies and NaN on or after asof change nothing,
    and neither do reference days after asof."""
    asof = CALENDAR[200]
    base = _prices(CALENDAR)
    calendar_long = CALENDAR.union(pd.bdate_range("2016-01-01", periods=30))

    def run(prices: pd.DataFrame, calendar: pd.DatetimeIndex) -> list[object]:
        return check_history(prices, ticker="KO", start=START, asof=asof,
                             calendar=calendar, min_obs=150)

    before = run(base, CALENDAR)
    changed = base.copy()
    changed.iloc[200:, 0] = np.nan
    changed.iloc[205, 1] = 99.0
    changed = changed.drop(CALENDAR[[201, 210]])
    assert run(changed, calendar_long) == before


def test_calendar_with_no_day_in_window_raises() -> None:
    with pytest.raises(ValueError, match="no trading day"):
        check_history(_prices(CALENDAR), ticker="KO", start="2020-01-01",
                      asof="2020-02-01", calendar=CALENDAR, min_obs=1)

"""Tests for span metrics, on a small ledger built by hand."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from statarb_agent.backtest import metrics as m
from statarb_agent.backtest.engine import BacktestResult
from statarb_agent.backtest.summary import (
    simple_returns,
    span_metrics,
    study_span_metrics,
)
from statarb_agent.study import Period, StudyConfig

INDEX = pd.bdate_range("2017-12-25", periods=10, name="date")  # crosses into 2018
PNL = np.array([0.0, 0.0, 10.0, -20.0, 30.0, 0.0, -5.0, 15.0, 0.0, 5.0])
CAPITAL = 1000.0


def make_result() -> BacktestResult:
    daily = pd.DataFrame(
        {
            "position": [0, 0, 1, 1, 1, 0, -1, -1, 0, 0],
            "price_pnl": PNL + 1.0,
            "dist_pnl": 0.5,
            "borrow_cost": 0.5,
            "trade_cost": 1.0,
            "gross_pnl": PNL + 1.5,
            "pnl": PNL,
            "ret": PNL / CAPITAL,
            "gross_ret": (PNL + 1.5) / CAPITAL,
            "traded_notional": [0, 0, 1000, 0, 0, 1000, 1000, 0, 1000, 0],
        },
        index=INDEX,
    )
    trades = pd.DataFrame(
        {
            "exit_date": [INDEX[5], INDEX[8], pd.NaT],
            "open": [False, False, True],
            "net_pnl": [20.0, -3.0, 1.0],
            "bars_held": [3, 2, 1],
            "exit_reason": ["exit", "time_stop", ""],
        }
    )
    return BacktestResult(
        kind="pair", labels=("A", "B"), hedge="static", cost_bps=10.0, daily=daily,
        trades=trades, signals=pd.DataFrame(), windows=pd.DataFrame(),
        first_signal_date=INDEX[2], settings={"capital": CAPITAL},
    )


def test_full_span_starts_at_the_first_signal_bar() -> None:
    out = span_metrics(make_result())
    ret = PNL[2:] / CAPITAL
    assert out["start"] == str(INDEX[2].date()) and out["end"] == str(INDEX[9].date())
    assert out["n_days"] == 8
    assert out["total_return"] == pytest.approx(0.035)
    assert out["sharpe"] == pytest.approx(m.sharpe_ratio(ret))
    assert out["sharpe_per_period"] == pytest.approx(ret.mean() / ret.std(ddof=1))
    assert out["annualised_return"] == pytest.approx(ret.mean() * 252)
    # equity from 1000: 1010, 990, 1020, 1020, 1015, 1030, 1030, 1035 -> worst 1010 to 990
    assert out["max_drawdown"] == pytest.approx(20.0 / 1010.0)
    assert out["n_trades"] == 2 and out["hit_rate"] == 0.5
    assert out["average_holding_bars"] == 2.5
    assert out["exit_reasons"] == {"exit": 1, "time_stop": 1}
    assert out["share_in_market"] == pytest.approx(5 / 8)
    assert out["annual_turnover"] == pytest.approx(4000 / 1000 * 252 / 8)
    assert out["cost_drag"] == pytest.approx(1.5 / CAPITAL * 252)
    assert out["trade_cost_return"] == pytest.approx(8 * 1.0 / CAPITAL)
    assert out["borrow_cost_return"] == pytest.approx(8 * 0.5 / CAPITAL)
    assert out["distribution_return"] == pytest.approx(8 * 0.5 / CAPITAL)
    assert math.isnan(out["beta_to_benchmark"])
    assert 0.0 < out["psr_zero"] < 1.0


def test_a_first_day_loss_counts_as_drawdown() -> None:
    out = span_metrics(make_result(), start=INDEX[3], end=INDEX[4])
    # span returns -20 then +30 on capital 1000: equity 1000, 980, 1010
    assert out["n_days"] == 2 and out["max_drawdown"] == pytest.approx(0.02)
    assert out["n_trades"] == 0 and math.isnan(out["hit_rate"])


def test_spans_split_by_date_and_trades_by_exit_date() -> None:
    result = make_result()
    study = StudyConfig(
        formation=Period(pd.Timestamp("2010-01-01"), pd.Timestamp("2017-12-31")),
        validation=Period(pd.Timestamp("2018-01-01"), pd.Timestamp("2021-12-31")),
        test_start=pd.Timestamp("2022-01-01"),
        test_period_unlocked=False,
    )
    spans = study_span_metrics(result, study)
    assert set(spans) == {"full", "formation", "validation"}
    formation, validation = spans["formation"], spans["validation"]
    # rows 2..4 are 2017-12-27..29; rows 5..9 are 2018-01-01..05
    assert (formation["start"], formation["end"]) == ("2017-12-27", "2017-12-29")
    assert (validation["start"], validation["end"]) == ("2018-01-01", "2018-01-05")
    assert formation["n_days"] + validation["n_days"] == spans["full"]["n_days"]
    assert formation["total_return"] == pytest.approx(0.020)
    assert validation["total_return"] == pytest.approx(0.015)
    assert formation["n_trades"] == 0 and validation["n_trades"] == 2
    assert span_metrics(result, start="2019-01-01") is None
    assert span_metrics(result, end=INDEX[2]) is None  # one row is not enough


def test_beta_uses_the_benchmark_on_the_same_dates() -> None:
    result = make_result()
    bench = pd.Series(np.linspace(-0.01, 0.02, 10), index=INDEX)
    out = span_metrics(result, benchmark=bench)
    expected = m.beta_to_benchmark(PNL[2:] / CAPITAL, bench.to_numpy()[2:])
    assert out["beta_to_benchmark"] == pytest.approx(expected)
    assert math.isnan(
        span_metrics(result, benchmark=bench.drop(INDEX[4]))["beta_to_benchmark"]
    )


def test_simple_returns() -> None:
    tr = pd.Series([100.0, 110.0, 99.0], index=INDEX[:3])
    out = simple_returns(tr)
    assert list(out.index) == list(INDEX[1:3])
    np.testing.assert_allclose(out, [0.10, -0.10])

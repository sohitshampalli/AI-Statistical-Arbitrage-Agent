"""Tests for the control data and batch runner (fast, small cases)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from statarb_agent.backtest.controls import (
    BATCH_COLUMNS,
    placebo_rank,
    run_batch,
    shuffle_dates,
    shuffle_pair,
    simulated_pair_frames,
    summarise_batch,
)
from statarb_agent.backtest.engine import run_pair_backtest
from statarb_agent.backtest.summary import span_metrics, study_span_metrics
from statarb_agent.data.synthetic import as_price_frame, simulate_cointegrated_pair
from statarb_agent.study import Period, StudyConfig


def paying_frame(n: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2012-01-02", periods=n, name="date")
    close = 40.0 * np.exp(np.cumsum(0.012 * rng.standard_normal(n)))
    dividends = np.zeros(n)
    dividends[20::60] = 0.25
    gains = np.zeros(n)
    gains[100] = 0.1
    growth = np.ones(n)
    growth[1:] = (close[1:] + dividends[1:] + gains[1:]) / close[:-1]
    return pd.DataFrame(
        {"close": close, "dividends": dividends, "capital_gains": gains,
         "tr_close": close[0] * np.cumprod(growth)},
        index=idx,
    )


def test_shuffle_keeps_every_daily_move_and_the_total() -> None:
    frame = paying_frame()
    out = shuffle_dates(frame, seed=3)
    assert out.index.equals(frame.index) and list(out.columns) == list(frame.columns)
    assert out["close"].iloc[0] == frame["close"].iloc[0]
    growth = lambda f: (f["close"].to_numpy()[1:] / f["close"].to_numpy()[:-1])
    np.testing.assert_allclose(np.sort(growth(out)), np.sort(growth(frame)), rtol=1e-12)
    # same moves in another order: the last close and total return are unchanged
    assert out["close"].iloc[-1] == pytest.approx(frame["close"].iloc[-1], rel=1e-10)
    assert out["tr_close"].iloc[-1] == pytest.approx(frame["tr_close"].iloc[-1], rel=1e-10)
    # distribution yields are permuted with their price moves
    dist = lambda f: ((f["dividends"] + f["capital_gains"]).to_numpy()[1:]
                      / f["close"].to_numpy()[:-1])
    np.testing.assert_allclose(np.sort(dist(out)), np.sort(dist(frame)), atol=1e-15)
    assert (out["capital_gains"] == 0.0).all()
    total = (dist(out) + growth(out))
    np.testing.assert_allclose(
        out["tr_close"].to_numpy()[1:] / out["tr_close"].to_numpy()[:-1], total, rtol=1e-12
    )
    assert not np.allclose(out["close"], frame["close"])


def test_shuffle_is_deterministic_and_seeded() -> None:
    frame = paying_frame()
    pd.testing.assert_frame_equal(shuffle_dates(frame, 3), shuffle_dates(frame, 3))
    assert not shuffle_dates(frame, 3)["close"].equals(shuffle_dates(frame, 4)["close"])
    with pytest.raises(ValueError):
        shuffle_dates(frame.iloc[:2], 0)


def test_shuffle_destroys_the_relation_between_the_legs() -> None:
    """A cointegrated pair's legs have highly correlated returns (measured 0.95
    here); after shuffling one leg the correlation is near zero (bound 0.15, about
    4 standard errors of a zero correlation over 800 rows, 1 / sqrt(800) each)."""
    pair = simulate_cointegrated_pair(seed=4, n_obs=800)
    a, b = as_price_frame(pair["log_a"]), as_price_frame(pair["log_b"])
    returns = lambda f: np.diff(np.log(f["close"].to_numpy()))
    assert np.corrcoef(returns(a), returns(b))[0, 1] > 0.6
    shuffled = shuffle_dates(b, seed=9)
    assert abs(np.corrcoef(returns(a), returns(shuffled))[0, 1]) < 0.15


def test_simulated_pair_frames(bt_config) -> None:
    config = bt_config()
    a, _ = simulated_pair_frames("cointegrated", 5, config, "2010-01-01")
    assert len(a) == 800 and a.index[0] == pd.Timestamp("2010-01-01")
    direct = simulate_cointegrated_pair(seed=5, n_obs=800, start="2010-01-01")
    np.testing.assert_allclose(np.log(a["close"]), direct["log_a"], rtol=1e-12)
    ra, _ = simulated_pair_frames("random_walk", 5, config, "2010-01-01")
    assert len(ra) == 800 and not ra["close"].equals(a["close"])
    assert (ra["dividends"] == 0).all() and ra["close"].equals(ra["tr_close"])
    with pytest.raises(ValueError):
        simulated_pair_frames("other", 5, config, "2010-01-01")


def test_run_batch_matches_single_runs(bt_config) -> None:
    config = bt_config()
    make = lambda seed: simulated_pair_frames("cointegrated", seed, config, "2010-01-01")
    batch = run_batch(make, range(100, 104), asof="2100-01-01", config=config)
    assert list(batch.columns) == list(BATCH_COLUMNS) and list(batch["seed"]) == [
        100, 101, 102, 103,
    ]
    a, b = make(102)
    single = span_metrics(run_pair_backtest(a, b, asof="2100-01-01", config=config))
    row = batch.loc[batch["seed"] == 102].iloc[0]
    assert row["sharpe"] == pytest.approx(single["sharpe"])
    assert row["total_return"] == pytest.approx(single["total_return"])
    assert row["gross_return"] == pytest.approx(
        single["price_return"] + single["distribution_return"]
    )
    assert row["n_trades"] == single["n_trades"]
    assert batch[["sharpe_formation", "sharpe_validation"]].isna().all().all()
    study = StudyConfig(
        formation=Period(pd.Timestamp("2010-01-01"), pd.Timestamp("2011-12-31")),
        validation=Period(pd.Timestamp("2012-01-01"), pd.Timestamp("2012-12-31")),
        test_start=pd.Timestamp("2022-01-01"),
        test_period_unlocked=False,
    )
    spans = run_batch(make, range(102, 103), asof="2100-01-01", config=config, study=study)
    result = run_pair_backtest(a, b, asof="2100-01-01", config=config)
    expected = study_span_metrics(result, study)
    assert spans["sharpe_formation"].iloc[0] == pytest.approx(expected["formation"]["sharpe"])
    assert spans["sharpe_validation"].iloc[0] == pytest.approx(
        expected["validation"]["sharpe"]
    )
    assert spans["sharpe"].iloc[0] == pytest.approx(row["sharpe"])
    free = run_batch(make, range(100, 104), asof="2100-01-01", config=config, cost_bps=0.0)
    assert (free["total_return"] > batch["total_return"]).all()
    np.testing.assert_allclose(free["gross_return"], batch["gross_return"])


def test_summarise_batch_by_hand() -> None:
    batch = pd.DataFrame(
        {
            "seed": [1, 2, 3, 4],
            "sharpe": [1.5, -0.5, math.nan, 0.5],
            "gross_sharpe": [2.0, 0.0, math.nan, 1.0],
            "total_return": [0.10, -0.02, 0.0, 0.04],
            "gross_return": [0.12, 0.00, 0.0, 0.06],
            "n_trades": [10, 4, 0, 6],
            "hit_rate": [0.7, 0.4, math.nan, 0.5],
            "share_in_market": [0.3, 0.2, 0.0, 0.25],
            "sharpe_formation": [math.nan] * 4,
            "sharpe_validation": [math.nan] * 4,
        }
    )
    out = summarise_batch(batch)
    assert out["n_seeds"] == 4 and out["n_sharpe_defined"] == 3
    assert out["mean_sharpe"] == pytest.approx(0.5)
    assert out["median_sharpe"] == pytest.approx(0.5)
    assert out["mean_total_return"] == pytest.approx(0.03)
    assert out["mean_gross_return"] == pytest.approx(0.045)
    gross = np.array([0.12, 0.0, 0.0, 0.06])
    assert out["gross_return_t"] == pytest.approx(
        gross.mean() / (gross.std(ddof=1) / 2.0)
    )
    assert out["share_positive"] == 0.5  # the zero is not positive
    assert out["share_sharpe_above_1"] == 0.25  # NaN is not above 1
    assert out["mean_trades"] == 5.0
    with pytest.raises(ValueError):
        summarise_batch(batch.iloc[:1])


def test_shuffle_pair_shuffles_both_legs_differently() -> None:
    a, b = paying_frame(seed=1), paying_frame(seed=2)
    sa, sb = shuffle_pair(a, b, seed=5)
    assert not sa["close"].equals(a["close"]) and not sb["close"].equals(b["close"])
    for original, shuffled in ((a, sa), (b, sb)):
        assert shuffled["close"].iloc[-1] == pytest.approx(original["close"].iloc[-1])
    # the two legs do not share one permutation: shuffling a frame against
    # itself gives two different paths
    twin_a, twin_b = shuffle_pair(a, a, seed=5)
    assert not twin_a["close"].equals(twin_b["close"])
    again_a, again_b = shuffle_pair(a, b, seed=5)
    pd.testing.assert_frame_equal(again_a, sa)
    pd.testing.assert_frame_equal(again_b, sb)
    assert not shuffle_pair(a, b, seed=6)[0]["close"].equals(sa["close"])


def test_placebo_rank_by_hand() -> None:
    out = placebo_rank(1.0, np.array([0.5, 1.0, 1.5, -0.2, math.nan]))
    # four defined placebos; two are at least 1.0; (1 + 2) / (1 + 4)
    assert out == {"n_placebos": 4.0, "placebo_mean": pytest.approx(0.7),
                   "share_at_least": pytest.approx(0.6)}
    assert placebo_rank(9.0, np.array([0.1, 0.2]))["share_at_least"] == pytest.approx(1 / 3)
    assert math.isnan(placebo_rank(math.nan, np.array([0.1]))["share_at_least"])
    assert math.isnan(placebo_rank(1.0, np.array([math.nan]))["share_at_least"])

"""Phase 3 gate: the backtester finds an edge only where one was built in.

Each test runs the walk-forward backtest with the project's settings
(configs/backtest.yaml) on 200 simulated cases, seeds 21000 to 21199, and
checks rates and means against bounds set from a separate calibration run
(seeds 20000 to 20199, scripts/measure_backtest_controls.py). Per-seed
calibration figures at 10 basis points per leg:

- cointegrated pairs, half-life 10: mean annualised net Sharpe 0.83 (static),
  0.85 (rolling), 0.86 (kalman), standard deviation across seeds 0.26, so the
  mean of 200 has a standard error of 0.018; all 200 seeds had a positive net
  return.
- independent random walks: mean net Sharpe -0.07, -0.06, -0.05, standard
  deviation 0.29 (standard error 0.020); t statistic of the mean gross return
  -0.5, -0.3, +0.7; no seed had a Sharpe above 1.
- shuffled-date placebos (one simulated cointegrated pair per seed, both legs
  shuffled): t of the mean gross return +0.7, mean net Sharpe -0.03, no seed
  above 1.
- cointegrated baskets: mean net Sharpe 0.47, 96.0 percent of seeds positive;
  independent baskets: t of the mean gross return +1.3, no seed above 1.

Bounds:
- "edge": the mean gross return is more than 3 standard errors above zero
  (calibration t statistics were between 37 and 61); mean net Sharpe above 0.70 for pairs (7 standard errors below the
  calibration mean) and above 0.33 for baskets (7 below); positive net return
  on at least 97 percent of pair seeds and 90 percent of basket seeds (the
  latter 4.3 standard errors below 96 percent).
- "no edge": the mean gross return is within 3 standard errors of zero
  (|t| < 3; costs are excluded so this tests the signal, not the fees), the
  mean net Sharpe is below 0.10 (7 standard errors above the calibration
  means), and at most 2 percent of seeds have a net Sharpe above 1.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from statarb_agent.backtest.config import BacktestConfig, load_backtest_config
from statarb_agent.backtest.controls import (
    run_batch,
    shuffle_pair,
    simulated_pair_frames,
    summarise_batch,
)
from statarb_agent.data.synthetic import as_price_frame, simulate_basket

REPO_ROOT = Path(__file__).resolve().parents[1]
SEEDS = range(21000, 21200)
START = "2010-01-01"
ASOF = "2100-01-01"
HEDGES = ("static", "rolling", "kalman")

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def config() -> BacktestConfig:
    return load_backtest_config(REPO_ROOT / "configs" / "backtest.yaml")


def _report(report_line: Callable[[str], None], name: str, s: dict[str, Any]) -> None:
    report_line(
        f"gate, {name}, seeds 21000-21199: mean net Sharpe {s['mean_sharpe']:.2f}, "
        f"positive {s['share_positive']:.1%}, Sharpe > 1 "
        f"{s['share_sharpe_above_1']:.1%}, gross t {s['gross_return_t']:+.1f}, mean "
        f"trades {s['mean_trades']:.1f}"
    )


def _assert_edge(s: dict[str, Any], min_sharpe: float, min_positive: float) -> None:
    assert s["mean_sharpe"] > min_sharpe
    assert s["share_positive"] >= min_positive
    assert s["gross_return_t"] > 3.0


def _assert_no_edge(s: dict[str, Any]) -> None:
    assert abs(s["gross_return_t"]) < 3.0
    assert s["mean_sharpe"] < 0.10
    assert s["share_sharpe_above_1"] <= 0.02


@pytest.mark.parametrize("hedge", HEDGES)
def test_cointegrated_pairs_show_an_edge(
    config: BacktestConfig, report_line: Callable[[str], None], hedge: str
) -> None:
    batch = run_batch(
        lambda seed: simulated_pair_frames("cointegrated", seed, config, START),
        SEEDS, asof=ASOF, config=config, hedge=hedge,
    )
    summary = summarise_batch(batch)
    _report(report_line, f"cointegrated pairs, {hedge}", summary)
    _assert_edge(summary, min_sharpe=0.70, min_positive=0.97)


@pytest.mark.parametrize("hedge", HEDGES)
def test_random_walks_show_no_edge(
    config: BacktestConfig, report_line: Callable[[str], None], hedge: str
) -> None:
    batch = run_batch(
        lambda seed: simulated_pair_frames("random_walk", seed, config, START),
        SEEDS, asof=ASOF, config=config, hedge=hedge,
    )
    summary = summarise_batch(batch)
    _report(report_line, f"random walks, {hedge}", summary)
    _assert_no_edge(summary)


def test_shuffled_placebos_show_no_edge(
    config: BacktestConfig, report_line: Callable[[str], None]
) -> None:
    """Each seed: a simulated cointegrated pair with both legs' dates shuffled."""

    def make(seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        a, b = simulated_pair_frames("cointegrated", seed, config, START)
        return shuffle_pair(a, b, seed)

    summary = summarise_batch(run_batch(make, SEEDS, asof=ASOF, config=config))
    _report(report_line, "shuffled placebos of cointegrated pairs, static", summary)
    _assert_no_edge(summary)


def _basket(config: BacktestConfig, seed: int, cointegrated: bool) -> dict[str, pd.DataFrame]:
    c = config.controls
    frame = simulate_basket(
        seed=seed, cointegrated=cointegrated, half_life=c.half_life,
        spread_sd=c.spread_sd, sigma=c.sigma, n_obs=c.n_obs, start=START,
    )
    return {name: as_price_frame(frame[name]) for name in frame.columns}


def test_cointegrated_baskets_show_an_edge(
    config: BacktestConfig, report_line: Callable[[str], None]
) -> None:
    batch = run_batch(
        lambda seed: _basket(config, seed, True), SEEDS, asof=ASOF, config=config
    )
    summary = summarise_batch(batch)
    _report(report_line, "cointegrated baskets, johansen", summary)
    _assert_edge(summary, min_sharpe=0.33, min_positive=0.90)


def test_independent_baskets_show_no_edge(
    config: BacktestConfig, report_line: Callable[[str], None]
) -> None:
    batch = run_batch(
        lambda seed: _basket(config, seed, False), SEEDS, asof=ASOF, config=config
    )
    summary = summarise_batch(batch)
    _report(report_line, "independent baskets, johansen", summary)
    _assert_no_edge(summary)

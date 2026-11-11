"""Controls: data on which the strategy should, or should not, show an edge.

The backtester's gate is that it finds an edge only where one exists:

- simulated cointegrated pairs: an edge is expected;
- simulated pairs of independent random walks: no edge;
- shuffled-date placebos of a real pair: no edge;
- an unrelated real pair (V and XOM): no edge is expected.

This module builds the control data and runs batches of backtests over fixed
seeds. It computes no statistic of its own beyond summarising the per-seed
metrics that backtest.summary produced.

Shuffled-date placebo. For each leg separately, the day-to-day moves (price
return and distribution yield together) are put in a random order and the price
path is rebuilt from the first close. Every daily move of a leg still occurs
exactly once, so its return distribution and its total return over the period
are unchanged, but the dates no longer line up with the other leg, so any
relation between the two legs is destroyed.

Both legs are shuffled, not one. Measured on simulated pairs (2026-11-11): with
one leg left in place, every placebo of a pair shares that leg's path, and the
batch mean depends on that one path. Across six base pairs the mean gross
return of 100 one-leg placebos ranged from -2.87 to +2.65 percent a year, far
from zero in both directions. Shuffling both legs of one base pair gave -0.17
percent a year (t = -0.9 over 200 placebos).

A placebo batch is a permutation test: if the two legs were unrelated, the real
ordering of dates would be one more shuffle, so the share of placebos that do
at least as well as the real pair is a p-value for "this pair's result needs
the dates to line up".
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from statarb_agent.backtest.config import BacktestConfig
from statarb_agent.backtest.engine import (
    BacktestResult,
    run_basket_backtest,
    run_pair_backtest,
)
from statarb_agent.backtest.summary import span_metrics
from statarb_agent.data.synthetic import (
    as_price_frame,
    simulate_cointegrated_pair,
    simulate_random_walk_pair,
)
from statarb_agent.sources.prices import total_return_index

BATCH_COLUMNS = (
    "seed", "sharpe", "gross_sharpe", "total_return", "gross_return", "n_trades",
    "hit_rate", "share_in_market",
)


def shuffle_dates(
    frame: pd.DataFrame, seed: int | np.random.SeedSequence
) -> pd.DataFrame:
    """Return a copy of a price frame with its daily moves in random order.

    Args:
        frame: Price frame with close, dividends, capital_gains and tr_close.
        seed: Seed (or SeedSequence) for numpy.random.default_rng, which draws
            the permutation.

    Returns:
        A frame on the same dates. The first row is kept. For rows 1 onward the
        pairs (close[t] / close[t-1], distributions[t] / close[t-1]) are
        permuted and the path rebuilt. All distributions are reported in the
        dividends column, capital_gains is zero, and tr_close is recomputed.
    """
    close = frame["close"].to_numpy(dtype=float)
    dist = (frame["dividends"] + frame["capital_gains"]).to_numpy(dtype=float)
    if len(close) < 3:
        raise ValueError("need at least 3 rows to shuffle")
    growth = close[1:] / close[:-1]
    dist_yield = dist[1:] / close[:-1]
    order = np.random.default_rng(seed).permutation(len(growth))
    new_close = np.empty_like(close)
    new_close[0] = close[0]
    new_close[1:] = close[0] * np.cumprod(growth[order])
    new_dist = np.empty_like(dist)
    new_dist[0] = dist[0]
    new_dist[1:] = dist_yield[order] * new_close[:-1]
    out = pd.DataFrame(
        {"close": new_close, "dividends": new_dist, "capital_gains": 0.0},
        index=frame.index,
    )
    out["tr_close"] = total_return_index(
        out["close"], out["dividends"], out["capital_gains"]
    ).to_numpy()
    return out


def shuffle_pair(
    a: pd.DataFrame, b: pd.DataFrame, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Shuffled-date placebo of a pair: both legs shuffled, independently.

    The two permutations come from one numpy.random.SeedSequence(seed), which
    is split into two child seeds, so the legs never share a permutation.
    """
    first, second = np.random.SeedSequence(seed).spawn(2)
    return shuffle_dates(a, first), shuffle_dates(b, second)


def placebo_rank(real: float, placebo: np.ndarray) -> dict[str, float]:
    """Where a real result stands among its placebos.

    Args:
        real: The real pair's metric (for example its net Sharpe ratio).
        placebo: The same metric for each placebo. NaN entries (a placebo
            that never traded) are left out.

    Returns:
        n_placebos (those with a defined metric), placebo_mean, and
        share_at_least, the share of placebos with a metric at least as large
        as the real one, counting the real result as one of the draws:
        (1 + number at least as large) / (1 + n). Both are NaN if the real
        metric is NaN or there is no placebo.
    """
    values = np.asarray(placebo, dtype=float)
    values = values[np.isfinite(values)]
    n = len(values)
    if n == 0 or not math.isfinite(real):
        return {"n_placebos": float(n), "placebo_mean": math.nan,
                "share_at_least": math.nan}
    return {
        "n_placebos": float(n),
        "placebo_mean": float(values.mean()),
        "share_at_least": float((1 + (values >= real).sum()) / (1 + n)),
    }


def simulated_pair_frames(
    kind: str, seed: int, config: BacktestConfig, start: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Price frames of one simulated control pair.

    Args:
        kind: "cointegrated" or "random_walk".
        seed: Simulation seed.
        config: Supplies the simulator parameters (config.controls).
        start: First date of the business-day index.
    """
    c = config.controls
    if kind == "cointegrated":
        data = simulate_cointegrated_pair(
            seed=seed, beta=c.beta, alpha=c.alpha, half_life=c.half_life,
            spread_sd=c.spread_sd, sigma_b=c.sigma, n_obs=c.n_obs, start=start,
        )
    elif kind == "random_walk":
        data = simulate_random_walk_pair(
            seed=seed, n_obs=c.n_obs, sigma=c.sigma, start=start
        )
    else:
        raise ValueError(f"kind must be cointegrated or random_walk, got {kind!r}")
    return as_price_frame(data["log_a"]), as_price_frame(data["log_b"])


def _row(seed: int, result: BacktestResult) -> dict[str, Any]:
    metrics = span_metrics(result)
    if metrics is None:
        raise ValueError("the backtest has no rows after the first signal bar")
    return {
        "seed": seed,
        "sharpe": metrics["sharpe"],
        "gross_sharpe": metrics["gross_sharpe"],
        "total_return": metrics["total_return"],
        "gross_return": metrics["price_return"] + metrics["distribution_return"],
        "n_trades": metrics["n_trades"],
        "hit_rate": metrics["hit_rate"],
        "share_in_market": metrics["share_in_market"],
    }


def run_batch(
    make_frames: Callable[
        [int], tuple[pd.DataFrame, pd.DataFrame] | dict[str, pd.DataFrame]
    ],
    seeds: range,
    *,
    asof: pd.Timestamp | str,
    config: BacktestConfig,
    hedge: str | None = None,
    cost_bps: float | None = None,
) -> pd.DataFrame:
    """Backtest one pair or basket per seed and collect the full-span metrics.

    Args:
        make_frames: Returns, for a seed, either the two legs' price frames (a
            pair) or a dict of three or more frames (a Johansen basket).
        seeds: Seeds to run.
        asof, config, hedge, cost_bps: As for run_pair_backtest. `hedge` is
            ignored for a basket.

    Returns:
        One row per seed with the columns in BATCH_COLUMNS. Returns are over
        the whole run from the first signal bar, as fractions of capital.
    """
    rows = []
    for seed in seeds:
        frames = make_frames(seed)
        if isinstance(frames, dict):
            result = run_basket_backtest(
                frames, asof=asof, config=config, cost_bps=cost_bps
            )
        else:
            a, b = frames
            result = run_pair_backtest(
                a, b, asof=asof, config=config, hedge=hedge, cost_bps=cost_bps
            )
        rows.append(_row(seed, result))
    return pd.DataFrame(rows, columns=list(BATCH_COLUMNS))


def summarise_batch(batch: pd.DataFrame) -> dict[str, Any]:
    """Summary of a batch: what the per-seed results look like as a group.

    Returns:
        n_seeds; mean, median and 5th, 25th, 75th and 95th percentile of the net
        Sharpe ratio over seeds where it is defined (n_sharpe_defined);
        mean_total_return and mean_gross_return; gross_return_t, the mean gross
        return over its standard error (sd / sqrt(n), ddof 1), which should be
        near zero when there is no edge; share_positive, the share of seeds
        with a positive net total return; share_sharpe_above_1; and
        mean_trades.
    """
    n = len(batch)
    if n < 2:
        raise ValueError("a batch needs at least 2 seeds")
    sharpe = batch["sharpe"].to_numpy(dtype=float)
    defined = sharpe[np.isfinite(sharpe)]
    gross = batch["gross_return"].to_numpy(dtype=float)
    net = batch["total_return"].to_numpy(dtype=float)
    gross_sd = float(gross.std(ddof=1))
    quantiles = (
        np.percentile(defined, [5, 25, 50, 75, 95]) if len(defined) else [math.nan] * 5
    )
    return {
        "n_seeds": n,
        "n_sharpe_defined": len(defined),
        "mean_sharpe": float(defined.mean()) if len(defined) else math.nan,
        "sharpe_p05": float(quantiles[0]),
        "sharpe_p25": float(quantiles[1]),
        "median_sharpe": float(quantiles[2]),
        "sharpe_p75": float(quantiles[3]),
        "sharpe_p95": float(quantiles[4]),
        "mean_total_return": float(net.mean()),
        "mean_gross_return": float(gross.mean()),
        "gross_return_t": (
            float(gross.mean() / (gross_sd / math.sqrt(n))) if gross_sd > 0 else math.nan
        ),
        "share_positive": float((net > 0.0).mean()),
        "share_sharpe_above_1": float((sharpe > 1.0).mean()),
        "mean_trades": float(batch["n_trades"].mean()),
    }
